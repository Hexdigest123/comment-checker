# Comment Checker Monorepo Makefile
# Quick actions for development and deployment

.PHONY: help dev down logs migrate test lint build clean db-reset

# Colors
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# Development
dev: ## Start all services in development mode
	@echo "$(YELLOW)Starting development environment...$(NC)"
	docker compose -f docker-compose.yml up -d

# Stop services
down: ## Stop and remove all containers
	@echo "$(YELLOW)Stopping containers...$(NC)"
	docker compose -f docker-compose.yml down

# View logs
logs: ## Show logs for all services
	@echo "$(YELLOW)Showing logs...$(NC)"
	docker compose -f docker-compose.yml logs -f

logs-backend: ## Show backend logs only
	docker compose -f docker-compose.yml logs -f backend

logs-frontend: ## Show frontend logs only
	docker compose -f docker-compose.yml logs -f frontend

logs-db: ## Show database logs only
	docker compose -f docker-compose.yml logs -f db

# Database migration
migrate: ## Run database migrations
	@echo "$(YELLOW)Running database migrations...$(NC)"
	docker compose -f docker-compose.yml exec backend alembic upgrade head

migrate-make: ## Create a new migration
	@echo "$(YELLOW)Creating new migration...$(NC)"
	docker compose -f docker-compose.yml exec backend alembic revision --autogenerate -m "$(message)"

# Testing
test: ## Run backend tests
	@echo "$(YELLOW)Running backend tests...$(NC)"
	docker compose -f docker-compose.yml exec backend pytest tests/ -v

# Linting
lint: ## Run linting on backend
	@echo "$(YELLOW)Running linting...$(NC)"
	docker compose -f docker-compose.yml exec backend ruff check src/
	docker compose -f docker-compose.yml exec backend mypy src/

# Build
build: ## Build production images
	@echo "$(YELLOW)Building production images...$(NC)"
	docker compose -f docker-compose.prod.yml build

build-backend: ## Build backend only
	docker build -t comment-checker-backend ./backend

build-frontend: ## Build frontend only
	docker build -t comment-checker-frontend ./frontend

# Clean
clean: ## Remove all containers, volumes, and images
	@echo "$(YELLOW)Cleaning up...$(NC)"
	docker compose -f docker-compose.yml down -v --rmi local
	docker compose -f docker-compose.prod.yml down -v --rmi local

# Database reset
db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(YELLOW)Resetting database...$(NC)"
	docker compose -f docker-compose.yml exec db dropdb -U ${DB_USER:-comment_checker} ${DB_NAME:-comment_checker} || true
	docker compose -f docker-compose.yml exec db createdb -U ${DB_USER:-comment_checker} ${DB_NAME:-comment_checker}
	docker compose -f docker-compose.yml exec backend alembic upgrade head

# Production
prod-up: ## Start production services
	@echo "$(YELLOW)Starting production environment...$(NC)"
	docker compose -f docker-compose.prod.yml up -d

prod-down: ## Stop production services
	docker compose -f docker-compose.prod.yml down

# Shell access
shell-backend: ## Open shell in backend container
	docker compose -f docker-compose.yml exec backend sh

shell-frontend: ## Open shell in frontend container
	docker compose -f docker-compose.yml exec frontend sh

shell-db: ## Open shell in database container
	docker compose -f docker-compose.yml exec db psql -U ${DB_USER:-comment_checker} -d ${DB_NAME:-comment_checker}

# Frontend install (for development)
frontend-install: ## Install frontend dependencies
	cd frontend && npm install

# Frontend dev server (standalone)
frontend-dev: ## Run frontend dev server
	cd frontend && npm run dev

# Backend install (for development)
backend-install: ## Install backend dependencies
	cd backend && pip install -r requirements.txt

# Backend dev server (standalone)
backend-dev: ## Run backend dev server
	cd backend && uvicorn src.main:app --reload --port 8000

# Check health
health: ## Check health of all services
	@echo "$(YELLOW)Checking service health...$(NC)"
	docker compose -f docker-compose.yml ps
	docker compose -f docker-compose.yml exec backend python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status(); print('Backend: OK')"
	docker compose -f docker-compose.yml exec frontend wget -qO- http://localhost:3000/ > /dev/null && echo "Frontend: OK" || echo "Frontend: FAILED"
	docker compose -f docker-compose.yml exec db pg_isready -U ${DB_USER:-comment_checker} -d ${DB_NAME:-comment_checker} && echo "Database: OK" || echo "Database: FAILED"
