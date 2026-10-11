import re

from rag.models import Chunk, Document
from security.injection import scan

SEPARATORS = ["\n## ", "\n\n", "\n", ". ", " "]
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.M)


def split_text(
    text: str, chunk_size: int, overlap: int, separators: list[str] | None = None
) -> list[str]:
    """Recursive splitter: try coarse separators first, fall back to finer ones,
    then merge adjacent pieces up to `chunk_size` with `overlap` characters."""
    separators = SEPARATORS if separators is None else separators
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    sep, *rest = separators or [""]
    parts = text.split(sep) if sep else list(text)
    pieces: list[str] = []
    for i, part in enumerate(parts):
        piece = (sep.lstrip("\n") if i and sep.startswith("\n#") else "") + part
        if len(piece) > chunk_size and rest:
            pieces.extend(split_text(piece, chunk_size, overlap, rest))
        elif piece.strip():
            pieces.append(piece)
    joiner = sep if not sep.startswith("\n#") else "\n"
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}{joiner}{piece}" if current else piece
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap else ""
            current = (
                f"{tail}{joiner}{piece}" if tail and len(tail) + len(piece) < chunk_size else piece
            )
        else:
            current = piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


def chunk_document(doc: Document, chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for i, text in enumerate(split_text(doc.text, chunk_size, overlap)):
        headings = _HEADING.findall(text)
        verdict = scan(text)
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{i}",
                doc_id=doc.doc_id,
                title=doc.title,
                section=headings[0] if headings else doc.title,
                text=text,
                source=doc.source,
                suspicious=verdict.suspicious,
                injection_rules=tuple(verdict.rules),
            )
        )
    return chunks
