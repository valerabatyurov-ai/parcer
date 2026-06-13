from __future__ import annotations

import sys

from loguru import logger

from config import LOG_DIR


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(LOG_DIR / "app.log", rotation="5 MB", retention=10, level="INFO")
    logger.add(LOG_DIR / "parser_errors.log", rotation="2 MB", retention=10, level="WARNING")
    logger.add(LOG_DIR / "unmatched_events.log", rotation="2 MB", retention=10, level="INFO", filter=_unmatched_filter)
    logger.add(LOG_DIR / "arbitrage.log", rotation="2 MB", retention=10, level="INFO", filter=_arbitrage_filter)


def _unmatched_filter(record: dict) -> bool:
    return record["extra"].get("channel") == "unmatched"


def _arbitrage_filter(record: dict) -> bool:
    return record["extra"].get("channel") == "arbitrage"
