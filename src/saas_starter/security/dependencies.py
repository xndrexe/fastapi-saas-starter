"""FastAPI-зависимости для авторизации.

current_user — достаёт пользователя из access-токена.
require_role — фабрика проверок RBAC.

Возвращаем 401 при отсутствии/невалидности токена и 403 при недостатке
прав. Это разные класса ошибок: «вы кто?» vs «вам сюда нельзя».
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import RoleName, User
from .jwt import InvalidTokenError, decode_token

_bearer = HTTPBearer(auto_error=False)


def _get_settings_from_app(request: Request) -> Settings:
    """Settings прячется в app.state.settings — туда кладёт create_app()."""

    return request.app.state.settings  # type: ignore[no-any-return]


def _get_session_from_app(request: Request):
    """Сессии-фабрика тоже на app.state — это упрощает override в тестах."""

    return request.app.state.sessionmaker


async def get_db(
    request: Request,
):
    """Достаём AsyncSession из закреплённой за приложением фабрики."""

    sessionmaker = _get_session_from_app(request)
    async with sessionmaker() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Распаковывает access-token, возвращает живого активного пользователя.

    Зачем именно тут проверка ``is_active`` и ``token_version``: токен живёт
    минуты, но за это время можно успеть отключить злоумышленника. Сверка
    с БД — единственный достоверный источник.
    """

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = _get_settings_from_app(request)

    try:
        payload = decode_token(
            credentials.credentials,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="wrong token type",
        )

    result = await session.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not available",
        )

    if user.token_version != payload.token_version:
        # Пароль сменили после выдачи токена — токен инвалидирован.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token revoked",
        )

    return user


def require_role(required: RoleName) -> Callable[..., Awaitable[User]]:
    """Фабрика зависимости: пускает только пользователей с нужной ролью.

    Сейчас плоская модель: admin > user. Если в будущем появятся роли с
    более сложной иерархией — менять здесь.
    """

    async def _checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="role missing",
            )

        if required == RoleName.USER:
            return user
        if required == RoleName.ADMIN and user.role.name == RoleName.ADMIN:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient role",
        )

    return _checker
