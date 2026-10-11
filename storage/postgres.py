from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from storage.models import Approval, ApprovalStatus, AuditEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    event_id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    request_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    detail JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_log_request_idx ON audit_log (request_id);
CREATE INDEX IF NOT EXISTS audit_log_ts_idx ON audit_log (timestamp DESC);
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    body JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS approvals_status_idx ON approvals (status, created_at DESC);
"""


async def migrate(pool: AsyncConnectionPool[AsyncConnection]) -> None:
    async with pool.connection() as conn:
        await conn.execute(SCHEMA)


class PostgresAuditLog:
    def __init__(self, pool: AsyncConnectionPool[AsyncConnection]) -> None:
        self.pool = pool

    async def write(self, event: AuditEvent) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO audit_log VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    event.event_id,
                    event.timestamp,
                    event.request_id,
                    event.thread_id,
                    event.actor,
                    event.role.value,
                    event.kind,
                    event.name,
                    event.status,
                    Jsonb(event.detail),
                ),
            )

    async def list(self, limit: int = 100, request_id: str | None = None) -> list[AuditEvent]:
        query = "SELECT * FROM audit_log"
        params: list[Any] = []
        if request_id:
            query += " WHERE request_id = %s"
            params.append(request_id)
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(query, params)
            cols = [d.name for d in cur.description or []]
            return [
                AuditEvent.model_validate(dict(zip(cols, row, strict=True)))
                for row in await cur.fetchall()
            ]


class PostgresApprovalStore:
    def __init__(self, pool: AsyncConnectionPool[AsyncConnection]) -> None:
        self.pool = pool

    async def create(self, approval: Approval) -> Approval:
        await self.save(approval)
        return approval

    async def save(self, approval: Approval) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO approvals VALUES (%s, %s, %s, %s) ON CONFLICT (approval_id) "
                "DO UPDATE SET status = EXCLUDED.status, body = EXCLUDED.body",
                (
                    approval.approval_id,
                    approval.status,
                    approval.created_at,
                    Jsonb(approval.model_dump(mode="json")),
                ),
            )

    async def get(self, approval_id: str) -> Approval | None:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT body FROM approvals WHERE approval_id = %s", (approval_id,))
            row = await cur.fetchone()
        return Approval.model_validate(row[0]) if row else None

    async def list(self, status: ApprovalStatus | None = None) -> list[Approval]:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            if status:
                await cur.execute(
                    "SELECT body FROM approvals WHERE status = %s ORDER BY created_at DESC",
                    (status,),
                )
            else:
                await cur.execute("SELECT body FROM approvals ORDER BY created_at DESC")
            return [Approval.model_validate(r[0]) for r in await cur.fetchall()]
