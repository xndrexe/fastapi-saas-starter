"""Начальная схема: таблицы roles, users + seed двух ролей.

Revision ID: 001_initial
Revises:
Create Date: 2026-06-05

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "name",
            sa.Enum("user", "admin", name="role_name_enum"),
            nullable=False,
            unique=True,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role_id",
            sa.Integer,
            sa.ForeignKey("roles.id"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Seed двух базовых ролей. Любой регистратор получит role=user.
    # Admin создаётся вручную (или через отдельный CLI — см. README).
    roles_tbl = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(
        roles_tbl,
        [
            {"id": 1, "name": "user", "description": "обычный пользователь"},
            {"id": 2, "name": "admin", "description": "административный доступ"},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
    sa.Enum(name="role_name_enum").drop(op.get_bind(), checkfirst=True)
