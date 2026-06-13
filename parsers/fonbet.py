from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from parsers.base import BaseBookmakerParser
from schemas import Event, Market, Outcome, ParserError


WIN_1X2_FACTORS = {
    921: ("1", "П1"),
    922: ("x", "Ничья"),
    923: ("2", "П2"),
}

HANDICAP_FACTOR_PAIRS = [
    (927, 928),
    (989, 991),
]

TOTAL_FACTOR_PAIRS = [
    (930, 931),
]


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
        if isinstance(payload, dict) and "events" in payload and "customFactors" not in payload:
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
        if not self.settings.use_sample_data:
            payload = await self.fetch_json(self.source_url)
            if isinstance(payload, dict) and "customFactors" in payload:
                return self.parse_fonbet_event_payload(payload)
            if isinstance(payload, dict) and "events" in payload:
                return self.parse_normalized_payload(payload)

        raw_events = await self.fetch_events()
        for event in raw_events:
            event["markets"] = await self.fetch_event_markets(event)
        return self.parse_normalized_payload({"events": raw_events})

    def parse_fonbet_event_payload(self, payload: dict[str, Any]) -> list[Event]:
        raw_events = payload.get("events") or []
        event_id = self._event_id_from_url(self.source_url)
        root_event = self._find_root_event(raw_events, event_id)
        if root_event is None:
            raise ParserError(self.bookmaker_name, "Root event was not found in FONBET payload", self.source_url)

        factors = self._factors_for_event(payload, int(root_event["id"]))
        if not factors:
            raise ParserError(self.bookmaker_name, "Odds were not found in FONBET payload", self.source_url)

        sport, league = self._sport_and_league(payload, int(root_event.get("sportId", 0)))
        markets = self._build_markets(root_event, factors)
        if not markets:
            raise ParserError(self.bookmaker_name, "Supported FONBET markets were not found", self.source_url)

        return [
            Event(
                bookmaker=self.bookmaker_name,
                sport=sport,
                league=league,
                home_team=str(root_event.get("team1") or ""),
                away_team=str(root_event.get("team2") or ""),
                start_time=datetime.fromtimestamp(int(root_event["startTime"]), tz=timezone.utc),
                event_url=self._event_url(root_event, sport),
                external_event_id=str(root_event.get("id")),
                markets=markets,
            )
        ]

    def _build_markets(self, event: dict[str, Any], factors: list[dict[str, Any]]) -> list[Market]:
        by_id = {int(item["f"]): item for item in factors if "f" in item and "v" in item}
        markets: list[Market] = []

        one_x_two = self._build_1x2_market(event, by_id)
        if one_x_two is not None:
            markets.append(one_x_two)

        for home_factor_id, away_factor_id in HANDICAP_FACTOR_PAIRS:
            market = self._build_handicap_market(event, by_id, home_factor_id, away_factor_id)
            if market is not None:
                markets.append(market)

        for over_factor_id, under_factor_id in TOTAL_FACTOR_PAIRS:
            market = self._build_total_market(by_id, over_factor_id, under_factor_id)
            if market is not None:
                markets.append(market)

        return markets

    def _build_1x2_market(self, event: dict[str, Any], by_id: dict[int, dict[str, Any]]) -> Market | None:
        outcomes: list[Outcome] = []
        names = {
            921: str(event.get("team1") or "П1"),
            922: "Ничья",
            923: str(event.get("team2") or "П2"),
        }
        for factor_id, (side, default_name) in WIN_1X2_FACTORS.items():
            factor = by_id.get(factor_id)
            if not factor:
                continue
            outcomes.append(
                Outcome(
                    outcome_name=names.get(factor_id, default_name),
                    side=side,
                    odds=float(factor["v"]),
                )
            )
        if len(outcomes) < 2:
            return None
        return Market(market_type="1x2", market_name="1X2", line=None, outcomes=outcomes)

    def _build_handicap_market(
        self,
        event: dict[str, Any],
        by_id: dict[int, dict[str, Any]],
        home_factor_id: int,
        away_factor_id: int,
    ) -> Market | None:
        home_factor = by_id.get(home_factor_id)
        away_factor = by_id.get(away_factor_id)
        if not home_factor or not away_factor:
            return None

        home_line = self._line_text(home_factor)
        away_line = self._line_text(away_factor)
        line = home_line or away_line
        return Market(
            market_type="handicap",
            market_name="Фора",
            line=line,
            outcomes=[
                Outcome(
                    outcome_name=f"{event.get('team1')} {home_line}".strip(),
                    side="home",
                    odds=float(home_factor["v"]),
                ),
                Outcome(
                    outcome_name=f"{event.get('team2')} {away_line}".strip(),
                    side="away",
                    odds=float(away_factor["v"]),
                ),
            ],
        )

    def _build_total_market(
        self,
        by_id: dict[int, dict[str, Any]],
        over_factor_id: int,
        under_factor_id: int,
    ) -> Market | None:
        over_factor = by_id.get(over_factor_id)
        under_factor = by_id.get(under_factor_id)
        if not over_factor or not under_factor:
            return None

        line = self._line_text(over_factor) or self._line_text(under_factor)
        return Market(
            market_type="total",
            market_name="Тотал",
            line=line,
            outcomes=[
                Outcome(outcome_name=f"ТБ {line}".strip(), side="over", odds=float(over_factor["v"])),
                Outcome(outcome_name=f"ТМ {line}".strip(), side="under", odds=float(under_factor["v"])),
            ],
        )

    def _find_root_event(self, raw_events: list[dict[str, Any]], event_id: int | None) -> dict[str, Any] | None:
        if event_id is not None:
            for event in raw_events:
                if event.get("id") == event_id:
                    return event
        for event in raw_events:
            if event.get("team1") and event.get("team2") and not event.get("parentId"):
                return event
        return None

    def _factors_for_event(self, payload: dict[str, Any], event_id: int) -> list[dict[str, Any]]:
        for group in payload.get("customFactors") or []:
            if group.get("e") == event_id:
                return list(group.get("factors") or [])
        return []

    def _sport_and_league(self, payload: dict[str, Any], sport_id: int) -> tuple[str, str]:
        sports_by_id = {item.get("id"): item for item in payload.get("sports") or []}
        league = str(sports_by_id.get(sport_id, {}).get("name") or "")

        current = sports_by_id.get(sport_id)
        while current:
            if current.get("kind") == "sport":
                return str(current.get("alias") or current.get("name") or "unknown").lower(), league
            current = sports_by_id.get(current.get("parentId"))

        return "unknown", league

    def _event_url(self, event: dict[str, Any], sport: str) -> str:
        sport_id = event.get("sportId")
        event_id = event.get("id")
        if sport_id and event_id and sport != "unknown":
            return f"https://fon.bet/sports/{sport}/{sport_id}/{event_id}"
        return self.source_url

    def _line_text(self, factor: dict[str, Any]) -> str:
        if factor.get("pt") not in (None, ""):
            return str(factor["pt"])
        if factor.get("p") in (None, ""):
            return ""
        return str(float(factor["p"]) / 100).rstrip("0").rstrip(".")

    def _event_id_from_url(self, url: str) -> int | None:
        try:
            query = parse_qs(urlparse(url).query)
            raw = query.get("eventId", [None])[0]
            return int(raw) if raw else None
        except ValueError:
            return None
