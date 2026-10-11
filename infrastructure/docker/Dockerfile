# syntax=docker/dockerfile:1.7
# API and MCP server image (same code, different command).

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS builder
COPY pyproject.toml README.md ./
COPY agents ./agents
COPY apps/__init__.py ./apps/__init__.py
COPY apps/api ./apps/api
COPY apps/mcp_server ./apps/mcp_server
COPY core ./core
COPY evals ./evals
COPY llm ./llm
COPY observability ./observability
COPY prompts ./prompts
COPY rag ./rag
COPY security ./security
COPY services ./services
COPY storage ./storage
RUN pip install --prefix=/install ".[postgres]"

FROM base AS production
COPY --from=builder /install /usr/local
COPY data ./data
RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app
ENV DOCUMENTS_DIR=/app/data/documents \
    ENTERPRISE_DATA_DIR=/app/data/enterprise
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
