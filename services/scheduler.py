from __future__ import annotations

import asyncio
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Settings
from parsers.base import BaseBookmakerParser
from schemas import Event, ParserError
from services.arbitrage import ArbitrageFinder
from services.matcher import EventMatcher
from services.normalizer import Normalizer
from services.sport_filter import SportFilter
from services.telegram import TelegramNotifier
from storage.db import Database
from utils.logging import logger


@dataclass(slots=True)
class MonitoringApp:
    settings: Settings
    db: Database
    parsers: list[BaseBookmakerParser]

    def __post_init__(self) -> None:
        self.normalizer = Normalizer()
        self.sport_filter = SportFilter(self.settings)
        self.matcher = EventMatcher(self.settings, self.normalizer)
        self.arbitrage_finder = ArbitrageFinder(self.settings)
        self.telegram = TelegramNotifier(self.settings)

    async def scan_once(self) -> None:
        logger.info("Scan started")
        events: list[Event] = []

        for parser in self.parsers:
            try:
                parsed_events = await parser.parse()
                logger.info("{} returned {} events", parser.bookmaker_name, len(parsed_events))
                events.extend(parsed_events)
            except ParserError as error:
                await self.db.save_parser_error(error)
                await self.telegram.send_parser_error(error)
                logger.warning("{} parser error: {}", error.bookmaker, error.message)
            except Exception as exc:  # noqa: BLE001 - scanner must keep other parsers alive
                error = ParserError(parser.bookmaker_name, str(exc), getattr(parser, "source_url", ""), "unexpected_error")
                await self.db.save_parser_error(error)
                await self.telegram.send_parser_error(error)
                logger.exception("{} unexpected parser error", parser.bookmaker_name)

        events = self.sport_filter.filter_events(events)
        await self.db.save_events(events, self.normalizer)

        event_pairs = self.matcher.match(events)
        await self.db.save_unmatched_candidates(self.matcher.unmatched_candidates)
        opportunities = self.arbitrage_finder.find(event_pairs)
        logger.info(
            "Scan finished: events={}, pairs={}, arbitrage={}",
            len(events),
            len(event_pairs),
            len(opportunities),
        )

        for opportunity in opportunities:
            await self.db.save_arbitrage(opportunity)
            should_send = await self.db.should_send_notification(opportunity)
            if not should_send:
                continue
            message_id = await self.telegram.send_arbitrage(opportunity)
            if message_id is not None:
                await self.db.save_sent_notification(opportunity, message_id)

    async def run_forever(self) -> None:
        scheduler = AsyncIOScheduler(timezone=self.settings.timezone)
        scheduler.add_job(
            self.scan_once,
            "interval",
            minutes=self.settings.scan_interval_minutes,
            max_instances=1,
        )
        scheduler.start()
        logger.info("Scheduler started: every {} minutes", self.settings.scan_interval_minutes)

        await self.scan_once()
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            scheduler.shutdown(wait=False)
