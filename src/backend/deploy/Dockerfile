# 1. Base Stage: System Dependencies
FROM python:3.10-slim AS base-system

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies (build-essential & libgomp1 for ML libs like XGBoost / Scikit-learn)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ========================================================

# 2. Base Worker Stage: ML & Core Dependencies
FROM base-system AS base-worker

COPY deploy/requirements.txt /app/deploy_requirements.txt
RUN pip install --no-cache-dir -r /app/deploy_requirements.txt

# ========================================================

# 3. Base Backend Stage: Install remaining dependencies (Database Drivers & Connectors)
FROM base-worker AS base-backend

# Pip will scan requirements.txt, find all ML libs already satisfied in base-worker,
# and only install the remaining packages (Database Drivers & Connectors).
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ========================================================

# 4. Test Stage: Run Unit Tests with pytest
FROM base-backend AS test-runner

# Install testing dependencies from tests/requirements.txt
COPY tests/requirements.txt /app/tests_requirements.txt
RUN pip install --no-cache-dir -r /app/tests_requirements.txt

# Copy source code, configurations, and test suites
COPY src/ /app/src/
COPY assets/ /app/assets/
COPY tests/ /app/tests/

# Execute tests using pytest
RUN pytest tests/ -c tests/pytest.ini -v

# ========================================================

# 5. Production: Backend API & Training Consumer
FROM base-backend AS production

# Copy application source code, assets
COPY --from=test-runner /app/src/ /app/src/
COPY --from=test-runner /app/assets/ /app/assets/

CMD ["python", "-m", "src.main"]

# ========================================================

# 6. Toolkit: Standalone Demo UI
FROM production AS toolkit

# Copy demo ui
COPY demo/ /app/demo/
RUN pip install --no-cache-dir -r /app/demo/requirements.txt

CMD ["python", "-m", "demo.app"]

# ========================================================
