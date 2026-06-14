# fastapi-saas-starter

[![CI](https://github.com/xndrexe/fastapi-saas-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/xndrexe/fastapi-saas-starter/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Готовый шаблон SaaS-бэкенда на FastAPI: JWT-аутентификация (access + refresh),
RBAC с двумя ролями, асинхронная SQLAlchemy 2.x, alembic-миграции с seed
ролей, ограничение частоты на auth-эндпоинтах через собственный
in-memory лимитер (~40 строк, без внешних зависимостей), bcrypt
с cost factor 12.

Поднимается одной командой `docker compose up`. Тесты на in-memory SQLite,
прод — на Postgres через asyncpg. Чистая архитектура, MIT-лицензия.

## Что умеет

- `POST /auth/register` — регистрация (роль `user` по умолчанию).
- `POST /auth/login` — выдача пары access/refresh.
- `POST /auth/refresh` — обмен refresh-токена на новую пару.
- `GET /auth/me` — профиль текущего пользователя.
- `PATCH /users/me` — изменить собственный email.
- `GET /users/{id}` — чужой профиль (только админ).
- `GET /health` — liveness-проба.

Защиты:

- bcrypt cost 12 для паролей.
- JWT HS256, отдельные lifetime для access (30 мин) и refresh (14 дней).
- Версионирование токенов через `token_version` — смена пароля
  инвалидирует все ранее выданные refresh.
- Generic-сообщения об ошибках на login (без подсказок «такого email нет»).
- Свой in-memory rate-limit на login/register/refresh (по умолчанию 5/мин на IP).
  Реализован как `FixedWindowLimiter + PathRateLimitMiddleware` в
  `security/rate_limit.py` — fixed window на deque, без внешних зависимостей.

## Запуск

### Через Docker

```bash
cp .env.example .env
# отредактировать .env: SAAS_JWT_SECRET минимум 32 символа
docker compose up -d
# применить миграции (в первый раз):
docker compose exec app alembic upgrade head
curl http://localhost:8000/health
```

### Локально

```bash
python -m venv .venv
.venv/Scripts/activate                 # Windows
# source .venv/bin/activate             # Linux/Mac
pip install -e ".[dev]"
cp .env.example .env
# править .env
alembic upgrade head                   # если используете Postgres
saas-starter                           # или: python -m saas_starter
```

В dev-режиме без `.env` пакет поднимется на in-memory SQLite — таблицы
создаются автоматически при старте, ролей сидится две (`user`, `admin`).

## Тесты

```bash
pytest -q
ruff check src/ tests/
```

Покрытие (20+ тестов):

- `test_auth.py` — happy-path регистрации/логина/refresh/me, дубль email,
  неверный пароль, неизвестный email, отключённый пользователь, expired
  refresh, refresh с access-типом, доступ к /me без токена и с битым.
- `test_users.py` — PATCH /users/me, RBAC на /users/{id}, 404 на чужой id,
  health-эндпоинт.
- `test_rate_limit.py` — login на жёстком лимите упирается в 429.
- `test_security_units.py` — bcrypt round-trip, разные соли, cost=12
  действительно применился, JWT round-trip access/refresh, expired,
  чужой секрет, мусор на входе, iat в прошлом.

Никаких сетевых вызовов: httpx через ASGITransport, БД в памяти. Весь
прогон укладывается в ~3 секунды.

## Стек

- Python 3.11+
- FastAPI 0.110+ / uvicorn
- SQLAlchemy 2.x async (asyncpg для prod, aiosqlite для dev/tests)
- alembic 1.13
- pydantic v2 + pydantic-settings
- python-jose (JWT)
- passlib[bcrypt]
- pytest + pytest-asyncio + httpx

Никаких C++-зависимостей с тяжёлой компиляцией: всё ставится на чистом
Windows без VS Build Tools, на Alpine без `build-base`.

## Архитектура

См. [docs/architecture.md](docs/architecture.md).

## Security checklist

Перед выкатом в прод пройти по списку. Шаблон закрывает базу, остальное —
зона ответственности оператора.

- [ ] `SAAS_JWT_SECRET` — не дефолтный, минимум 32 байта из криптослучайного
      источника (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- [ ] Postgres-логин/пароль из `.env`, не дефолтные `saas:saas`.
- [ ] `.env` в `.gitignore`, секреты не в репозитории и не в Dockerfile.
- [ ] TLS на reverse-proxy (nginx / Caddy / Traefik), приложение не
      слушает 0.0.0.0 наружу напрямую.
- [ ] За прокси — настроен `--forwarded-allow-ips` у uvicorn, и
      `_default_key` в `security/rate_limit.py` поменян на чтение
      `X-Forwarded-For`. Иначе все запросы будут считаться с одного IP прокси.
- [ ] `ratelimit_auth_per_minute` подобран под реальный трафик — 5/мин
      это компромисс по умолчанию, не догма.
- [ ] bcrypt rounds оставлены 12 (или выше — но тогда замерить латенси
      на железе). 10 и ниже — слишком слабо для 2026 года.
- [ ] Refresh-токены не хранятся в localStorage — только httpOnly cookie
      или secure storage клиента. Шаблон сейчас отдаёт их в body —
      это удобно для SDK, для браузерного фронта поменять на cookie.
- [ ] Бэкап Postgres настроен.
- [ ] Логи приложения не содержат токены и пароли (по умолчанию uvicorn
      не пишет тела запросов — не включать `--log-level debug` в проде).
- [ ] Алерт на серию 401/429 — детектор перебора.

## Что осознанно НЕ сделано

- **Refresh-token rotation с отзывом конкретного токена.** Сейчас
  отзыв — это инкремент `token_version` (рубит все refresh пользователя).
  Перcистентная таблица `refresh_tokens` с `jti` и blacklist — следующий
  логичный шаг, но это усложняет шаблон. Для большинства SaaS на старте
  достаточно того, что есть.
- **OAuth/SSO/magic-link.** Только классический email+password.
  Добавление Google/GitHub OAuth — отдельный модуль `api/oauth.py`,
  трогать ядро не нужно.
- **Сброс пароля по email.** Нет интеграции с SMTP/SES. Эндпоинт
  `POST /auth/password-reset` с одноразовым токеном — следующий шаг,
  но требует выбора почтового провайдера и шаблонов писем.
- **CSRF.** Шаблон под токен в заголовке (SPA / mobile), не cookie.
  Если переходите на cookie-сессии — добавить SameSite + CSRF-токены.
- **Логирование структурированное.** Нет structlog/loguru — uvicorn
  пишет в stdout, прод-логирование собирается на инфраструктурном
  уровне (Loki, CloudWatch).
- **Метрики Prometheus.** `/metrics` нет. Стартеру не нужен — добавляется
  `prometheus-fastapi-instrumentator` за 10 строк.
- **API-versioning через префикс /v1.** Сейчас плоско, без префикса.
  Когда появится v2 — менять схему URL'ов осознанно.
- **Сложная иерархия ролей.** Только `user` и `admin`. Многоуровневые
  permissions/scopes — отдельная подсистема, не для стартера.
- **Email verification flow.** Регистрация сразу даёт активного
  пользователя. Для прода добавить `is_email_verified` + одноразовый
  токен подтверждения.
- **WebSocket / SSE.** Только REST.
- **CI/CD pipeline.** Нет `.github/workflows/`. Шаблон фокусируется
  на коде, CI каждый настраивает под свою экосистему.

## Лицензия

MIT.

## Контекст

Это публичная демонстрация моего стека для FastAPI / async-SQLAlchemy /
JWT-аутентификации. Боевые системы (мультитенант на десятки тысяч активных
пользователей, OAuth с собственным IdP, rate-limit на распределённом
Redis, аудит и мониторинг безопасности) идут под NDA — архитектуру
разберу на созвоне по запросу.

Контакт: [skostuhov@gmail.com](mailto:skostuhov@gmail.com) /
[GitHub @xndrexe](https://github.com/xndrexe).
