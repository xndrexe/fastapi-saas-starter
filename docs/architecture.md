# Архитектура

```
┌──────────────┐    HTTP/JSON     ┌─────────────────────────────────┐
│   Клиент     │ ──────────────▶ │       FastAPI / uvicorn         │
│ (браузер,    │                 │  ┌───────────────────────────┐  │
│  curl, SDK)  │ ◀── ответы ──── │  │ PathRateLimitMiddleware   │  │
└──────────────┘                 │  │   (login/register/refresh)│  │
                                 │  └─────────────┬─────────────┘  │
                                 │                ▼                │
                                 │  ┌───────────────────────────┐  │
                                 │  │ api/auth.py  api/users.py │  │
                                 │  │ api/health.py             │  │
                                 │  └─────────────┬─────────────┘  │
                                 │                │                │
                                 │   ┌────────────┴────────────┐   │
                                 │   ▼                         ▼   │
                                 │ ┌─────────────────┐  ┌─────────┐│
                                 │ │ security/       │  │ schemas/││
                                 │ │  jwt.py         │  │ pydantic││
                                 │ │  password.py    │  │ v2      ││
                                 │ │  dependencies.py│  └─────────┘│
                                 │ └────────┬────────┘             │
                                 │          │                      │
                                 │          ▼                      │
                                 │ ┌─────────────────────────────┐ │
                                 │ │ models/  SQLAlchemy 2.x ORM │ │
                                 │ │  User, Role (Mapped[...])   │ │
                                 │ └────────────┬────────────────┘ │
                                 │              │                  │
                                 └──────────────┼──────────────────┘
                                                ▼
                                  ┌─────────────────────────────┐
                                  │ asyncpg ─ Postgres (prod)    │
                                  │ aiosqlite ─ in-memory (dev) │
                                  └─────────────────────────────┘
```

## Слои

- **api/** — роутеры FastAPI. Никакой бизнес-логики в обработчиках:
  только распаковать запрос, дёрнуть нижний слой, упаковать ответ. Все
  ошибки конвертируются в `HTTPException` с generic-сообщением (чтобы
  не помогать перебору).
- **schemas/** — Pydantic v2. Отдельные `*Request` и `*Out` модели,
  чтобы password / password_hash физически не могли утечь наружу
  через сериализацию.
- **security/** —
  - `password.py`: bcrypt с настраиваемым cost (по умолчанию 12).
  - `jwt.py`: чистые функции create/decode, никакой стороннего state.
  - `dependencies.py`: FastAPI-зависимости `get_current_user`,
    `require_role`, `get_db`.
- **models/** — SQLAlchemy 2.x ORM (Mapped). UUID-идентификаторы
  у пользователей: id попадает в URL'ы и токены, монотонной
  последовательности нет.
- **database.py** — фабрика async-engine и sessionmaker. Для SQLite
  in-memory подключаем StaticPool — иначе каждый connect получает
  пустую БД.
- **config.py** — pydantic-settings, префикс `SAAS_`. Один источник
  правды для прод/dev/тестов.
- **main.py** — `create_app(settings, sessionmaker)` фабрика.
  Под тесты подменяется и settings, и sessionmaker — без monkey-patching
  глобального состояния.

## Поток аутентификации

```
1. POST /auth/register {email, password}
   └─▶ bcrypt(password) ─▶ INSERT users
       ◀── 201 + UserOut

2. POST /auth/login {email, password}
   └─▶ SELECT users WHERE email=? ─▶ verify_password
       ─▶ create_access_token + create_refresh_token
       ◀── 200 + {access_token, refresh_token}

3. GET /auth/me  Authorization: Bearer <access>
   └─▶ decode_token ─▶ SELECT users WHERE id=?
       ─▶ проверка is_active + token_version
       ◀── 200 + UserOut

4. POST /auth/refresh {refresh_token}
   └─▶ decode_token (type=refresh) ─▶ SELECT users
       ─▶ проверка token_version
       ─▶ выдача новой пары
       ◀── 200 + {access_token, refresh_token}
```

## Изоляция и инвалидация

- `token_version` на пользователе. При смене пароля (или другом
  событии — отзыв, ротация) счётчик инкрементируется, все ранее выданные
  refresh-токены становятся невалидны на ближайшем `/auth/refresh`.
- `is_active=False` блокирует и login, и любой access по уже выданному
  токену.
- На `/auth/login` сообщение `invalid credentials` одинаковое и при
  неверном пароле, и при неизвестном email, и при отключённом
  пользователе — чтобы не помогать перечислению.

## Что осознанно НЕ сделано

См. одноимённый раздел в `README.md`.
