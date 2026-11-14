"""Эндпоинты управления пользователями.

PATCH /users/me — себя править разрешено.
GET /users/{id} — только админ.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import RoleName, User
from ..schemas import UserOut, UserUpdate
from ..security.dependencies import get_current_user, get_db, require_role

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Поменять собственные данные. Сейчас только email."""

    if payload.email is not None:
        new_email = payload.email.lower().strip()
        if new_email != user.email:
            existing = await session.execute(
                select(User.id).where(User.email == new_email)
            )
            if existing.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="email already taken",
                )
            user.email = new_email

    await session.commit()
    await session.refresh(user, attribute_names=["role"])
    return user


@router.get(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_role(RoleName.ADMIN))],
)
async def get_user(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Прочитать чужой профиль. Только для админа."""

    result = await session.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    return user
