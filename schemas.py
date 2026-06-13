from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Outcome(BaseModel):
    model_config = ConfigDict(extra="allow")

    outcome_name: str
    side: str
    odds: float

    @field_validator("side")
    @classmethod
    def normalize_side(cls, value: str) -> str:
        return value.strip().lower()


class Market(BaseModel):
    model_config = ConfigDict(extra="allow")

    market_type: str
    market_name: str
    line: str | None = None
    outcomes: list[Outcome] = Field(default_factory=list)

    @field_validator("market_type")
    @classmethod
    def normalize_market_type(cls, value: str) -> str:
        return value.strip().lower()


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")

    bookmaker: str
    sport: str
    league: str
    home_team: str
    away_team: str
    start_time: datetime
    event_url: str = ""
    external_event_id: str | None = None
    markets: list[Market] = Field(default_factory=list)

    @field_validator("bookmaker", mode="before")
    @classmethod
    def normalize_bookmaker(cls, value: str) -> str:
        return str(value).strip().upper()

    @field_validator("sport", mode="before")
    @classmethod
    def normalize_sport(cls, value: str) -> str:
        return str(value).strip().lower()

    @property
    def event_name(self) -> str:
        return f"{self.home_team} - {self.away_team}"


class StakePlan(BaseModel):
    stake_1: float
    stake_2: float
    expected_payout: float
    profit_rub: float


class ArbitrageOpportunity(BaseModel):
    event_key: str
    sport: str
    league: str
    event_name: str
    market_type: str
    market_name: str
    line: str | None
    bookmaker_1: str
    outcome_1: str
    odds_1: float
    bookmaker_2: str
    outcome_2: str
    odds_2: float
    implied_sum: float
    profit_percent: float
    bankroll_rub: float
    stake_1: float
    stake_2: float
    expected_payout: float
    profit_rub: float
    detected_at: datetime
    event_start_time: datetime
    event_url_1: str = ""
    event_url_2: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParserError(Exception):
    def __init__(self, bookmaker: str, message: str, url: str = "", error_type: str = "parser_error") -> None:
        super().__init__(message)
        self.bookmaker = bookmaker
        self.message = message
        self.url = url
        self.error_type = error_type
