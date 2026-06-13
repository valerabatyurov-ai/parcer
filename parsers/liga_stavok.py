from __future__ import annotations

from parsers.base import BaseBookmakerParser
from schemas import Event


class LigaStavokParser(BaseBookmakerParser):
    bookmaker_name = "Liga Stavok"

    async def fetch_events(self) -> list[dict]:
        return []

    async def fetch_event_markets(self, event: dict) -> list[dict]:
        return []

    async def parse(self) -> list[Event]:
        return []
