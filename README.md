# 🔭 Async Content Scraper — универсальный монитор сайтов и Telegram-каналов

Асинхронный сервис на Python для непрерывного (24/7) мониторинга публичных
веб-сайтов и Telegram-каналов: находит новые публикации, дедуплицирует их на
уровне БД и присылает дайджест в Telegram. Спроектирован как
production-сервис, а не как одноразовый скрипт: graceful shutdown,
backoff при сбоях источника, health-мониторинг, systemd/Docker-деплой.

<p>
  <a href="https://github.com/sonoyumi/async-content-scraper/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/sonoyumi/async-content-scraper/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Async" src="https://img.shields.io/badge/asyncio-native-informational">
  <img alt="Code style" src="https://img.shields.io/badge/lint-ruff-blueviolet">
  <img alt="Typed" src="https://img.shields.io/badge/mypy-checked-blue">
  <img alt="Tests" src="https://img.shields.io/badge/tests-pytest-yellow">
</p>

> **⚠️ Дисклеймер.** Этот репозиторий является демонстрацией архитектурных
> навыков. Уникальные алгоритмы парсинга удалены в целях защиты ИС — см.
> раздел [«Что показано, а что нет»](#-что-показано-а-что-нет) ниже.

---

## Что делает сервис

- **Сайты** — HTTP-фетч + BeautifulSoup с конфигурируемыми CSS-селекторами
  (без единой строчки Python на новый источник — всё через YAML/CLI), либо
  headless Chromium через Playwright для JS-тяжёлых/infinite-scroll страниц.
- **Публичные Telegram-каналы** — без токенов и логина, только открытые
  данные (в публичной сборке эта часть — задокументированная заглушка, см.
  дисклеймер).
- **Хранение** — SQLAlchemy 2.0, SQLite для разработки, PostgreSQL для прода
  (одни и те же модели работают с обоими).
- **Дедупликация** — на уровне UNIQUE-constraint'ов в БД
  (`ON CONFLICT DO NOTHING ... RETURNING id`), а не через
  проверил-потом-вставил — устраняет гонки между конкурентными циклами.
- **Уведомления** — дайджест новых постов в Telegram, с корректной
  обработкой rate-limit (HTTP 429) и разбивкой длинных дайджестов на части.

## Архитектура

```
scheduler (AsyncIOScheduler, 1 job/источник)
        │
        ▼
   poller.poll_source  ──►  Fetcher (HTTP / Playwright)
        │                          │
        │                          ▼
        │                    Extractor (BS4-парсинг по CSS-селекторам)
        │                          │
        ▼                          ▼
   backoff при сбоях        Storage (SQLAlchemy + UNIQUE constraint dedup)
        │                          │
        ▼                          ▼
   heartbeat + healthcheck   Notifier (Telegram Bot API, дайджест)
```

Каждый компонент — за абстрактным базовым классом (`Fetcher`, `Extractor`),
поэтому добавление нового типа источника не требует правки остального кода.

## Инженерные решения, которые здесь стоит посмотреть

- **`asyncio.Semaphore` + per-domain `AsyncLimiter`** — конкурентность
  ограничена глобально *и* по каждому домену отдельно, чтобы несколько
  источников на одном хосте не создавали эффект DDoS даже случайно
  (`scheduler/queue.py`).
- **Sync SQLAlchemy без блокировки event loop** — БД-операции вынесены в
  `asyncio.to_thread`, чтобы не блокировать конкурентные fetch'и других
  источников на время запроса к БД (`poller.py`).
- **Сетевой I/O никогда не держит открытой транзакцию БД** — загрузка медиа
  и отправка уведомлений выполняются вне сессии, результат сохраняется
  отдельной короткой транзакцией после (см. `_download_pending_media`,
  `_notify_new_posts`).
- **Graceful shutdown по SIGTERM** — не только SIGINT: планировщик и общий
  экземпляр headless-браузера корректно закрываются при `systemctl stop`/
  `docker stop`, а не просто убиваются по таймауту (`scheduler/runner.py`).
- **Backoff при повторяющихся ошибках** — источник, который стабильно
  падает (например, после редизайна сайта), опрашивается всё реже, а не
  долбится с тем же интервалом бесконечно.
- **Heartbeat-based healthcheck** — отдельный сигнал "event loop реально
  отвечает", а не просто "процесс жив по PID" (`deploy/healthcheck.sh`,
  подключён и в Docker `HEALTHCHECK`, и в systemd-таймер).

## Стек

`Python 3.11+` · `asyncio` · `httpx` · `BeautifulSoup4` · `Playwright` ·
`SQLAlchemy 2.0` + `Alembic` · `PostgreSQL` / `SQLite` · `APScheduler` ·
`Pydantic v2` + `pydantic-settings` · `tenacity` · `aiolimiter` ·
`structlog` · `Typer` + `Rich` · `pytest` + `pytest-asyncio` + `respx` ·
`ruff` + `mypy`

## Быстрый старт

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
./.venv/bin/scraper init-db
cp config/sources.example.yaml config/sources.yaml   # включи нужные источники
./.venv/bin/scraper seed --config-file config/sources.yaml
./.venv/bin/scraper test-source --config-file config/sources.yaml --name "Example: static news site"
./.venv/bin/pytest -q
```

CI (`.github/workflows/ci.yml`) на каждый push гоняет `ruff check`, `mypy` и
`pytest`.

## Деплой

- `docker compose -f docker/docker-compose.yml up --build -d` — Postgres +
  сервис, с healthcheck'ом из коробки.
- Systemd-юнит для bare-metal-деплоя — `deploy/scraper.service` +
  `deploy/healthcheck.sh` (hardening: `ProtectSystem=strict`,
  `NoNewPrivileges`, лимиты памяти, graceful restart-policy).

## Что показано, а что нет

Публичная версия целиком демонстрирует архитектуру: конкурентность,
работу с БД, дедупликацию, отказоустойчивость, деплой. **Не включена**
рабочая реализация парсинга разметки Telegram-канала
(`extractors/telegram_extractor.py` — задокументированная заглушка,
поднимает `NotImplementedError` с пояснением) — это единственная часть,
которая в приватной версии содержит конкретную, наработанную логику,
пригодную для прямого коммерческого использования без доработки. Всё
остальное — HTML-экстрактор, планировщик, дедупликация, деплой-конфигурация
— работает так же, как в продакшен-версии.

## Автор

**Vladyslav Shokun** ([@sonoyumi](https://github.com/sonoyumi)) — Python-разработчик:
Telegram-боты, парсинг, асинхронные сервисы.

[![Telegram](https://img.shields.io/badge/Telegram-write%20me-2CA5E0?logo=telegram&logoColor=white)](https://t.me/sonoyumiii)
[![Email](https://img.shields.io/badge/Email-contact-EA4335?logo=gmail&logoColor=white)](mailto:sonoyumiii@gmail.com)

> 💼 Нужен мониторинг сайтов, парсер или бот под вашу задачу? Напишите мне.

## Лицензия

MIT — см. [LICENSE](LICENSE).
