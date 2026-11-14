"""Модель пользователя.

UUID в качестве идентификатора, а не автоинкремент: id попадает в URL'ы
(/users/{id}) и в токены — раскрывать монотонную последовательность
не хочется. ID хранится строкой, чтобы тесты на SQLite работали без
дополнительных расширений.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .role import Role


def _utcnow() -> datetime:
    """tz-aware now. Используем как default — иначе SQLite возвращает naive."""

    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """Пользователь сервиса."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    role: Mapped[Role] = relationship(Role, lazy="joined")

    # Версия для refresh-token revocation: при смене пароля инкрементируется,
    # все ранее выданные refresh становятся невалидны.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email}>"
