from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from config import DATA_DIR, Settings
from schemas import Event, ParserError


class BaseBookmakerParser(ABC):
    bookmaker_name: str
    source_url: str = ""
    sample_file: str = ""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def fetch_events(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_event_markets(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def parse(self) -> list[Event]:
        raise NotImplementedError

    async def fetch_json(self, url: str) -> Any:
        if not url:
            raise ParserError(self.bookmaker_name, "Public JSON endpoint is not configured")

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/json,text/plain,*/*",
                    "User-Agent": "OddsArbitrageMonitor/1.0 (+local monitoring; no betting)",
                },
            )
            response.raise_for_status()
            return response.json()

    def load_sample_payload(self) -> dict[str, Any]:
        path = DATA_DIR / self.sample_file
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def parse_normalized_payload(self, payload: Any) -> list[Event]:
        if isinstance(payload, dict):
            raw_events = payload.get("events", [])
        elif isinstance(payload, list):
            raw_events = payload
        else:
            raise ParserError(self.bookmaker_name, "Unsupported JSON payload type")

        events: list[Event] = []
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue
            data = {**raw_event, "bookmaker": raw_event.get("bookmaker") or self.bookmaker_name}
            events.append(Event.model_validate(data))
        return events

    def ensure_sample_exists(self) -> None:
        path = DATA_DIR / self.sample_file
        if not Path(path).exists():
            raise ParserError(self.bookmaker_name, f"Sample file is missing: {path}", error_type="sample_error")
