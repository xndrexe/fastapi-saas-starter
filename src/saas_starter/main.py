"""Фабрика FastAPI-приложения.

Зачем фабрика, а не глобальный ``app``: тестам нужны изолированные
инстансы со своими настройками и БД. Фабрика принимает Settings и
sessionmaker — оба можно подменить в conftest без monkey-patching.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from .api import auth as auth_module
from .api import health as health_module
from .api import users as users_module
from .config import Settings, get_settings
from .database import Base, make_engine, make_sessionmaker
from .security.rate_limit import FixedWindowLimiter, PathRateLimitMiddleware

AUTH_RATE_LIMITED_PATHS = ("/auth/login", "/auth/register", "/auth/refresh")


def create_app(
    settings: Settings | None = None,
    sessionmaker: async_sessionmaker | None = None,
) -> FastAPI:
    """Собрать приложение под конкретные настройки.

    Если ``sessionmaker`` не передан — создаём свой на основе ``settings``.
    Для тестов удобно передавать готовый sessionmaker, заранее засеяв БД.
    """

    settings = settings or get_settings()

    if sessionmaker is None:
        engine = make_engine(settings)
        sessionmaker = make_sessionmaker(engine)

        @asynccontextmanager
        async def _lifespan(app: FastAPI):
            # Авто-создание таблиц для in-memory dev. В проде — alembic.
            if settings.database_url.startswith("sqlite+aiosqlite"):
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            yield
            await engine.dispose()

        lifespan = _lifespan
    else:
        lifespan = None

    app = FastAPI(
        title="fastapi-saas-starter",
        version="0.1.0",
        description="Шаблон SaaS на FastAPI с JWT, RBAC и async SQLAlchemy.",
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.state.settings = settings
    app.state.sessionmaker = sessionmaker

    # Лимитер на auth-эндпоинтах. Per-инстанс, не делится между приложениями.
    # Хранилище в памяти процесса — для prod на нескольких worker'ах
    # подключите Redis-backend.
    limiter = FixedWindowLimiter(
        limit=settings.ratelimit_auth_per_minute,
        window_seconds=60,
    )
    app.state.rate_limiter = limiter
    app.add_middleware(
        PathRateLimitMiddleware,
        limiter=limiter,
        protected_paths=AUTH_RATE_LIMITED_PATHS,
    )

    app.include_router(health_module.router)
    app.include_router(auth_module.router)
    app.include_router(users_module.router)

    return app


# Готовый объект для uvicorn в проде.
app = create_app()
