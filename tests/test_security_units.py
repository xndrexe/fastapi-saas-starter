"""Unit-тесты криптомодулей: bcrypt и JWT."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from saas_starter.security.jwt import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from saas_starter.security.password import hash_password, verify_password

SECRET = "unit-test-secret-32-chars-minimum-please-ok-12345"


def test_bcrypt_hash_and_verify_round_trip() -> None:
    h = hash_password("correct-horse-battery", rounds=4)
    assert h != "correct-horse-battery"
    assert verify_password("correct-horse-battery", h)
    assert not verify_password("wrong", h)


def test_bcrypt_different_salts() -> None:
    h1 = hash_password("same", rounds=4)
    h2 = hash_password("same", rounds=4)
    # bcrypt сам подмешивает соль — два хэша одного пароля разные.
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_bcrypt_empty_password_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("", rounds=4)
    assert verify_password("", "$2b$04$broken") is False
    assert verify_password("anything", "") is False


def test_bcrypt_cost_12_actually_used() -> None:
    # Проверяем, что cost=12 действительно применился: хэш bcrypt
    # хранит cost в формате $2b$12$...
    h = hash_password("check-cost", rounds=12)
    parts = h.split("$")
    assert parts[1] in ("2a", "2b", "2y")
    assert parts[2] == "12"


def test_jwt_round_trip_access() -> None:
    token = create_access_token(
        sub="user-1",
        role="user",
        token_version=0,
        secret=SECRET,
        lifetime_min=5,
    )
    payload = decode_token(token, secret=SECRET)
    assert payload.sub == "user-1"
    assert payload.role == "user"
    assert payload.token_type == "access"
    assert payload.token_version == 0


def test_jwt_round_trip_refresh() -> None:
    token = create_refresh_token(
        sub="user-2",
        role="admin",
        token_version=7,
        secret=SECRET,
        lifetime_days=1,
    )
    payload = decode_token(token, secret=SECRET)
    assert payload.token_type == "refresh"
    assert payload.token_version == 7


def test_jwt_expired_raises() -> None:
    past = datetime.now(UTC) - timedelta(minutes=5)
    raw = {
        "sub": "u",
        "role": "user",
        "type": "access",
        "ver": 0,
        "iat": int((past - timedelta(minutes=1)).timestamp()),
        "exp": int(past.timestamp()),
    }
    expired = jwt.encode(raw, SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_token(expired, secret=SECRET)


def test_jwt_wrong_secret_raises() -> None:
    token = create_access_token(
        sub="u",
        role="user",
        token_version=0,
        secret=SECRET,
        lifetime_min=5,
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token, secret="another-secret-32-chars-minimum-required-ok!")


def test_jwt_garbage_raises() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.jwt", secret=SECRET)


def test_jwt_iat_in_past() -> None:
    # iat должен быть раньше exp; проверяем что свежий токен живёт.
    before = time.time()
    token = create_access_token(
        sub="u",
        role="user",
        token_version=0,
        secret=SECRET,
        lifetime_min=10,
    )
    payload = decode_token(token, secret=SECRET)
    assert payload.iat.timestamp() >= before - 1
    assert payload.exp > payload.iat
