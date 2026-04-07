.PHONY: infra infra-down api celery frontend migrate migration lint test

# ============ Infrastructure ============
# Start Docker services (Postgres, Qdrant, Redis)
infra:
	docker compose -f docker-compose.dev.yml up -d postgres qdrant redis

infra-down:
	docker compose -f docker-compose.dev.yml down

# ============ Backend ============
# Start FastAPI server with hot reload
api:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker for background PDF processing
celery:
	cd backend && uv run celery -A app.celery_app worker --loglevel=info --concurrency=4

# ============ Frontend ============
# Start React dev server
frontend:
	cd frontend && npm run dev

# ============ Database ============
# Run Alembic migrations
migrate:
	cd backend && uv run alembic upgrade head

# Create a new migration
migration:
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

# ============ Quality ============
# Run linter
lint:
	cd backend && uv run ruff check .

lint-frontend:
	cd frontend && npm run lint

# Start Celery Beat scheduler for periodic tasks
celery-beat:
	cd backend && uv run celery -A app.celery_app beat --loglevel=info

# Run tests
test:
	cd backend && uv run pytest

hooks:
	pre-commit install

# ============ Dev Infrastructure ============
dev-infra:
	docker compose -f docker-compose.dev.yml up -d

dev-infra-down:
	docker compose -f docker-compose.dev.yml down

dev-infra-logs:
	docker compose -f docker-compose.dev.yml logs -f