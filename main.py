from __future__ import annotations

import argparse
import asyncio

from config import Settings
from parsers.fonbet import FonbetParser
from parsers.winline import WinlineParser
from services.scheduler import MonitoringApp
from storage.db import Database
from utils.logging import configure_logging, logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local odds arbitrage monitor")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--sample", action="store_true", help="Use bundled sample data instead of HTTP sources")
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    if args.sample:
        settings.use_sample_data = True

    configure_logging()
    if settings.mode != "monitoring_only":
        raise RuntimeError("Only MODE=monitoring_only is supported. Automatic betting is intentionally absent.")

    db = Database(settings)
    await db.init()

    parsers = [
        FonbetParser(settings),
        WinlineParser(settings),
    ]

    app = MonitoringApp(settings=settings, db=db, parsers=parsers)
    if args.once:
        await app.scan_once()
        await db.close()
        return

    await app.run_forever()


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")


if __name__ == "__main__":
    main()
