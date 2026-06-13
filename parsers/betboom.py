from __future__ import annotations

from parsers.base import BaseBookmakerParser
from schemas import Event


class BetBoomParser(BaseBookmakerParser):
    bookmaker_name = "BetBoom"

    async def fetch_events(self) -> list[dict]:
        return []

    async def fetch_event_markets(self, event: dict) -> list[dict]:
        return []

    async def parse(self) -> list[Event]:
        return []
