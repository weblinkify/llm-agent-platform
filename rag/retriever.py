from rag.bm25 import BM25Index
from rag.embeddings import Embedder
from rag.models import Chunk, RetrievalResult, ScoredChunk, embedding_text
from rag.rerank import Reranker
from rag.store import VectorStore

RRF_K = 60


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank + 1)
    return fused


class HybridRetriever:
    """BM25 + vector search merged with reciprocal rank fusion, optional
    cross-encoder rerank, a similarity gate and prompt-injection quarantine."""

    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        *,
        min_similarity: float,
        candidates: int = 20,
        reranker: Reranker | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.min_similarity = min_similarity
        self.candidates = candidates
        self.reranker = reranker
        self._chunks: list[Chunk] = []
        self._bm25: BM25Index | None = None

    async def refresh(self) -> None:
        self._chunks = await self.store.all_chunks()
        self._bm25 = BM25Index([f"{c.title}\n{c.text}" for c in self._chunks])

    async def retrieve(self, query: str, top_k: int = 4) -> RetrievalResult:
        if self._bm25 is None:
            await self.refresh()
        assert self._bm25 is not None
        query_vec = (await self.embedder.embed([query]))[0]
        vector_hits = await self.store.search(query_vec, self.candidates)
        similarity = {c.chunk_id: s for c, s in vector_hits}

        bm25_scores = self._bm25.scores(query)
        bm25_by_id = {c.chunk_id: s for c, s in zip(self._chunks, bm25_scores, strict=True)}
        bm25_ranking = [
            cid
            for cid, s in sorted(bm25_by_id.items(), key=lambda kv: kv[1], reverse=True)
            if s > 0
        ][: self.candidates]

        fused = reciprocal_rank_fusion([[c.chunk_id for c, _ in vector_hits], bm25_ranking])
        by_id = {c.chunk_id: c for c in self._chunks} | {c.chunk_id: c for c, _ in vector_hits}
        missing = [cid for cid in fused if cid not in similarity]
        if missing:
            vectors = await self.embedder.embed([embedding_text(by_id[cid]) for cid in missing])
            for cid, vec in zip(missing, vectors, strict=True):
                similarity[cid] = float(vec @ query_vec)

        ranked = [
            ScoredChunk(by_id[cid], score, similarity[cid], bm25_by_id.get(cid, 0.0))
            for cid, score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        ]
        best = max((s.similarity for s in ranked), default=0.0)
        floor = self.min_similarity * 0.6
        relevant = [s for s in ranked if s.similarity >= floor]

        if self.reranker and relevant:
            pool = relevant[: self.candidates]
            scores = await self.reranker.score(query, [s.chunk.text for s in pool])
            relevant = [
                ScoredChunk(s.chunk, s.score, s.similarity, s.bm25, r)
                for s, r in sorted(zip(pool, scores, strict=True), key=lambda p: p[1], reverse=True)
            ]

        trusted = [s for s in relevant if not s.chunk.suspicious]
        quarantined = [s for s in relevant[: top_k * 2] if s.chunk.suspicious]
        return RetrievalResult(
            chunks=trusted[:top_k],
            quarantined=quarantined,
            best_similarity=best,
            sufficient=best >= self.min_similarity and bool(trusted),
        )
