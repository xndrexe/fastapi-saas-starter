"""Тест ограничения частоты на /auth/login."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saas_starter.config import Settings
from saas_starter.main import create_app
from saas_starter.models import User
from tests.conftest import TEST_BCRYPT_ROUNDS, TEST_JWT_SECRET


@pytest.fixture
def low_rate_settings() -> Settings:
    """Жёсткий лимит для теста — 3 попытки на минуту."""

    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret=TEST_JWT_SECRET,
        jwt_algorithm="HS256",
        access_token_lifetime_min=30,
        refresh_token_lifetime_days=14,
        ratelimit_auth_per_minute=3,
        bcrypt_rounds=TEST_BCRYPT_ROUNDS,
    )


@pytest_asyncio.fixture
async def low_rate_client(
    low_rate_settings: Settings,
    sessionmaker_fx: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """Клиент с жёстким лимитом, общая фабрика БД с остальными фикстурами."""

    app = create_app(settings=low_rate_settings, sessionmaker=sessionmaker_fx)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_login_rate_limited(low_rate_client: AsyncClient, test_user: User) -> None:
    """После N попыток подряд /login должен вернуть 429."""

    # Шлём заведомо неверные пароли, чтобы не зависеть от bcrypt-времени
    # и точно остаться в окне.
    statuses: list[int] = []
    for _ in range(6):
        r = await low_rate_client.post(
            "/auth/login",
            json={"email": test_user.email, "password": "wrong-on-purpose"},
        )
        statuses.append(r.status_code)

    # Минимум одна попытка должна упереться в 429.
    assert 429 in statuses, f"ожидали 429 хотя бы один раз, получили {statuses}"
    # Первые попытки до исчерпания лимита должны быть 401 (неверный пароль).
    assert statuses[0] == 401
