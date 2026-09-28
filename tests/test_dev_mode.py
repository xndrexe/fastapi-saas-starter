"""Режим разработки: приложение само создаёт таблицы и роли в SQLite."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from saas_starter.config import Settings
from saas_starter.main import create_app


async def test_dev_sqlite_register_works_without_migrations() -> None:
    """README обещает: без .env и alembic регистрация работает сразу."""
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret="test-secret-32-chars-minimum-for-pydantic-validator-ok!",
        bcrypt_rounds=4,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/auth/register",
                json={"email": "new@example.com", "password": "Str0ng-pass-123"},
            )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "user"
