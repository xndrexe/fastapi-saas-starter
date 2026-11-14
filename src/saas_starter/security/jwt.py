"""JWT: создание и проверка access/refresh-токенов.

Один секрет на access и refresh — упрощение шаблона. В проде стоит
разнести: refresh-секрет крутить реже, access-секрет ротейтить с overlap.

Содержимое payload минимальное: sub (user_id), role, type (access/refresh),
exp, iat. Никакого email — он меняется, а токен короткоживущий.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt

TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class TokenPayload:
    """Распакованное содержимое токена в удобной форме."""

    sub: str
    role: str
    token_type: TokenType
    token_version: int
    exp: datetime
    iat: datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _create(
    *,
    sub: str,
    role: str,
    token_type: TokenType,
    token_version: int,
    secret: str,
    algorithm: str,
    lifetime: timedelta,
) -> str:
    now = _utcnow()
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "type": token_type,
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_access_token(
    *,
    sub: str,
    role: str,
    token_version: int,
    secret: str,
    algorithm: str = "HS256",
    lifetime_min: int = 30,
) -> str:
    """Короткоживущий токен для доступа к API."""

    return _create(
        sub=sub,
        role=role,
        token_type="access",
        token_version=token_version,
        secret=secret,
        algorithm=algorithm,
        lifetime=timedelta(minutes=lifetime_min),
    )


def create_refresh_token(
    *,
    sub: str,
    role: str,
    token_version: int,
    secret: str,
    algorithm: str = "HS256",
    lifetime_days: int = 14,
) -> str:
    """Долгоживущий токен только для обмена на новую пару."""

    return _create(
        sub=sub,
        role=role,
        token_type="refresh",
        token_version=token_version,
        secret=secret,
        algorithm=algorithm,
        lifetime=timedelta(days=lifetime_days),
    )


class InvalidTokenError(Exception):
    """Токен не валиден: подпись битая, истёк, не той схемы."""


def decode_token(token: str, *, secret: str, algorithm: str = "HS256") -> TokenPayload:
    """Распаковать и проверить токен.

    Любая внутренняя ошибка python-jose превращается в InvalidTokenError —
    наружу не выдаём детали (это безопасность, не диагностика).
    """

    try:
        raw = jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    try:
        sub = str(raw["sub"])
        role = str(raw["role"])
        token_type = raw["type"]
        token_version = int(raw.get("ver", 0))
        exp = datetime.fromtimestamp(int(raw["exp"]), tz=UTC)
        iat = datetime.fromtimestamp(int(raw["iat"]), tz=UTC)
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError(f"malformed payload: {exc}") from exc

    if token_type not in ("access", "refresh"):
        raise InvalidTokenError("unknown token type")

    return TokenPayload(
        sub=sub,
        role=role,
        token_type=token_type,
        token_version=token_version,
        exp=exp,
        iat=iat,
    )
