"""Общие фикстуры тестов.

Принципы:
- in-memory SQLite через aiosqlite, без реальной сети;
- bcrypt cost=4 в тестах — иначе каждый login отъедает ~150 мс;
- свежий engine на каждый тест → полная изоляция и отсутствие
  кэширования между прогонами;
- AsyncClient через ASGITransport — никакого uvicorn/портов.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saas_starter.config import Settings
from saas_starter.database import Base, make_engine, make_sessionmaker
from saas_starter.main import create_app
from saas_starter.models import Role, RoleName, User
from saas_starter.security import hash_password

TEST_BCRYPT_ROUNDS = 4
TEST_JWT_SECRET = "test-secret-32-chars-minimum-for-pydantic-validator-ok!"


@pytest.fixture
def settings() -> Settings:
    """Тестовые настройки. Дёшево по bcrypt, лимиты крупные."""

    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret=TEST_JWT_SECRET,
        jwt_algorithm="HS256",
        access_token_lifetime_min=30,
        refresh_token_lifetime_days=14,
        ratelimit_auth_per_minute=1000,
        bcrypt_rounds=TEST_BCRYPT_ROUNDS,
    )


@pytest_asyncio.fixture
async def sessionmaker_fx(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Свежий engine + засеянные роли."""

    engine = make_engine(settings)
    sm = make_sessionmaker(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed двух ролей — без миграции, чтобы не тащить alembic в каждый тест.
    async with sm() as session:
        session.add_all(
            [
                Role(id=1, name=RoleName.USER, description="user"),
                Role(id=2, name=RoleName.ADMIN, description="admin"),
            ]
        )
        await session.commit()

    yield sm
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(
    sessionmaker_fx: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Готовая открытая сессия для тестов с прямым доступом к БД."""

    async with sessionmaker_fx() as session:
        yield session


@pytest_asyncio.fixture
async def app(
    settings: Settings,
    sessionmaker_fx: async_sessionmaker[AsyncSession],
):
    """FastAPI-приложение с подменённой фабрикой сессий."""

    return create_app(settings=settings, sessionmaker=sessionmaker_fx)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    """httpx-клиент поверх ASGITransport — без сети."""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user(
    sessionmaker_fx: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> User:
    """Готовый пользователь с ролью ``user`` и известным паролем."""

    async with sessionmaker_fx() as session:
        user = User(
            email="user@example.com",
            password_hash=hash_password("password123", rounds=settings.bcrypt_rounds),
            role_id=1,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user, attribute_names=["role"])
        return user


@pytest_asyncio.fixture
async def test_admin(
    sessionmaker_fx: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> User:
    """Готовый администратор."""

    async with sessionmaker_fx() as session:
        admin = User(
            email="admin@example.com",
            password_hash=hash_password("adminpass123", rounds=settings.bcrypt_rounds),
            role_id=2,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin, attribute_names=["role"])
        return admin


async def login_and_get_tokens(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Хелпер: логин и возврат пары access/refresh."""

    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()
