"""Простой in-memory rate-limiter с фиксированным окном.

Зачем своя реализация, а не slowapi: slowapi в комбинации с фабрикой
приложений требует декорировать функции-обработчики до регистрации в
роутере. У нас фабричный create_app — лимитер на каждый инстанс свой,
повесить декоратор на модульном уровне не получается без танцев.
Свой минимальный middleware на ~40 строк закрывает кейс полностью.

Ограничения:
- В памяти процесса, не разделяется между worker'ами uvicorn. Для prod
  на нескольких worker'ах подключите Redis-backend (имя метода и сигнатура
  совпадают с Limiter — заменяется без правки middleware).
- Fixed window, не sliding: всплеск на стыке окон может пропустить
  2*limit запросов подряд. Для auth-кейса (защита от перебора) — норм.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from typing import Final

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class FixedWindowLimiter:
    """Счётчик попыток в фиксированном временном окне.

    Хранит отметки времени последних попыток в deque на каждый ключ. При
    проверке отбрасывает протухшие, считает живые. Память — O(limit*keys),
    при горячем кейсе перебора это десятки байт на IP.
    """

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._limit: Final = limit
        self._window: Final = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, key: str) -> bool:
        """Зарегистрировать попытку. True если в пределах лимита, False если превышен."""

        now = time.monotonic()
        cutoff = now - self._window
        bucket = self._hits[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._limit:
            return False
        bucket.append(now)
        return True

    def reset(self) -> None:
        """Очистить все счётчики. Полезно в тестах между кейсами."""

        self._hits.clear()


def _default_key(request: Request) -> str:
    """IP клиента. ``request.client`` может быть None в редких ASGI-сценариях."""

    if request.client is None:
        return "unknown"
    return request.client.host


class PathRateLimitMiddleware(BaseHTTPMiddleware):
    """Применяет лимитер к запросам на указанные пути.

    Совпадение по полному pathname (без query). Подмаршруты не
    охватываются — auth-эндпоинтов мало, явное перечисление честнее
    регулярки и не ловит false-positive на user-эндпоинтах.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: FixedWindowLimiter,
        protected_paths: Iterable[str],
        key_func: Callable[[Request], str] = _default_key,
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._paths = frozenset(protected_paths)
        self._key_func = key_func

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._paths:
            key = f"{request.url.path}:{self._key_func(request)}"
            if not self._limiter.check_and_record(key):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "too many requests"},
                )
        return await call_next(request)
