from typing import Protocol

import numpy as np

from rag.embeddings import Vector
from rag.models import Chunk


class VectorStore(Protocol):
    async def upsert(self, chunks: list[Chunk], vectors: Vector) -> None: ...

    async def search(self, query: Vector, k: int) -> list[tuple[Chunk, float]]: ...

    async def all_chunks(self) -> list[Chunk]: ...

    async def count(self) -> int: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._vectors: dict[str, Vector] = {}

    async def upsert(self, chunks: list[Chunk], vectors: Vector) -> None:
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._chunks[chunk.chunk_id] = chunk
            self._vectors[chunk.chunk_id] = vector

    async def search(self, query: Vector, k: int) -> list[tuple[Chunk, float]]:
        if not self._chunks:
            return []
        ids = list(self._chunks)
        matrix = np.stack([self._vectors[i] for i in ids])
        sims = matrix @ query
        order = np.argsort(-sims)[:k]
        return [(self._chunks[ids[i]], float(sims[i])) for i in order]

    async def all_chunks(self) -> list[Chunk]:
        return list(self._chunks.values())

    async def count(self) -> int:
        return len(self._chunks)
