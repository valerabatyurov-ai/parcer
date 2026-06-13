from __future__ import annotations

from typing import Any

from parsers.base import BaseBookmakerParser
from schemas import Event, ParserError


class FonbetParser(BaseBookmakerParser):
    bookmaker_name = "FONBET"
    sample_file = "sample_fonbet.json"

    @property
    def source_url(self) -> str:
        return self.settings.fonbet_api_url

    async def fetch_events(self) -> list[dict[str, Any]]:
        if self.settings.use_sample_data:
            self.ensure_sample_exists()
            return self.load_sample_payload().get("events", [])
        payload = await self.fetch_json(self.source_url)
        if isinstance(payload, dict) and "events" in payload:
            return payload["events"]
        raise ParserError(
            self.bookmaker_name,
            "Unsupported FONBET payload. Configure FONBET_API_URL to return normalized events or adapt parser mapping.",
            self.source_url,
            "payload_error",
        )

    async def fetch_event_markets(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        return list(event.get("markets", []))

    async def parse(self) -> list[Event]:
        raw_events = await self.fetch_events()
        for event in raw_events:
            event["markets"] = await self.fetch_event_markets(event)
        return self.parse_normalized_payload({"events": raw_events})
