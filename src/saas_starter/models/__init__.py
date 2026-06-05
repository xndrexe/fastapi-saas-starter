"""ORM-модели. Импорт здесь нужен, чтобы alembic-autogenerate видел все таблицы."""

from .role import Role, RoleName
from .user import User

__all__ = ["Role", "RoleName", "User"]
