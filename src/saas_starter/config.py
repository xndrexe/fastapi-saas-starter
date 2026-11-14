"""Настройки приложения.

Все значения берутся из окружения с префиксом ``SAAS_``. Для тестов настройки
можно создавать вручную, не трогая глобальное окружение — это упрощает
изоляцию между тестами и параллельный запуск.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг сервиса.

    Зачем отдельная модель, а не модуль с константами: pydantic-settings даёт
    валидацию типов и понятную ошибку при старте, если в окружении опечатка.
    """

    model_config = SettingsConfigDict(
        env_prefix="SAAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="DSN для SQLAlchemy. В prod — postgresql+asyncpg, в dev/tests — aiosqlite.",
    )

    jwt_secret: str = Field(
        default="dev-secret-change-me-please-32-chars-minimum-required",
        min_length=32,
        description="Симметричный секрет для подписи JWT. В prod заменить на криптослучайные байты.",
    )
    jwt_algorithm: str = Field(default="HS256")

    access_token_lifetime_min: int = Field(default=30, ge=1, le=24 * 60)
    refresh_token_lifetime_days: int = Field(default=14, ge=1, le=365)

    ratelimit_auth_per_minute: int = Field(
        default=5,
        ge=1,
        le=1000,
        description="Сколько запросов в минуту разрешено на auth-эндпоинт с одного IP.",
    )

    bcrypt_rounds: int = Field(default=12, ge=4, le=15)

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)


def get_settings() -> Settings:
    """Фабрика настроек. Отдельная функция, чтобы её было удобно мокать в тестах."""

    return Settings()
