# Multi-stage Dockerfile for the NCKH AutoML Project

# =====================================
# Stage 1: Frontend Builder
# =====================================
FROM node:20.19.2-alpine AS frontend-builder

# Set working directory
WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy frontend source code
COPY frontend/ ./

# Build the Next.js application
RUN npm run build

# =====================================
# Stage 2: Backend Base
# =====================================
FROM python:3.10.12-slim AS backend-base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    vim \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# =====================================
# Stage 3: Final Production Image
# =====================================
FROM python:3.10.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgomp1 \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Next.js runtime
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from backend-base stage
COPY --from=backend-base /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=backend-base /usr/local/bin /usr/local/bin

# Copy backend application
COPY --chown=appuser:appuser backend/ ./backend/

# Copy frontend build and source
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/public ./frontend/public
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/node_modules ./frontend/node_modules
COPY --chown=appuser:appuser frontend/package*.json ./frontend/
COPY --chown=appuser:appuser frontend/next.config.ts ./frontend/
COPY --chown=appuser:appuser frontend/.env* ./frontend/

# Copy tools if exists
COPY --chown=appuser:appuser tools/ ./tools/

# Copy system architecture documentation
COPY --chown=appuser:appuser SYSTEM_ARCHITECTURE.md ./

# Set Python path
ENV PYTHONPATH=/app/backend
ENV NODE_ENV=production

# Create necessary directories
RUN mkdir -p /app/backend/data /app/backend/logs /app/backend/uploads \
    && chown -R appuser:appuser /app/backend/data /app/backend/logs /app/backend/uploads

# Copy supervisor configuration
RUN cat > /etc/supervisor/conf.d/app.conf << EOF
[supervisord]
nodaemon=true
user=root

[program:backend]
command=/usr/local/bin/python /app/backend/app.py
directory=/app/backend
user=appuser
autostart=true
autorestart=true
stderr_logfile=/var/log/backend.err.log
stdout_logfile=/var/log/backend.out.log
environment=PYTHONPATH="/app/backend",PATH="/usr/local/bin:/usr/bin:/bin"

[program:frontend]
command=/usr/bin/node /app/frontend/node_modules/.bin/next start -p 3000
directory=/app/frontend
user=appuser
autostart=true
autorestart=true
stderr_logfile=/var/log/frontend.err.log
stdout_logfile=/var/log/frontend.out.log
environment=NODE_ENV="production",PATH="/usr/bin:/bin"

[program:worker]
command=/usr/local/bin/python /app/backend/worker.py
directory=/app/backend
user=appuser
autostart=true
autorestart=true
stderr_logfile=/var/log/worker.err.log
stdout_logfile=/var/log/worker.out.log
environment=PYTHONPATH="/app/backend",PATH="/usr/local/bin:/usr/bin:/bin"
EOF

# Configure Nginx as reverse proxy
RUN cat > /etc/nginx/sites-available/default << EOF
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:9999/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Gradio interface
    location /gradio {
        proxy_pass http://localhost:7860;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    # Worker API
    location /worker/ {
        proxy_pass http://localhost:4000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Expose ports
EXPOSE 80 3000 9999 7860 4000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/api/health || exit 1

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/app.conf"]
