"""Postgres-backed integration tests (pgvector, audit log, approvals, LangGraph
checkpointer). Run with DATABASE_URL set; skipped otherwise."""

import os

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from core.models import Role
from core.settings import Settings
from storage.factory import open_backends

DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]


@pytest.fixture(scope="module")
def pg_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"database_url": DATABASE_URL})


async def test_pgvector_store_round_trip(pg_settings: Settings) -> None:
    from apps.mcp_server.bootstrap import build_retriever

    async with open_backends(pg_settings) as backends:
        assert backends.kind == "postgres"
        retriever = await build_retriever(backends.vector_store, backends.embedder, pg_settings)
        assert await backends.vector_store.count() > 30
        result = await retriever.retrieve("What is the SLA for a Priority 1 incident?")
        assert result.sufficient and result.chunks[0].chunk.doc_id == "DOC-001"
        assert {c.chunk.doc_id for c in result.quarantined} <= {"DOC-099"}


def test_approval_survives_restart_via_postgres_checkpointer(pg_settings: Settings, auth) -> None:  # type: ignore[no-untyped-def]
    message = "Customer 10002 is affected by INC-1003. Create a support incident and notify the support team."
    with TestClient(create_app(pg_settings)) as first:
        body = first.post(
            "/chat", json={"message": message}, headers=auth(Role.SUPPORT_AGENT, "pg-agent")
        ).json()
        assert body["status"] == "pending_approval"
        approval_id = body["approval"]["approval_id"]

    # A brand-new app instance (simulating a restart or another replica) resumes the paused graph.
    with TestClient(create_app(pg_settings)) as second:
        pending = second.get("/approvals", headers=auth(Role.ADMIN, "pg-admin")).json()
        assert approval_id in {a["approval_id"] for a in pending}
        result = second.post(
            f"/approvals/{approval_id}",
            json={"decision": "approve", "reason": "ok"},
            headers=auth(Role.ADMIN, "pg-admin"),
        ).json()
        assert result["status"] == "completed"
        assert [t["tool"] for t in result["tool_calls"]] == [
            "create_incident",
            "create_notification",
        ]
        events = second.get(
            f"/audit?request_id={body['request_id']}", headers=auth(Role.ADMIN)
        ).json()
        assert {"request", "approval_requested", "response"} <= {e["kind"] for e in events}
