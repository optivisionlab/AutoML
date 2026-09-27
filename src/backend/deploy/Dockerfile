# ========================================================
# 1. Base Stage: System & Python Dependencies
# ========================================================
FROM python:3.12-slim AS base

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

# Install Python production and demo dependencies
COPY requirements.txt /app/requirements.txt
COPY demo/requirements.txt /app/demo_requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/demo_requirements.txt


# ========================================================
# 2. Test Stage: Run Unit Tests with pytest
# ========================================================
FROM base AS test-runner

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
# 3. Production / Demo Stage: Clean Image
# ========================================================
FROM base AS production

# Copy application source code, assets, and demo UI (Tests are excluded)
COPY src/ /app/src/
COPY assets/ /app/assets/
COPY demo/ /app/demo/

# Expose Gradio demo port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Launch Demo application
CMD ["python", "-m", "demo.app"]
