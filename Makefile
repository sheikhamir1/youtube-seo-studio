# YouTube SEO Studio - convenience commands.
# Windows users: equivalent direct commands are documented in README.md.

SHELL := /bin/bash

.PHONY: help db-up db-down migrate dev-backend dev-frontend seed test test-backend test-frontend lint format build docker-up docker-down docker-build docker-logs clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

db-up: ## Start PostgreSQL only (development mode)
	docker compose up -d postgres

db-down: ## Stop PostgreSQL
	docker compose stop postgres

migrate: ## Apply database migrations (alembic upgrade head)
	cd backend && alembic upgrade head

dev-backend: ## Run FastAPI + worker natively with reload
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run the Vite dev server
	cd frontend && npm run dev

seed: ## Seed the default prompt template (idempotent)
	cd backend && python -m app.cli seed

status: ## Print system status from the CLI
	cd backend && python -m app.cli status

cleanup: ## Cleanup stale uploads / orphan temporary files
	cd backend && python -m app.cli cleanup

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend pytest suite
	cd backend && python -m pytest -q

test-frontend: ## Run frontend vitest suite
	cd frontend && npm run test -- --run

lint: ## Lint backend (ruff) and frontend (eslint)
	cd backend && ruff check app tests
	cd frontend && npm run lint

format: ## Format backend (ruff) and frontend (prettier)
	cd backend && ruff format app tests
	cd frontend && npm run format

build: ## Build the production frontend bundle
	cd frontend && npm run build

docker-up: ## Start the full local production-style stack
	docker compose up -d --build

docker-down: ## Stop the stack
	docker compose down

docker-build: ## Build both images
	docker compose build

docker-logs: ## Follow compose logs
	docker compose logs -f

clean: ## Remove caches and build output
	rm -rf frontend/dist backend/.pytest_cache backend/.ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
