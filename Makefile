.PHONY: install up down migrate run test lint format

install:
	uv sync

up:
	docker compose up -d --wait

down:
	docker compose down

migrate:
	uv run alembic upgrade head

run:
	uv run uvicorn app.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .
