FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir build && \
    python -m build --wheel

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --gid 1000 saas && \
    useradd --uid 1000 --gid saas --create-home --shell /bin/bash saas

WORKDIR /app

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install /tmp/*.whl && rm /tmp/*.whl

COPY alembic.ini ./
COPY alembic ./alembic

USER saas

EXPOSE 8000

ENTRYPOINT ["saas-starter"]
