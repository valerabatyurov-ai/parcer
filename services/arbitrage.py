from __future__ import annotations

import hashlib
from datetime import datetime

from config import Settings
from schemas import ArbitrageOpportunity, Event, Market, Outcome
from services.matcher import EventPair
from services.stake_calculator import calculate_stakes, implied_sum, profit_percent
from utils.logging import logger


OPPOSITE_SIDES = {
    "home": {"away"},
    "away": {"home"},
    "over": {"under"},
    "under": {"over"},
    "1": {"2"},
    "2": {"1"},
    "p1": {"p2"},
    "p2": {"p1"},
}


class ArbitrageFinder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def find(self, event_pairs: list[EventPair]) -> list[ArbitrageOpportunity]:
        opportunities: list[ArbitrageOpportunity] = []
        for pair in event_pairs:
            opportunities.extend(self._find_for_pair(pair))
        opportunities.sort(key=lambda item: item.profit_percent, reverse=True)
        return opportunities

    def _find_for_pair(self, pair: EventPair) -> list[ArbitrageOpportunity]:
        found: list[ArbitrageOpportunity] = []
        for left_market in pair.left.markets:
            for right_market in pair.right.markets:
                if not self._same_market(left_market, right_market):
                    continue
                for left_outcome in left_market.outcomes:
                    for right_outcome in right_market.outcomes:
                        if not self._opposite_outcomes(left_outcome, right_outcome):
                            continue
                        total = implied_sum(left_outcome.odds, right_outcome.odds)
                        if total >= 1:
                            continue
                        profit = profit_percent(left_outcome.odds, right_outcome.odds)
                        if profit < self.settings.min_profit_percent:
                            continue
                        stake_plan = calculate_stakes(
                            self.settings.bankroll_rub,
                            left_outcome.odds,
                            right_outcome.odds,
                        )
                        opportunity = self._build_opportunity(
                            pair.left,
                            pair.right,
                            left_market,
                            left_outcome,
                            right_market,
                            right_outcome,
                            total,
                            profit,
                            stake_plan,
                        )
                        logger.bind(channel="arbitrage").info(
                            "Arbitrage found: {profit:.2f}% {event} {market} {line}",
                            profit=opportunity.profit_percent,
                            event=opportunity.event_name,
                            market=opportunity.market_type,
                            line=opportunity.line,
                        )
                        found.append(opportunity)
        return found

    def _same_market(self, left: Market, right: Market) -> bool:
        if left.market_type != right.market_type:
            return False
        return self._line_key(left.market_type, left.line) == self._line_key(right.market_type, right.line)

    def _line_key(self, market_type: str, line: str | None) -> str:
        if line in (None, ""):
            return ""
        text = str(line).replace(",", ".").strip()
        if market_type in {"handicap", "total", "individual_total"}:
            try:
                return f"{abs(float(text)):.2f}"
            except ValueError:
                return text
        return text.lower()

    def _opposite_outcomes(self, left: Outcome, right: Outcome) -> bool:
        left_side = left.side.lower()
        right_side = right.side.lower()
        return right_side in OPPOSITE_SIDES.get(left_side, set())

    def _build_opportunity(
        self,
        left_event: Event,
        right_event: Event,
        left_market: Market,
        left_outcome: Outcome,
        right_market: Market,
        right_outcome: Outcome,
        total: float,
        profit: float,
        stake_plan,
    ) -> ArbitrageOpportunity:
        event_key = self.event_key(left_event, right_event, left_market)
        return ArbitrageOpportunity(
            event_key=event_key,
            sport=left_event.sport,
            league=left_event.league,
            event_name=left_event.event_name,
            market_type=left_market.market_type,
            market_name=left_market.market_name,
            line=left_market.line or right_market.line,
            bookmaker_1=left_event.bookmaker,
            outcome_1=left_outcome.outcome_name,
            odds_1=left_outcome.odds,
            bookmaker_2=right_event.bookmaker,
            outcome_2=right_outcome.outcome_name,
            odds_2=right_outcome.odds,
            implied_sum=total,
            profit_percent=profit,
            bankroll_rub=self.settings.bankroll_rub,
            stake_1=stake_plan.stake_1,
            stake_2=stake_plan.stake_2,
            expected_payout=stake_plan.expected_payout,
            profit_rub=stake_plan.profit_rub,
            detected_at=datetime.now(self.settings.timezone),
            event_start_time=left_event.start_time,
            event_url_1=left_event.event_url,
            event_url_2=right_event.event_url,
        )

    @staticmethod
    def event_key(left_event: Event, right_event: Event, market: Market) -> str:
        raw = "|".join(
            [
                left_event.sport,
                left_event.league.lower(),
                left_event.home_team.lower(),
                left_event.away_team.lower(),
                left_event.start_time.isoformat(),
                market.market_type,
                str(market.line or ""),
                left_event.bookmaker,
                right_event.bookmaker,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
