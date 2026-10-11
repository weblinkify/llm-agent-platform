import asyncio
import logging
from pathlib import Path

from core.settings import Settings, get_settings
from rag.chunking import chunk_document
from rag.documents import load_documents
from rag.embeddings import Embedder
from rag.models import embedding_text
from rag.store import VectorStore

log = logging.getLogger(__name__)


async def ingest(
    directory: Path, store: VectorStore, embedder: Embedder, settings: Settings
) -> int:
    documents = load_documents(directory)
    chunks = [
        chunk
        for doc in documents
        for chunk in chunk_document(doc, settings.chunk_size, settings.chunk_overlap)
    ]
    vectors = await embedder.embed([embedding_text(c) for c in chunks])
    await store.upsert(chunks, vectors)
    flagged = [c.chunk_id for c in chunks if c.suspicious]
    log.info(
        "ingested documents",
        extra={
            "documents": len(documents),
            "chunks": len(chunks),
            "quarantined": flagged,
        },
    )
    return len(chunks)


def main() -> None:
    """CLI: ingest data/documents into the configured store (pgvector if DATABASE_URL)."""
    from storage.factory import open_backends

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    async def run() -> None:
        async with open_backends(settings) as backends:
            count = await ingest(
                settings.documents_dir,
                backends.vector_store,
                backends.embedder,
                settings,
            )
            print(f"Ingested {count} chunks from {settings.documents_dir}")

    asyncio.run(run())
