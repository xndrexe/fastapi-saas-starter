"""Эндпоинты аутентификации.

Под limiter завёрнуты register/login/refresh — чтобы перебор пароля и
spam-регистрация упирались в 429 после ``ratelimit_auth_per_minute`` в минуту.

Сообщения об ошибках намеренно generic: «invalid credentials» вместо
«пользователь не найден» / «пароль не совпал» — иначе можно перечислить
зарегистрированные email.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import Settings
from ..models import Role, RoleName, User
from ..schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserOut
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..security.dependencies import get_current_user, get_db
from ..security.jwt import InvalidTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def _issue_pair(user: User, settings: Settings) -> TokenPair:
    """Сформировать пару токенов под текущее состояние пользователя."""

    access = create_access_token(
        sub=user.id,
        role=user.role.name.value,
        token_version=user.token_version,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        lifetime_min=settings.access_token_lifetime_min,
    )
    refresh = create_refresh_token(
        sub=user.id,
        role=user.role.name.value,
        token_version=user.token_version,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        lifetime_days=settings.refresh_token_lifetime_days,
    )
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Регистрация нового пользователя с ролью ``user``.

    Дубль по email — 409. Зачем не 400: 400 — клиент прислал кривой запрос,
    409 — запрос ок, но конфликт с состоянием БД.
    """

    settings = _settings(request)
    email = payload.email.lower().strip()

    exists = await session.execute(select(User.id).where(User.email == email))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )

    role_result = await session.execute(
        select(Role).where(Role.name == RoleName.USER)
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        # Не выполнили миграцию с seed — это не вина клиента, поэтому 500.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="server misconfigured: roles not seeded",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password, rounds=settings.bcrypt_rounds),
        role_id=role.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user, attribute_names=["role"])
    return user


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """Выдать пару токенов. На любую ошибку — 401 с generic-сообщением."""

    settings = _settings(request)
    email = payload.email.lower().strip()

    result = await session.execute(
        select(User).options(selectinload(User.role)).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    if not user.is_active:
        # Отключённому пользователю говорим то же самое, что и при ошибке пароля,
        # чтобы не подсказывать перебору.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    return _issue_pair(user, settings)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """Обмен refresh-токена на свежую пару.

    Проверяем не только подпись и срок, но и ``token_version`` пользователя:
    смена пароля инвалидирует все ранее выданные refresh.
    """

    settings = _settings(request)
    try:
        decoded = decode_token(
            payload.refresh_token,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid refresh token",
        ) from exc

    if decoded.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="wrong token type",
        )

    result = await session.execute(
        select(User).options(selectinload(User.role)).where(User.id == decoded.sub)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not available",
        )
    if user.token_version != decoded.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token revoked",
        )

    return _issue_pair(user, settings)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Текущий пользователь по access-токену."""

    return user
