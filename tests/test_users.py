"""Тесты эндпоинтов /users."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from saas_starter.models import User
from tests.conftest import login_and_get_tokens


@pytest.mark.asyncio
async def test_patch_me_changes_email(client: AsyncClient, test_user: User) -> None:
    tokens = await login_and_get_tokens(client, test_user.email, "password123")
    response = await client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"email": "renamed@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "renamed@example.com"


@pytest.mark.asyncio
async def test_patch_me_requires_auth(client: AsyncClient) -> None:
    response = await client.patch("/users/me", json={"email": "x@y.z"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_user_as_admin(
    client: AsyncClient,
    test_user: User,
    test_admin: User,
) -> None:
    tokens = await login_and_get_tokens(client, test_admin.email, "adminpass123")
    response = await client.get(
        f"/users/{test_user.id}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email


@pytest.mark.asyncio
async def test_get_user_as_user_forbidden(
    client: AsyncClient,
    test_user: User,
    test_admin: User,
) -> None:
    tokens = await login_and_get_tokens(client, test_user.email, "password123")
    response = await client.get(
        f"/users/{test_admin.id}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_unknown_user_admin(client: AsyncClient, test_admin: User) -> None:
    tokens = await login_and_get_tokens(client, test_admin.email, "adminpass123")
    response = await client.get(
        "/users/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
