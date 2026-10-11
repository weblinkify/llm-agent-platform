from typing import cast

import numpy as np
from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection, sql
from psycopg_pool import AsyncConnectionPool

from rag.embeddings import Vector
from rag.models import Chunk

_COLUMNS = "chunk_id, doc_id, title, section, text, source, suspicious, injection_rules"


def _row_to_chunk(row: tuple[object, ...]) -> Chunk:
    return Chunk(
        chunk_id=str(row[0]),
        doc_id=str(row[1]),
        title=str(row[2]),
        section=str(row[3]),
        text=str(row[4]),
        source=str(row[5]),
        suspicious=bool(row[6]),
        injection_rules=tuple(cast(list[str], row[7] or [])),
    )


class PgVectorStore:
    """pgvector-backed store with an HNSW cosine index."""

    def __init__(self, pool: AsyncConnectionPool[AsyncConnection], dim: int) -> None:
        self.pool = pool
        self.dim = dim

    @staticmethod
    async def configure(conn: AsyncConnection) -> None:
        await register_vector_async(conn)

    async def migrate(self) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        section TEXT NOT NULL,
                        text TEXT NOT NULL,
                        source TEXT NOT NULL,
                        suspicious BOOLEAN NOT NULL DEFAULT FALSE,
                        injection_rules TEXT[] NOT NULL DEFAULT '{{}}',
                        embedding vector({dim}) NOT NULL
                    )
                    """
                ).format(dim=sql.Literal(self.dim))
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx "
                "ON rag_chunks USING hnsw (embedding vector_cosine_ops)"
            )

    async def upsert(self, chunks: list[Chunk], vectors: Vector) -> None:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.executemany(
                f"INSERT INTO rag_chunks ({_COLUMNS}, embedding) "  # noqa: S608  # nosec B608 - constant column list, values are parameterised
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (chunk_id) DO UPDATE SET text = EXCLUDED.text, "
                "title = EXCLUDED.title, section = EXCLUDED.section, "
                "suspicious = EXCLUDED.suspicious, injection_rules = EXCLUDED.injection_rules, "
                "embedding = EXCLUDED.embedding",
                [
                    (
                        c.chunk_id,
                        c.doc_id,
                        c.title,
                        c.section,
                        c.text,
                        c.source,
                        c.suspicious,
                        list(c.injection_rules),
                        np.asarray(v, dtype=np.float32),
                    )
                    for c, v in zip(chunks, vectors, strict=True)
                ],
            )

    async def search(self, query: Vector, k: int) -> list[tuple[Chunk, float]]:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_COLUMNS}, 1 - (embedding <=> %s) AS similarity "  # noqa: S608  # nosec B608 - constant column list, values are parameterised
                "FROM rag_chunks ORDER BY embedding <=> %s LIMIT %s",
                (
                    np.asarray(query, dtype=np.float32),
                    np.asarray(query, dtype=np.float32),
                    k,
                ),
            )
            rows = await cur.fetchall()
        return [(_row_to_chunk(r), float(r[8])) for r in rows]

    async def all_chunks(self) -> list[Chunk]:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(f"SELECT {_COLUMNS} FROM rag_chunks ORDER BY chunk_id")  # noqa: S608  # nosec B608 - constant column list, values are parameterised
            return [_row_to_chunk(r) for r in await cur.fetchall()]

    async def count(self) -> int:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT count(*) FROM rag_chunks")
            row = await cur.fetchone()
            return int(row[0]) if row else 0
