"""Асинхронный слой БД: фабрика engine, dependency для session.

Отдельная Base здесь, а не в models/, чтобы не плодить циклические импорты
между моделями и движком.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import Settings


class Base(DeclarativeBase):
    """Общая декларативная база для всех ORM-моделей."""


def make_engine(settings: Settings) -> AsyncEngine:
    """Создать async engine под выбранный DSN.

    Для SQLite-in-memory нужны особые параметры: один и тот же connection
    переиспользуется через StaticPool, иначе каждое подключение получает
    свежую пустую базу.
    """

    url = settings.database_url
    if url.startswith("sqlite+aiosqlite"):
        from sqlalchemy.pool import StaticPool

        connect_args = {"check_same_thread": False}
        return create_async_engine(
            url,
            connect_args=connect_args,
            poolclass=StaticPool,
            echo=settings.debug,
        )

    return create_async_engine(url, echo=settings.debug, pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Фабрика session, привязанная к конкретному engine."""

    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session_dependency(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Превращает sessionmaker в FastAPI-dependency.

    Зачем не глобальный sessionmaker: при тестах удобно поднять отдельный
    engine на in-memory SQLite и подменить эту зависимость.
    """

    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
