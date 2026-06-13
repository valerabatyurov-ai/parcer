from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
LOG_DIR = ROOT_DIR / "logs"
DATA_DIR = ROOT_DIR / "data"


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return list(default)
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def parse_timezone(value: str) -> timezone:
    normalized = value.strip().upper().replace(" ", "")
    if normalized in {"UTC", "Z"}:
        return timezone.utc
    if normalized.startswith("UTC"):
        offset = normalized[3:]
        sign = 1
        if offset.startswith("+"):
            offset = offset[1:]
        elif offset.startswith("-"):
            sign = -1
            offset = offset[1:]
        hours, _, minutes = offset.partition(":")
        return timezone(sign * timedelta(hours=int(hours or 0), minutes=int(minutes or 0)))
    raise ValueError(f"Unsupported TIMEZONE value: {value}")


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    scan_interval_minutes: int = 5
    bankroll_rub: float = 10000.0
    min_profit_percent: float = 5.0
    timezone_name: str = "UTC+5"
    date_format: str = "%d/%m"
    database_url: str = "sqlite:///odds_monitor.db"
    mode: str = "monitoring_only"

    enable_only_liquid_sports: bool = True
    skip_low_liquidity_markets: bool = True
    sport_whitelist: list[str] = field(
        default_factory=lambda: [
            "football",
            "hockey",
            "basketball",
            "tennis",
            "volleyball",
            "mma",
            "boxing",
            "cs",
            "dota2",
            "lol",
            "valorant",
        ]
    )
    sport_blacklist: list[str] = field(
        default_factory=lambda: [
            "chess",
            "virtual_sport",
            "cyberfootball",
            "cyberbasketball",
            "table_tennis_low_tier",
            "unknown_low_liquidity_sports",
        ]
    )

    team_match_threshold: int = 88
    league_match_threshold: int = 80
    max_start_time_diff_minutes: int = 10
    resend_after_minutes: int = 60
    profit_change_threshold_percent: float = 0.5

    fonbet_api_url: str = ""
    winline_api_url: str = ""
    use_sample_data: bool = False

    @property
    def timezone(self) -> timezone:
        return parse_timezone(self.timezone_name)

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return self.database_url

    @classmethod
    def from_env(cls, env_file: str | os.PathLike[str] | None = None) -> "Settings":
        load_dotenv(env_file or ROOT_DIR / ".env")
        defaults = cls()
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", defaults.telegram_bot_token),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", defaults.telegram_chat_id),
            scan_interval_minutes=_int(os.getenv("SCAN_INTERVAL_MINUTES"), defaults.scan_interval_minutes),
            bankroll_rub=_float(os.getenv("BANKROLL_RUB"), defaults.bankroll_rub),
            min_profit_percent=_float(os.getenv("MIN_PROFIT_PERCENT"), defaults.min_profit_percent),
            timezone_name=os.getenv("TIMEZONE", defaults.timezone_name),
            date_format=os.getenv("DATE_FORMAT", defaults.date_format),
            database_url=os.getenv("DATABASE_URL", defaults.database_url),
            mode=os.getenv("MODE", defaults.mode),
            enable_only_liquid_sports=_bool(
                os.getenv("ENABLE_ONLY_LIQUID_SPORTS"), defaults.enable_only_liquid_sports
            ),
            skip_low_liquidity_markets=_bool(
                os.getenv("SKIP_LOW_LIQUIDITY_MARKETS"), defaults.skip_low_liquidity_markets
            ),
            sport_whitelist=_csv(os.getenv("SPORT_WHITELIST"), defaults.sport_whitelist),
            sport_blacklist=_csv(os.getenv("SPORT_BLACKLIST"), defaults.sport_blacklist),
            team_match_threshold=_int(os.getenv("TEAM_MATCH_THRESHOLD"), defaults.team_match_threshold),
            league_match_threshold=_int(os.getenv("LEAGUE_MATCH_THRESHOLD"), defaults.league_match_threshold),
            max_start_time_diff_minutes=_int(
                os.getenv("MAX_START_TIME_DIFF_MINUTES"), defaults.max_start_time_diff_minutes
            ),
            resend_after_minutes=_int(os.getenv("RESEND_AFTER_MINUTES"), defaults.resend_after_minutes),
            profit_change_threshold_percent=_float(
                os.getenv("PROFIT_CHANGE_THRESHOLD_PERCENT"),
                defaults.profit_change_threshold_percent,
            ),
            fonbet_api_url=os.getenv("FONBET_API_URL", defaults.fonbet_api_url),
            winline_api_url=os.getenv("WINLINE_API_URL", defaults.winline_api_url),
            use_sample_data=_bool(os.getenv("USE_SAMPLE_DATA"), defaults.use_sample_data),
        )
