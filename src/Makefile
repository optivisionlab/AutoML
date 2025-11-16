# Makefile for NCKH AutoML Project Docker Operations
# ===================================================

# Variables
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_FILE = docker-compose.yml
DOCKER_COMPOSE_DEV = docker-compose.dev.yml
DOCKER_COMPOSE_PROD = docker-compose.prod.yml
PROJECT_NAME = nckh-automl

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

# ===================================================
# Help
# ===================================================
.PHONY: help
help: ## Show this help message
	@echo "$(GREEN)NCKH AutoML Docker Management$(NC)"
	@echo "==============================="
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make [command]"

# ===================================================
# Docker Build Commands
# ===================================================
.PHONY: build
build: ## Build all Docker images
	@echo "$(GREEN)Building all Docker images...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) build

.PHONY: build-frontend
build-frontend: ## Build frontend Docker image
	@echo "$(GREEN)Building frontend Docker image...$(NC)"
	docker build -t $(PROJECT_NAME)-frontend:latest -f frontend/Dockerfile.production frontend/

.PHONY: build-backend
build-backend: ## Build backend Docker image
	@echo "$(GREEN)Building backend Docker image...$(NC)"
	docker build -t $(PROJECT_NAME)-backend:latest -f backend/Dockerfile.api backend/

.PHONY: build-worker
build-worker: ## Build worker Docker image
	@echo "$(GREEN)Building worker Docker image...$(NC)"
	docker build -t $(PROJECT_NAME)-worker:latest -f backend/worker.dockerfile backend/

.PHONY: build-no-cache
build-no-cache: ## Build all images without cache
	@echo "$(GREEN)Building all Docker images without cache...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) build --no-cache

# ===================================================
# Docker Run Commands
# ===================================================
.PHONY: up
up: ## Start all services in detached mode
	@echo "$(GREEN)Starting all services...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d

.PHONY: up-verbose
up-verbose: ## Start all services with logs
	@echo "$(GREEN)Starting all services with logs...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up

.PHONY: up-frontend
up-frontend: ## Start only frontend service
	@echo "$(GREEN)Starting frontend service...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d frontend

.PHONY: up-backend
up-backend: ## Start only backend services
	@echo "$(GREEN)Starting backend services...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d backend worker-1 worker-2 gradio

.PHONY: up-infra
up-infra: ## Start only infrastructure services (DB, Kafka, Redis, MinIO)
	@echo "$(GREEN)Starting infrastructure services...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d mongo kafka redis minio

.PHONY: up-prod
up-prod: ## Start services in production mode with nginx
	@echo "$(GREEN)Starting services in production mode...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --profile production up -d

# ===================================================
# Docker Stop Commands
# ===================================================
.PHONY: down
down: ## Stop and remove all containers
	@echo "$(RED)Stopping and removing all containers...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down

.PHONY: down-volumes
down-volumes: ## Stop containers and remove volumes (WARNING: Deletes data!)
	@echo "$(RED)WARNING: This will delete all data in volumes!$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down -v

.PHONY: stop
stop: ## Stop all running containers
	@echo "$(YELLOW)Stopping all containers...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) stop

.PHONY: restart
restart: ## Restart all services
	@echo "$(YELLOW)Restarting all services...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) restart

# ===================================================
# Docker Logs Commands
# ===================================================
.PHONY: logs
logs: ## Show logs for all services
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f

.PHONY: logs-frontend
logs-frontend: ## Show frontend logs
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f frontend

.PHONY: logs-backend
logs-backend: ## Show backend logs
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f backend

.PHONY: logs-worker
logs-worker: ## Show worker logs
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f worker-1 worker-2

.PHONY: logs-kafka
logs-kafka: ## Show Kafka logs
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f kafka

.PHONY: logs-mongo
logs-mongo: ## Show MongoDB logs
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f mongo

# ===================================================
# Docker Status Commands
# ===================================================
.PHONY: ps
ps: ## Show status of all containers
	@echo "$(GREEN)Container Status:$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) ps

.PHONY: health
health: ## Check health status of services
	@echo "$(GREEN)Checking service health...$(NC)"
	@echo "Frontend: " && curl -f http://localhost:3000/api/health 2>/dev/null && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Unhealthy$(NC)"
	@echo "Backend: " && curl -f http://localhost:9999/health 2>/dev/null && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Unhealthy$(NC)"
	@echo "Gradio: " && curl -f http://localhost:7860 2>/dev/null && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Unhealthy$(NC)"
	@echo "MongoDB: " && docker exec nckh-mongodb mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Unhealthy$(NC)"
	@echo "Redis: " && docker exec nckh-redis redis-cli ping >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Unhealthy$(NC)"

# ===================================================
# Docker Exec Commands
# ===================================================
.PHONY: shell-backend
shell-backend: ## Open shell in backend container
	docker exec -it nckh-backend /bin/bash

.PHONY: shell-frontend
shell-frontend: ## Open shell in frontend container
	docker exec -it nckh-frontend /bin/sh

.PHONY: shell-mongo
shell-mongo: ## Open MongoDB shell
	docker exec -it nckh-mongodb mongosh

.PHONY: shell-redis
shell-redis: ## Open Redis CLI
	docker exec -it nckh-redis redis-cli

# ===================================================
# Database Commands
# ===================================================
.PHONY: db-backup
db-backup: ## Backup MongoDB database
	@echo "$(GREEN)Backing up MongoDB...$(NC)"
	@mkdir -p backups
	docker exec nckh-mongodb mongodump --out /tmp/backup
	docker cp nckh-mongodb:/tmp/backup ./backups/mongo-backup-$$(date +%Y%m%d-%H%M%S)
	@echo "$(GREEN)Backup completed!$(NC)"

.PHONY: db-restore
db-restore: ## Restore MongoDB database from backup (requires BACKUP_PATH)
	@if [ -z "$(BACKUP_PATH)" ]; then \
		echo "$(RED)ERROR: BACKUP_PATH not specified$(NC)"; \
		echo "Usage: make db-restore BACKUP_PATH=./backups/mongo-backup-YYYYMMDD-HHMMSS"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restoring MongoDB from $(BACKUP_PATH)...$(NC)"
	docker cp $(BACKUP_PATH) nckh-mongodb:/tmp/restore
	docker exec nckh-mongodb mongorestore /tmp/restore
	@echo "$(GREEN)Restore completed!$(NC)"

# ===================================================
# Development Commands
# ===================================================
.PHONY: dev
dev: ## Start services in development mode
	@echo "$(GREEN)Starting services in development mode...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up

.PHONY: dev-frontend
dev-frontend: ## Start frontend in development mode
	@echo "$(GREEN)Starting frontend in development mode...$(NC)"
	cd frontend && npm run dev

.PHONY: dev-backend
dev-backend: ## Start backend in development mode
	@echo "$(GREEN)Starting backend in development mode...$(NC)"
	cd backend && python app.py

# ===================================================
# Testing Commands
# ===================================================
.PHONY: test
test: ## Run all tests
	@echo "$(GREEN)Running all tests...$(NC)"
	@echo "Running backend tests..."
	cd backend && python -m pytest
	@echo "Running frontend tests..."
	cd frontend && npm test

.PHONY: test-backend
test-backend: ## Run backend tests
	@echo "$(GREEN)Running backend tests...$(NC)"
	docker exec nckh-backend python -m pytest

.PHONY: test-frontend
test-frontend: ## Run frontend tests
	@echo "$(GREEN)Running frontend tests...$(NC)"
	docker exec nckh-frontend npm test

# ===================================================
# Cleaning Commands
# ===================================================
.PHONY: clean
clean: ## Clean up Docker resources
	@echo "$(YELLOW)Cleaning up Docker resources...$(NC)"
	docker system prune -f

.PHONY: clean-all
clean-all: ## Clean all Docker resources including volumes (WARNING!)
	@echo "$(RED)WARNING: This will remove all Docker resources including volumes!$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	docker system prune -af --volumes

.PHONY: clean-images
clean-images: ## Remove project Docker images
	@echo "$(YELLOW)Removing project Docker images...$(NC)"
	docker rmi -f $$(docker images | grep $(PROJECT_NAME) | awk '{print $$3}') 2>/dev/null || true

# ===================================================
# Utility Commands
# ===================================================
.PHONY: ports
ports: ## Show exposed ports
	@echo "$(GREEN)Exposed Ports:$(NC)"
	@echo "Frontend:    http://localhost:3000"
	@echo "Backend API: http://localhost:9999"
	@echo "Gradio Demo: http://localhost:7860"
	@echo "Worker 1:    http://localhost:4001"
	@echo "Worker 2:    http://localhost:4002"
	@echo "MongoDB:     mongodb://localhost:27017"
	@echo "Kafka:       localhost:9092"
	@echo "Redis:       localhost:6379"
	@echo "MinIO:       http://localhost:9000"
	@echo "MinIO Console: http://localhost:9001"

.PHONY: install
install: ## Install project dependencies
	@echo "$(GREEN)Installing project dependencies...$(NC)"
	cd frontend && npm install
	cd backend && pip install -r requirements.txt

.PHONY: validate
validate: ## Validate Docker Compose configuration
	@echo "$(GREEN)Validating Docker Compose configuration...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) config

# ===================================================
# Quick Start Commands
# ===================================================
.PHONY: quick-start
quick-start: ## Quick start - build and run all services
	@echo "$(GREEN)Quick starting NCKH AutoML project...$(NC)"
	@make build
	@make up
	@sleep 10
	@make health
	@make ports

.PHONY: reset
reset: ## Reset everything - stop, clean, rebuild, and start
	@echo "$(YELLOW)Resetting entire project...$(NC)"
	@make down
	@make clean
	@make build
	@make up
	@echo "$(GREEN)Reset complete!$(NC)"
