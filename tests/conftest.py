from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from core.models import Principal, Role
from core.settings import Settings
from security.auth import issue_token

Headers = dict[str, str]


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="mock",
        embedding_provider="hashing",
        database_url="",
        mcp_server_url="",
        rate_limit_per_minute=1000,
        otel_exporter_otlp_endpoint="",
    )


@pytest.fixture(scope="session")
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def auth(settings: Settings) -> Callable[..., Headers]:
    def make(role: Role | str, subject: str | None = None) -> Headers:
        role = Role(role)
        principal = Principal(subject=subject or f"test-{role.value.lower()}", role=role)
        return {"Authorization": f"Bearer {issue_token(principal, settings)}"}

    return make
