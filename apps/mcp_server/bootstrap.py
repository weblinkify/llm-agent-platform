from core.settings import Settings
from rag.embeddings import Embedder
from rag.ingest import ingest
from rag.rerank import CrossEncoderReranker, Reranker
from rag.retriever import HybridRetriever
from rag.store import VectorStore
from services.enterprise import EnterpriseSystems


async def build_retriever(
    store: VectorStore, embedder: Embedder, settings: Settings
) -> HybridRetriever:
    """Seed the store from data/documents if empty, then build the hybrid index."""
    if await store.count() == 0:
        await ingest(settings.documents_dir, store, embedder, settings)
    reranker: Reranker | None = (
        CrossEncoderReranker(settings.reranker_model) if settings.reranker_model else None
    )
    retriever = HybridRetriever(
        store,
        embedder,
        min_similarity=settings.min_similarity,
        candidates=settings.retrieval_candidates,
        reranker=reranker,
    )
    await retriever.refresh()
    return retriever


def load_enterprise(settings: Settings) -> EnterpriseSystems:
    return EnterpriseSystems(settings.enterprise_data_dir)
