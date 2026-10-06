# syntax=docker/dockerfile:1.7

# ============================================================
# Base
# ============================================================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*


# ============================================================
# Builder
# ============================================================
FROM base AS builder

# Build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

# Install dependencies into an isolated directory
RUN pip install --upgrade pip && \
    pip install --prefix=/install .


# ============================================================
# Production
# ============================================================
FROM base AS production

# Copy installed Python packages
COPY --from=builder /install /usr/local

# Copy application
COPY apps/ ./apps/
COPY agents/ ./agents/
COPY rag/ ./rag/
COPY prompts/ ./prompts/
COPY tools/ ./tools/

# Create non-root user
RUN groupadd --system appgroup && \
    useradd --system \
            --gid appgroup \
            --home-dir /app \
            --shell /usr/sbin/nologin \
            appuser

# Ensure application files are owned by non-root user
RUN chown -R appuser:appgroup /app

USER appuser

# Application port
EXPOSE 8000

# Container health check
HEALTHCHECK --interval=30s \
            --timeout=5s \
            --start-period=20s \
            --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# Start FastAPI application
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]