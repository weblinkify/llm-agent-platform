import asyncio
from typing import Protocol


class Reranker(Protocol):
    async def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    """Cross-encoder reranking (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`).
    Requires the `rerank` extra; enabled by setting RERANKER_MODEL."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    async def score(self, query: str, passages: list[str]) -> list[float]:
        pairs = [(query, p) for p in passages]
        scores = await asyncio.to_thread(self._model.predict, pairs)
        return [float(s) for s in scores]
