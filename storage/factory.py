from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from core.settings import Settings
from rag.embeddings import Embedder, create_embedder
from rag.store import InMemoryVectorStore, VectorStore
from storage.memory import InMemoryApprovalStore, InMemoryAuditLog
from storage.protocols import ApprovalStore, AuditLog


@dataclass
class Backends:
    vector_store: VectorStore
    embedder: Embedder
    audit_log: AuditLog
    approvals: ApprovalStore
    checkpointer: BaseCheckpointSaver[str]
    kind: str


@asynccontextmanager
async def open_backends(settings: Settings) -> AsyncIterator[Backends]:
    """In-memory backends when DATABASE_URL is empty (demo, tests, serverless);
    Postgres + pgvector + LangGraph Postgres checkpointer otherwise."""
    embedder = create_embedder(settings)
    if not settings.database_url:
        yield Backends(
            InMemoryVectorStore(),
            embedder,
            InMemoryAuditLog(),
            InMemoryApprovalStore(),
            InMemorySaver(),
            "memory",
        )
        return

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    from rag.pgvector_store import PgVectorStore
    from storage.postgres import PostgresApprovalStore, PostgresAuditLog, migrate

    conninfo = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    async with await AsyncConnection.connect(conninfo, autocommit=True) as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    pool: AsyncConnectionPool[AsyncConnection] = AsyncConnectionPool(
        conninfo,
        open=False,
        kwargs={"autocommit": True},
        configure=PgVectorStore.configure,
    )
    # LangGraph's saver needs dict rows, so it gets its own small pool.
    checkpoint_pool: AsyncConnectionPool[AsyncConnection] = AsyncConnectionPool(
        conninfo,
        open=False,
        max_size=4,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open()
    await checkpoint_pool.open()
    try:
        await migrate(pool)
        store = PgVectorStore(pool, embedder.dim)
        await store.migrate()
        checkpointer = AsyncPostgresSaver(checkpoint_pool)  # type: ignore[arg-type]
        await checkpointer.setup()
        yield Backends(
            store,
            embedder,
            PostgresAuditLog(pool),
            PostgresApprovalStore(pool),
            checkpointer,
            "postgres",
        )
    finally:
        await checkpoint_pool.close()
        await pool.close()
