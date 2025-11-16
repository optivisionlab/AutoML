# Docker Setup for NCKH AutoML Project

This document provides comprehensive instructions for building, running, and managing the NCKH AutoML project using Docker.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Project Architecture](#project-architecture)
- [Quick Start](#quick-start)
- [Docker Files Overview](#docker-files-overview)
- [Build Instructions](#build-instructions)
- [Running Services](#running-services)
- [Service URLs](#service-urls)
- [Environment Variables](#environment-variables)
- [Data Persistence](#data-persistence)
- [Monitoring & Logs](#monitoring--logs)
- [Troubleshooting](#troubleshooting)
- [Production Deployment](#production-deployment)

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Make** (optional): For using the Makefile commands
- **Git**: For cloning the repository

### System Requirements

- **RAM**: Minimum 8GB (16GB recommended)
- **Storage**: At least 20GB free space
- **CPU**: 4 cores or more recommended

## Project Architecture

The project consists of multiple microservices:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│   Workers   │
│  (Next.js)  │     │  (FastAPI)  │     │  (Python)   │
└─────────────┘     └─────────────┘     └─────────────┘
                            │
                    ┌───────┼───────┐
                    │       │       │
            ┌─────────┐ ┌─────────┐ ┌─────────┐
            │ MongoDB │ │  Kafka  │ │  Redis  │
            └─────────┘ └─────────┘ └─────────┘
                            │
                    ┌─────────────┐
                    │    MinIO    │
                    └─────────────┘
```

## Quick Start

### Using Make (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd nckh/src

# Quick start - build and run all services
make quick-start

# Check service health
make health

# View service URLs
make ports
```

### Using Docker Compose Directly

```bash
# Build all images
docker-compose build

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Docker Files Overview

### Main Docker Files

- **`Dockerfile`**: Multi-stage build for the entire application
- **`docker-compose.yml`**: Main orchestration file for all services
- **`docker-compose.dev.yml`**: Development-specific overrides
- **`docker-compose.prod.yml`**: Production-specific overrides

### Service-Specific Dockerfiles

- **`frontend/Dockerfile.production`**: Optimized frontend build
- **`backend/Dockerfile.api`**: Backend API service
- **`backend/worker.dockerfile`**: Worker service for ML tasks
- **`backend/hautoml.nano.dockerfile`**: Gradio demo interface
- **`backend/hautoml.toolkit.dockerfile`**: AutoML toolkit service

## Build Instructions

### Building Individual Services

```bash
# Build frontend
make build-frontend
# or
docker build -t nckh-frontend:latest -f frontend/Dockerfile.production frontend/

# Build backend
make build-backend
# or
docker build -t nckh-backend:latest -f backend/Dockerfile.api backend/

# Build worker
make build-worker
# or
docker build -t nckh-worker:latest -f backend/worker.dockerfile backend/
```

### Building All Services

```bash
# Build all services
make build
# or
docker-compose build

# Build without cache (fresh build)
make build-no-cache
# or
docker-compose build --no-cache
```

## Running Services

### Starting All Services

```bash
# Start all services in background
make up
# or
docker-compose up -d

# Start with logs visible
make up-verbose
# or
docker-compose up
```

### Starting Specific Services

```bash
# Start only infrastructure (MongoDB, Kafka, Redis, MinIO)
make up-infra

# Start only frontend
make up-frontend

# Start only backend services
make up-backend

# Start in production mode with nginx
make up-prod
```

### Stopping Services

```bash
# Stop all services
make stop
# or
docker-compose stop

# Stop and remove containers
make down
# or
docker-compose down

# Stop and remove everything including volumes (WARNING: Deletes data!)
make down-volumes
# or
docker-compose down -v
```

## Service URLs

Once the services are running, you can access them at:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Main web interface |
| **Backend API** | http://localhost:9999 | REST API endpoints |
| **API Docs** | http://localhost:9999/docs | Swagger documentation |
| **Gradio Demo** | http://localhost:7860 | ML demo interface |
| **Worker 1** | http://localhost:4001 | Worker service |
| **Worker 2** | http://localhost:4002 | Worker service |
| **MongoDB** | mongodb://localhost:27017 | Database |
| **Kafka** | localhost:9092 | Message broker |
| **Redis** | localhost:6379 | Cache |
| **MinIO** | http://localhost:9000 | Object storage |
| **MinIO Console** | http://localhost:9001 | MinIO admin UI |

## Environment Variables

### Backend Configuration

Create a `.env` file in the `backend/` directory:

```env
# Database
MONGODB_URL=mongodb://mongo:27017
MONGO_DB_NAME=nckh_automl

# Message Queue
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC=ml-tasks

# Cache
REDIS_HOST=redis
REDIS_PORT=6379

# Object Storage
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=models

# API Settings
API_HOST=0.0.0.0
API_PORT=9999
API_WORKERS=4
LOG_LEVEL=info

# JWT Secret
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
```

### Frontend Configuration

Create a `.env.local` file in the `frontend/` directory:

```env
# API Endpoints
NEXT_PUBLIC_API_URL=http://localhost:9999
NEXT_PUBLIC_GRADIO_URL=http://localhost:7860
NEXT_PUBLIC_WS_URL=ws://localhost:9999/ws

# Authentication
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret-here

# Features
NEXT_PUBLIC_ENABLE_ANALYTICS=false
NEXT_PUBLIC_ENABLE_DEBUG=false
```

## Data Persistence

### Volume Mappings

The following volumes are used for data persistence:

| Volume | Container Path | Description |
|--------|---------------|-------------|
| `mongo-data` | `/data/db` | MongoDB database files |
| `kafka-data` | `/var/lib/kafka/data` | Kafka message data |
| `redis-data` | `/data` | Redis persistence |
| `minio-data` | `/data` | MinIO object storage |
| `./backend/data` | `/app/data` | Application data |
| `./backend/logs` | `/app/logs` | Application logs |
| `./backend/uploads` | `/app/uploads` | User uploads |

### Backup and Restore

#### MongoDB Backup

```bash
# Create backup
make db-backup
# or manually
docker exec nckh-mongodb mongodump --out /tmp/backup
docker cp nckh-mongodb:/tmp/backup ./backups/mongo-backup-$(date +%Y%m%d-%H%M%S)

# Restore backup
make db-restore BACKUP_PATH=./backups/mongo-backup-20240101-120000
# or manually
docker cp ./backups/mongo-backup-20240101-120000 nckh-mongodb:/tmp/restore
docker exec nckh-mongodb mongorestore /tmp/restore
```

## Monitoring & Logs

### Viewing Logs

```bash
# View all logs
make logs
# or
docker-compose logs -f

# View specific service logs
make logs-frontend
make logs-backend
make logs-worker
make logs-kafka
make logs-mongo

# Using docker-compose
docker-compose logs -f frontend
docker-compose logs -f backend
```

### Health Checks

```bash
# Check all services health
make health

# Check individual service
curl http://localhost:9999/health  # Backend
curl http://localhost:3000/api/health  # Frontend

# Check container status
make ps
# or
docker-compose ps
```

### Accessing Service Shells

```bash
# Backend shell
make shell-backend
# or
docker exec -it nckh-backend /bin/bash

# Frontend shell
make shell-frontend
# or
docker exec -it nckh-frontend /bin/sh

# MongoDB shell
make shell-mongo
# or
docker exec -it nckh-mongodb mongosh

# Redis CLI
make shell-redis
# or
docker exec -it nckh-redis redis-cli
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Port Already in Use

```bash
# Check what's using the port
lsof -i :3000  # For macOS/Linux
netstat -ano | findstr :3000  # For Windows

# Change port in docker-compose.yml
# Example: Change "3000:3000" to "3001:3000"
```

#### 2. Container Fails to Start

```bash
# Check logs
docker-compose logs <service-name>

# Rebuild the image
docker-compose build --no-cache <service-name>

# Remove and recreate
docker-compose rm -f <service-name>
docker-compose up -d <service-name>
```

#### 3. Database Connection Issues

```bash
# Verify MongoDB is running
docker-compose ps mongo

# Check MongoDB logs
docker-compose logs mongo

# Test connection
docker exec -it nckh-mongodb mongosh --eval "db.adminCommand('ping')"
```

#### 4. Out of Memory

```bash
# Check Docker resources
docker system df

# Clean up unused resources
docker system prune -a

# Increase Docker memory limit (Docker Desktop settings)
```

#### 5. Permission Issues

```bash
# Fix permissions for volumes
sudo chown -R $USER:$USER ./backend/data ./backend/logs ./backend/uploads

# Or run with appropriate user in docker-compose.yml
user: "1000:1000"
```

### Debug Mode

To run services in debug mode:

```bash
# Set debug environment variables
export DEBUG=true
export LOG_LEVEL=debug

# Run with debug configuration
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up
```

## Production Deployment

### Production Build

```bash
# Build production images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start production services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Security Considerations

1. **Change default passwords**:
   - MongoDB root password
   - MinIO access keys
   - JWT secret keys

2. **Use secrets management**:
   ```yaml
   # docker-compose.prod.yml
   secrets:
     db_password:
       file: ./secrets/db_password.txt
   ```

3. **Enable TLS/SSL**:
   - Configure nginx with SSL certificates
   - Use HTTPS for all external communication

4. **Network isolation**:
   ```yaml
   networks:
     frontend:
     backend:
     database:
   ```

### Scaling Services

```bash
# Scale workers
docker-compose up -d --scale worker=4

# Using Docker Swarm
docker stack deploy -c docker-stack.yml nckh-automl
```

### Monitoring in Production

Consider adding:
- **Prometheus** for metrics collection
- **Grafana** for visualization
- **ELK Stack** for log aggregation
- **Jaeger** for distributed tracing

## Maintenance

### Regular Tasks

```bash
# Daily: Check service health
make health

# Weekly: Clean up unused resources
make clean

# Monthly: Backup databases
make db-backup

# As needed: Update images
docker-compose pull
make build
```

### Updating Services

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
make down
make build
make up
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [MongoDB Docker Hub](https://hub.docker.com/_/mongo)
- [Kafka Docker Hub](https://hub.docker.com/r/apache/kafka)
- [Redis Docker Hub](https://hub.docker.com/_/redis)
- [MinIO Documentation](https://docs.min.io/)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review service logs using `docker-compose logs <service>`
3. Create an issue in the project repository
4. Contact the development team

---

**Note**: This project is configured for development and testing. For production deployment, ensure you review and update all security settings, passwords, and configurations according to your organization's security policies.