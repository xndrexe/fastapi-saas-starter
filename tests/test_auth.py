"""Тесты аутентификации: регистрация, логин, refresh, /me."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from saas_starter.config import Settings
from saas_starter.models import User
from tests.conftest import login_and_get_tokens


@pytest.mark.asyncio
async def test_register_happy_path(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "Strong-Pass-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user: User) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": test_user.email, "password": "Different-Pass-2"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "email already registered"


@pytest.mark.asyncio
async def test_register_short_password_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "1234567"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: User) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "any-password"},
    )
    # Сообщение такое же, как и при неверном пароле — не помогаем перебору.
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


@pytest.mark.asyncio
async def test_login_disabled_user(
    client: AsyncClient,
    test_user: User,
    sessionmaker_fx,
) -> None:
    async with sessionmaker_fx() as session:
        db_user = await session.get(User, test_user.id)
        db_user.is_active = False
        await session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "password123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_valid(client: AsyncClient, test_user: User) -> None:
    tokens = await login_and_get_tokens(client, test_user.email, "password123")
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    new_pair = response.json()
    assert new_pair["access_token"]
    assert new_pair["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_expired(
    client: AsyncClient,
    test_user: User,
    settings: Settings,
) -> None:
    # Подделываем уже-просроченный refresh: алгоритм и секрет настоящие,
    # но exp в прошлом.
    past = datetime.now(UTC) - timedelta(days=1)
    payload = {
        "sub": test_user.id,
        "role": "user",
        "type": "refresh",
        "ver": 0,
        "iat": int((past - timedelta(minutes=5)).timestamp()),
        "exp": int(past.timestamp()),
    }
    expired = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    response = await client.post("/auth/refresh", json={"refresh_token": expired})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_wrong_type(client: AsyncClient, test_user: User) -> None:
    # access-токен нельзя слать в /refresh.
    tokens = await login_and_get_tokens(client, test_user.email, "password123")
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient, test_user: User) -> None:
    tokens = await login_and_get_tokens(client, test_user.email, "password123")
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email


@pytest.mark.asyncio
async def test_me_with_malformed_token(client: AsyncClient) -> None:
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 401
