FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY alembic.ini ./
COPY migrations migrations
COPY app app
