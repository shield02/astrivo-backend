.PHONY: help up rebuild build down restart ps logs logs-postgres logs-redis db-shell redis-shell db-upgrade db-downgrade worker

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z_-]+:.*## / {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start PostgreSQL and Redis, waiting for health checks
	docker compose up -d --wait

build: ## Build images (all services, or one with SERVICE=api)
	docker compose build $(SERVICE)

rebuild: ## Rebuild and start services (all, or one with SERVICE=api)
	docker compose up -d --build --wait $(SERVICE)

down: ## Stop local services and preserve their data volumes
	docker compose down

restart: ## Restart local services
	docker compose restart

ps: ## Show local service status
	docker compose ps

logs: ## Follow logs from PostgreSQL and Redis
	docker compose logs -f postgres redis

logs-postgres: ## Follow PostgreSQL logs
	docker compose logs -f postgres

logs-redis: ## Follow Redis logs
	docker compose logs -f redis

db-shell: ## Open a psql shell in the local database
	docker compose exec postgres sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

redis-shell: ## Open a Redis CLI shell
	docker compose exec redis redis-cli

db-upgrade: ## Apply all Alembic migrations
	.venv/bin/alembic upgrade head

db-downgrade: ## Roll back the latest Alembic migration
	.venv/bin/alembic downgrade -1

worker: ## Run the ARQ document-processing worker
	.venv/bin/arq app.workers.document_worker.WorkerSettings
