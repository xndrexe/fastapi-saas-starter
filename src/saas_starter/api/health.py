"""Liveness-проба.

Не лезем в БД: на k8s liveness должен отвечать «процесс жив», даже если
БД временно недоступна — иначе k8s перезапустит контейнер, и БД от этого
не оживёт. Под отдельный readyz сделать в проде.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
