"""Роли пользователей. Простейший RBAC: фиксированный набор имён.

Зачем enum, а не свободная строка: ошибка в названии роли — это баг
безопасности, а не опечатка в данных. Лучше падать в проверке типа.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RoleName(enum.StrEnum):
    """Имена ролей. ``user`` — обычный пользователь, ``admin`` — полный доступ."""

    USER = "user"
    ADMIN = "admin"


class Role(Base):
    """Роль. Один пользователь — одна роль (упрощение для шаблона)."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[RoleName] = mapped_column(
        SAEnum(RoleName, name="role_name_enum"),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover — диагностика, не бизнес-логика
        return f"<Role {self.name.value}>"
