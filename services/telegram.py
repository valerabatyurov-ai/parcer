from __future__ import annotations

import hashlib
import json
from datetime import datetime

import httpx

from config import Settings
from schemas import ArbitrageOpportunity, ParserError
from utils.logging import logger


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    async def send_arbitrage(self, opportunity: ArbitrageOpportunity) -> int | None:
        return await self._send(self.format_arbitrage(opportunity))

    async def send_parser_error(self, error: ParserError) -> int | None:
        now = datetime.now(self.settings.timezone).strftime(
            f"{self.settings.date_format}, %H:%M {self.settings.timezone_name}"
        )
        message = (
            f"⚠️ Ошибка парсинга {error.bookmaker}\n"
            f"Причина: {error.message}\n"
            f"Время: {now}\n"
            f"Страница: {error.url or '-'}"
        )
        return await self._send(message)

    async def _send(self, text: str) -> int | None:
        if not self.enabled:
            logger.info("Telegram is not configured; notification skipped")
            return None

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("result", {}).get("message_id")
        except Exception as exc:  # noqa: BLE001 - log and continue monitoring
            logger.warning("Telegram API error: {}", exc)
            return None

    def format_arbitrage(self, opportunity: ArbitrageOpportunity) -> str:
        event_start = opportunity.event_start_time
        if event_start.tzinfo is None:
            event_start = event_start.replace(tzinfo=self.settings.timezone)
        event_time = event_start.astimezone(self.settings.timezone).strftime(
            f"{self.settings.date_format}, %H:%M {self.settings.timezone_name}"
        )
        return (
            f"🔥 Найдена вилка: {opportunity.profit_percent:.2f}%\n"
            f"Событие: {opportunity.event_name}\n"
            f"Спорт: {opportunity.sport}\n"
            f"Турнир: {opportunity.league}\n"
            f"Дата: {event_time}\n"
            f"Рынок: {opportunity.market_name}\n"
            f"БК 1: {opportunity.bookmaker_1}\n"
            f"Исход: {opportunity.outcome_1}\n"
            f"Коэффициент: {opportunity.odds_1:.2f}\n"
            f"БК 2: {opportunity.bookmaker_2}\n"
            f"Исход: {opportunity.outcome_2}\n"
            f"Коэффициент: {opportunity.odds_2:.2f}\n"
            f"Банк: {self._money(opportunity.bankroll_rub)} ₽\n"
            f"Рекомендуемое распределение:\n"
            f"Ставка 1: {self._money(opportunity.stake_1)} ₽\n"
            f"Ставка 2: {self._money(opportunity.stake_2)} ₽\n"
            f"Ожидаемая выплата: {self._money(opportunity.expected_payout)} ₽\n"
            f"Чистая прибыль: {self._money(opportunity.profit_rub)} ₽\n"
            f"Ссылка {opportunity.bookmaker_1}: {opportunity.event_url_1 or '-'}\n"
            f"Ссылка {opportunity.bookmaker_2}: {opportunity.event_url_2 or '-'}"
        )

    @staticmethod
    def _money(value: float) -> str:
        return f"{value:,.0f}".replace(",", " ")

    @staticmethod
    def arbitrage_hash(opportunity: ArbitrageOpportunity) -> str:
        payload = {
            "event_key": opportunity.event_key,
            "market_type": opportunity.market_type,
            "line": opportunity.line,
            "bookmaker_1": opportunity.bookmaker_1,
            "bookmaker_2": opportunity.bookmaker_2,
            "odds_1": round(opportunity.odds_1, 4),
            "odds_2": round(opportunity.odds_2, 4),
            "profit_percent": round(opportunity.profit_percent, 2),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
