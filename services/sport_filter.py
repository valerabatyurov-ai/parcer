from __future__ import annotations

from config import Settings
from schemas import Event, Market


class SportFilter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def allow_event(self, event: Event) -> bool:
        sport = event.sport.lower()
        if sport in self.settings.sport_blacklist:
            return False
        if self.settings.enable_only_liquid_sports and sport not in self.settings.sport_whitelist:
            return False
        return True

    def allow_market(self, market: Market) -> bool:
        if not self.settings.skip_low_liquidity_markets:
            return True
        return market.market_type in {
            "winner",
            "moneyline",
            "1x2",
            "handicap",
            "total",
            "individual_total",
        }

    def filter_events(self, events: list[Event]) -> list[Event]:
        filtered: list[Event] = []
        for event in events:
            if not self.allow_event(event):
                continue
            event.markets = [market for market in event.markets if self.allow_market(market)]
            filtered.append(event)
        return filtered
