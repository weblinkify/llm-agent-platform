from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent

DEV_JWT_SECRET = "dev-only-change-me-0123456789abcdef"  # noqa: S105

LLMProviderName = Literal["mock", "openai", "azure_openai", "anthropic"]
EmbeddingProviderName = Literal["hashing", "openai", "azure_openai"]


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or `.env`."""

    app_name: str = "Telco AI Operations Assistant"
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM
    llm_provider: LLMProviderName = "mock"
    llm_model: str = ""
    llm_temperature: float = 0.0
    mock_token_delay_ms: int = Field(
        default=0, description="Simulated per-token pacing for mock streaming in the demo UI."
    )
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""

    # Retrieval
    embedding_provider: EmbeddingProviderName = "hashing"
    embedding_model: str = "text-embedding-3-small"
    documents_dir: Path = ROOT_DIR / "data" / "documents"
    enterprise_data_dir: Path = ROOT_DIR / "data" / "enterprise"
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_top_k: int = 4
    retrieval_candidates: int = 20
    min_similarity: float = Field(
        default=0.18,
        description="Minimum cosine similarity of the best chunk; below it the "
        "assistant answers 'insufficient context'.",
    )
    reranker_model: str = ""

    # Storage: empty DATABASE_URL selects in-memory stores
    database_url: str = ""

    # MCP: empty URL runs the MCP server in-process
    mcp_server_url: str = ""

    # Security
    jwt_secret: str = DEV_JWT_SECRET
    jwt_issuer: str = "telco-ai-ops"
    jwt_ttl_minutes: int = 60
    demo_mode: bool = True
    rate_limit_per_minute: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]

    # Observability
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "telco-ai-api"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.app_env == "production" and settings.jwt_secret == DEV_JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be set in production")
    return settings
