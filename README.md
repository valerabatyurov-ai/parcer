# Odds Arbitrage Monitor

Локальный Python-проект для мониторинга prematch-коэффициентов букмекеров, поиска арбитражных ситуаций и отправки сигналов в Telegram. Проект работает только в режиме `MODE=monitoring_only`: автоматическое размещение ставок, обход капчи, обход антибот-защиты и работа с приватными API не реализованы намеренно.

## Что реализовано

- Модульная структура из ТЗ: `parsers`, `services`, `storage`, `data`, `logs`.
- MVP-парсеры `FONBET` и `Winline` с единым форматом событий.
- Безопасный источник данных: публичный JSON endpoint из `.env` или локальный sample-режим.
- Whitelist/blacklist видов спорта.
- Нормализация команд и лиг через очистку текста, aliases и fuzzy matching.
- Сопоставление событий между разными букмекерами.
- Сопоставление основных рынков: победа, 1X2, форы, тоталы, индивидуальные тоталы.
- Поиск двухисходных вилок от заданного процента.
- Расчет распределения банка, ожидаемой выплаты и чистой прибыли.
- SQLite-хранилище с таблицами из ТЗ.
- Дедупликация Telegram-уведомлений.
- Логи приложения, ошибок парсеров, сомнительных совпадений и найденных вилок.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка

```bash
copy .env.example .env
```

Заполните:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FONBET_API_URL`
- `WINLINE_API_URL`

`FONBET_API_URL` и `WINLINE_API_URL` должны указывать только на легально доступные публичные JSON-источники без авторизации, обхода защиты или нарушения правил сайта. Если источник возвращает уже нормализованный формат:

```json
{
  "events": [
    {
      "bookmaker": "FONBET",
      "sport": "football",
      "league": "World Cup 2026",
      "home_team": "Team A",
      "away_team": "Team B",
      "start_time": "2026-06-14T19:30:00+05:00",
      "event_url": "https://example.com/event/123",
      "markets": []
    }
  ]
}
```

парсер обработает его без доработок. Для другого JSON нужно адаптировать mapping в `parsers/fonbet.py` или `parsers/winline.py`.

## Запуск

Один проход на sample-данных:

```bash
python main.py --once --sample
```

Один проход на настроенных источниках:

```bash
python main.py --once
```

Постоянный мониторинг раз в `SCAN_INTERVAL_MINUTES`:

```bash
python main.py
```

## Как добавить нового букмекера

1. Создайте файл в `parsers`, например `parsers/betboom.py`.
2. Наследуйтесь от `BaseBookmakerParser`.
3. Реализуйте `fetch_events`, `fetch_event_markets`, `parse`.
4. Возвращайте события в формате `schemas.Event`.
5. Добавьте парсер в список `parsers` в `main.py`.

Ядро сопоставления, поиска вилок, Telegram и SQLite менять не нужно.

## Как добавить алиасы

Откройте `data/aliases.yaml` и добавьте варианты:

```yaml
teams:
  canonical team:
    - alias one
    - alias two
```

После этого normalizer будет приводить alias к canonical name до fuzzy matching.

## Как изменить параметры вилки и банка

В `.env`:

```env
MIN_PROFIT_PERCENT=5
BANKROLL_RUB=10000
```

## Как изменить whitelist/blacklist спорта

В `.env`:

```env
SPORT_WHITELIST=football,hockey,basketball,tennis,volleyball,mma,boxing,cs,dota2,lol,valorant
SPORT_BLACKLIST=chess,virtual_sport,cyberfootball,cyberbasketball,table_tennis_low_tier,unknown_low_liquidity_sports
```

Если `ENABLE_ONLY_LIQUID_SPORTS=true`, события вне whitelist пропускаются.

## Логи

- `logs/app.log` — общий ход мониторинга.
- `logs/parser_errors.log` — ошибки парсеров и Telegram.
- `logs/unmatched_events.log` — сомнительные совпадения.
- `logs/arbitrage.log` — найденные вилки.

## Ограничения MVP

- Реальное получение данных зависит от доступного публичного источника для каждого букмекера.
- Закрытые API, приватные аккаунтные данные, агрессивный скрейпинг, обход капчи и антибота не используются.
- Поиск вилок реализован для двухисходных сравнений, что покрывает П1/П2, форы и тоталы. Для полноценного 1X2 с ничьей потребуется расширить модель уведомления и хранения до трех исходов.
