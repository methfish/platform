.PHONY: help dev up down migrate test lint seed clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Development ---

dev: ## Start all services for local development
	docker compose up -d postgres redis
	@echo "Waiting for services..."
	@sleep 3
	cd backend && pip install -e ".[dev]" && \
	alembic upgrade head && \
	python -m scripts.seed_data && \
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

up: ## Start all services with Docker Compose
	docker compose up -d --build

down: ## Stop all services
	docker compose down

logs: ## View backend logs
	docker compose logs -f backend

# --- Database ---

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="add_column")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	cd backend && alembic downgrade -1

# --- Testing ---

test: ## Run all tests
	cd backend && python -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	cd backend && python -m pytest tests/unit/ -v

test-integration: ## Run integration tests
	cd backend && python -m pytest tests/integration/ -v

test-cov: ## Run tests with coverage
	cd backend && python -m pytest tests/ --cov=app --cov-report=html --cov-report=term

# --- Code Quality ---

lint: ## Run linter
	cd backend && ruff check app/ tests/

format: ## Format code
	cd backend && ruff format app/ tests/

typecheck: ## Run type checker
	cd backend && mypy app/

# --- Data ---

seed: ## Seed demo data for paper trading
	cd backend && python -m scripts.seed_data

# --- Cleanup ---

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

clean-all: clean ## Remove everything including Docker volumes
	docker compose down -v
