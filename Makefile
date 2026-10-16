.PHONY: install up infra down migrate run worker webhook test lint format

install:
	uv sync

up:
	docker compose up -d --build --wait

infra:
	docker compose up -d --wait postgres rabbitmq

down:
	docker compose down

migrate:
	uv run alembic upgrade head

run:
	uv run uvicorn app.main:app --reload

worker:
	uv run faststream run app.worker:app

webhook:
	uv run python scripts/webhook.py

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .
