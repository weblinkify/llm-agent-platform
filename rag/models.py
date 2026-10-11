from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    category: str
    source: str
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    source: str
    suspicious: bool = False
    injection_rules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float
    similarity: float
    bm25: float
    rerank: float | None = None


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[ScoredChunk]
    quarantined: list[ScoredChunk]
    best_similarity: float
    sufficient: bool


def embedding_text(chunk: Chunk) -> str:
    return f"{chunk.title}\n{chunk.section}\n{chunk.text}"
