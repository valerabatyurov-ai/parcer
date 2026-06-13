from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Settings
from schemas import ArbitrageOpportunity, Event, ParserError
from services.normalizer import Normalizer
from services.telegram import TelegramNotifier
from services.matcher import UnmatchedCandidate
from storage.models import (
    ArbitrageOpportunityModel,
    Base,
    Bookmaker,
    EventModel,
    MarketModel,
    OddsHistory,
    OddsModel,
    ParserErrorModel,
    SentNotification,
    UnmatchedEvent,
)


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_async_engine(settings.async_database_url, future=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def save_events(self, events: list[Event], normalizer: Normalizer) -> None:
        async with self.session_factory() as session:
            for event in events:
                bookmaker = await self._get_or_create_bookmaker(session, event.bookmaker)
                db_event = await self._get_or_create_event(session, bookmaker, event, normalizer)
                await session.flush()

                for market in event.markets:
                    db_market = await self._get_or_create_market(session, db_event, market.market_type, market.line)
                    db_market.market_name = market.market_name
                    db_market.updated_at = datetime.utcnow()
                    await session.flush()

                    for outcome in market.outcomes:
                        odds = await self._get_or_create_odds(session, db_market, outcome.outcome_name, outcome.side)
                        odds.odds = outcome.odds
                        odds.collected_at = datetime.utcnow()
                        history = OddsHistory(
                            bookmaker_id=bookmaker.id,
                            event_id=db_event.id,
                            market_id=db_market.id,
                            outcome_name=outcome.outcome_name,
                            odds=outcome.odds,
                        )
                        session.add_all([odds, history])
            await session.commit()

    async def save_arbitrage(self, opportunity: ArbitrageOpportunity) -> None:
        async with self.session_factory() as session:
            session.add(
                ArbitrageOpportunityModel(
                    event_key=opportunity.event_key,
                    sport=opportunity.sport,
                    league=opportunity.league,
                    event_name=opportunity.event_name,
                    market_type=opportunity.market_type,
                    line=opportunity.line,
                    bookmaker_1=opportunity.bookmaker_1,
                    outcome_1=opportunity.outcome_1,
                    odds_1=opportunity.odds_1,
                    bookmaker_2=opportunity.bookmaker_2,
                    outcome_2=opportunity.outcome_2,
                    odds_2=opportunity.odds_2,
                    implied_sum=opportunity.implied_sum,
                    profit_percent=opportunity.profit_percent,
                    bankroll_rub=opportunity.bankroll_rub,
                    stake_1=opportunity.stake_1,
                    stake_2=opportunity.stake_2,
                    expected_payout=opportunity.expected_payout,
                    profit_rub=opportunity.profit_rub,
                    detected_at=opportunity.detected_at,
                )
            )
            await session.commit()

    async def should_send_notification(self, opportunity: ArbitrageOpportunity) -> bool:
        arbitrage_hash = TelegramNotifier.arbitrage_hash(opportunity)
        async with self.session_factory() as session:
            existing = await session.scalar(
                select(SentNotification).where(SentNotification.arbitrage_hash == arbitrage_hash)
            )
            if existing is None:
                return True

            resend_at = existing.sent_at + timedelta(minutes=self.settings.resend_after_minutes)
            profit_grew = (
                opportunity.profit_percent - existing.profit_percent
                >= self.settings.profit_change_threshold_percent
            )
            return datetime.utcnow() >= resend_at or profit_grew

    async def save_sent_notification(self, opportunity: ArbitrageOpportunity, message_id: int | None) -> None:
        arbitrage_hash = TelegramNotifier.arbitrage_hash(opportunity)
        snapshot = json.dumps(
            {
                "odds_1": opportunity.odds_1,
                "odds_2": opportunity.odds_2,
                "profit_percent": opportunity.profit_percent,
            },
            ensure_ascii=False,
        )
        async with self.session_factory() as session:
            existing = await session.scalar(
                select(SentNotification).where(SentNotification.arbitrage_hash == arbitrage_hash)
            )
            if existing:
                existing.telegram_message_id = message_id
                existing.profit_percent = opportunity.profit_percent
                existing.odds_snapshot = snapshot
                existing.sent_at = datetime.utcnow()
            else:
                session.add(
                    SentNotification(
                        arbitrage_hash=arbitrage_hash,
                        telegram_message_id=message_id,
                        profit_percent=opportunity.profit_percent,
                        odds_snapshot=snapshot,
                    )
                )
            await session.commit()

    async def save_parser_error(self, error: ParserError) -> None:
        async with self.session_factory() as session:
            session.add(
                ParserErrorModel(
                    bookmaker=error.bookmaker,
                    error_type=error.error_type,
                    error_message=error.message,
                    url=error.url,
                )
            )
            await session.commit()

    async def save_unmatched_candidates(self, candidates: list[UnmatchedCandidate]) -> None:
        if not candidates:
            return
        async with self.session_factory() as session:
            for candidate in candidates:
                session.add(
                    UnmatchedEvent(
                        bookmaker_1=candidate.left.bookmaker,
                        event_name_1=candidate.left.event_name,
                        bookmaker_2=candidate.right.bookmaker,
                        event_name_2=candidate.right.event_name,
                        sport=candidate.left.sport,
                        league=candidate.left.league,
                        start_time_1=candidate.left.start_time,
                        start_time_2=candidate.right.start_time,
                        confidence=candidate.confidence,
                        suggested_alias=candidate.suggested_alias,
                    )
                )
            await session.commit()

    async def _get_or_create_bookmaker(self, session: AsyncSession, name: str) -> Bookmaker:
        slug = name.lower().replace(" ", "_")
        bookmaker = await session.scalar(select(Bookmaker).where(Bookmaker.slug == slug))
        if bookmaker is not None:
            return bookmaker
        bookmaker = Bookmaker(name=name, slug=slug, base_url="")
        session.add(bookmaker)
        await session.flush()
        return bookmaker

    async def _get_or_create_event(
        self,
        session: AsyncSession,
        bookmaker: Bookmaker,
        event: Event,
        normalizer: Normalizer,
    ) -> EventModel:
        filters = [EventModel.bookmaker_id == bookmaker.id]
        if event.external_event_id:
            filters.append(EventModel.external_event_id == event.external_event_id)
        else:
            filters.extend(
                [
                    EventModel.sport == event.sport,
                    EventModel.home_team == event.home_team,
                    EventModel.away_team == event.away_team,
                    EventModel.start_time == event.start_time,
                ]
            )

        db_event = await session.scalar(select(EventModel).where(*filters))
        if db_event is None:
            db_event = EventModel(
                bookmaker_id=bookmaker.id,
                external_event_id=event.external_event_id,
                sport=event.sport,
                league=event.league,
                home_team=event.home_team,
                away_team=event.away_team,
                normalized_home_team=normalizer.normalize_team(event.home_team),
                normalized_away_team=normalizer.normalize_team(event.away_team),
                start_time=event.start_time,
                event_url=event.event_url,
            )
            session.add(db_event)
        else:
            db_event.sport = event.sport
            db_event.league = event.league
            db_event.home_team = event.home_team
            db_event.away_team = event.away_team
            db_event.normalized_home_team = normalizer.normalize_team(event.home_team)
            db_event.normalized_away_team = normalizer.normalize_team(event.away_team)
            db_event.start_time = event.start_time
            db_event.event_url = event.event_url
            db_event.updated_at = datetime.utcnow()
        return db_event

    async def _get_or_create_market(
        self,
        session: AsyncSession,
        event: EventModel,
        market_type: str,
        line: str | None,
    ) -> MarketModel:
        market = await session.scalar(
            select(MarketModel).where(
                MarketModel.event_id == event.id,
                MarketModel.market_type == market_type,
                MarketModel.line == line,
            )
        )
        if market is not None:
            return market
        market = MarketModel(event_id=event.id, market_type=market_type, market_name=market_type, line=line)
        session.add(market)
        await session.flush()
        return market

    async def _get_or_create_odds(
        self,
        session: AsyncSession,
        market: MarketModel,
        outcome_name: str,
        side: str,
    ) -> OddsModel:
        odds = await session.scalar(
            select(OddsModel).where(
                OddsModel.market_id == market.id,
                OddsModel.outcome_name == outcome_name,
                OddsModel.side == side,
            )
        )
        if odds is not None:
            return odds
        odds = OddsModel(market_id=market.id, outcome_name=outcome_name, side=side, odds=0)
        session.add(odds)
        await session.flush()
        return odds
