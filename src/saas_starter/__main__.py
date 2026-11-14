"""Запуск через ``python -m saas_starter`` или скрипт ``saas-starter``."""

from __future__ import annotations

import uvicorn

from .config import get_settings


def main() -> None:
    """Запустить uvicorn на настройках из .env."""

    settings = get_settings()
    uvicorn.run(
        "saas_starter.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
