"""Хэширование паролей.

bcrypt с настраиваемым cost factor (default 12) — компромисс между
скоростью входа и стойкостью к подбору. На современном железе ~100-150 мс
на одну операцию: пользователь не замечает, перебор GPU становится дорогим.

passlib используем как абстракцию: если завтра bcrypt станет слабым,
сменим schemas без переписывания вызовов.
"""

from __future__ import annotations

from passlib.context import CryptContext

# Контекст создаётся лениво при первом вызове, чтобы конфиг можно было
# подменить в тестах (через monkeypatch на _get_context).
_context: CryptContext | None = None
_current_rounds: int | None = None


def _get_context(rounds: int = 12) -> CryptContext:
    """Достаём (или пересоздаём) контекст под указанный cost.

    В тестах удобно держать cost=4 — быстрее в десятки раз. В проде только 12+.
    """

    global _context, _current_rounds
    if _context is None or _current_rounds != rounds:
        _context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=rounds,
        )
        _current_rounds = rounds
    return _context


def hash_password(password: str, rounds: int = 12) -> str:
    """Захэшировать пароль. Соль bcrypt генерит сам."""

    if not password:
        raise ValueError("password must not be empty")
    return _get_context(rounds).hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Сравнить пароль с хэшем. Возвращает False при любом сбое.

    Любое исключение в verify (битый хэш, неподдерживаемый schema) трактуется
    как «не совпало», чтобы наружу не утекали детали внутреннего состояния.
    """

    if not password or not password_hash:
        return False
    try:
        return _get_context().verify(password, password_hash)
    except Exception:
        return False
