"""Схемы пользователя для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ..models.role import RoleName


class UserOut(BaseModel):
    """Публичный взгляд на пользователя. Хэш пароля сюда не попадает никогда."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: RoleName
    is_active: bool
    created_at: datetime

    @field_validator("role", mode="before")
    @classmethod
    def _unwrap_role(cls, value: Any) -> Any:
        """Из ORM приходит Role-объект — достаём из него имя."""

        if hasattr(value, "name"):
            return value.name
        return value


class UserUpdate(BaseModel):
    """Изменение собственных данных. Сейчас только email, на расширение."""

    email: EmailStr | None = Field(default=None)
