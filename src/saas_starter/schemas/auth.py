"""Схемы аутентификации.

Зачем отдельные классы под request и response, а не один: в request
паролю место есть, в response его быть не должно — даже хэша.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Регистрация. Минимум 8 символов в пароле — компромисс между UX и стойкостью."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Логин. Возвращаем generic-ошибку, чтобы не помогать перебору."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Обмен refresh-токена на новую пару."""

    refresh_token: str


class TokenPair(BaseModel):
    """Пара токенов в ответе. ``token_type`` фиксированно ``bearer``."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
