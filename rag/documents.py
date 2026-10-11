import re
from pathlib import Path

from pypdf import PdfReader

from rag.models import Document

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_PDF_ID = re.compile(r"\((DOC-\d+)\)")
_WRAPPED_LINE = re.compile(r"(?<![.:!?])\n(?=[a-z0-9(])")


def _cells(line: str) -> list[str]:
    return [c.strip().strip("`") for c in line.strip().strip("|").split("|")]


def linearize_tables(text: str) -> str:
    """Rewrite markdown tables as one sentence per row ("P2: Acknowledge 30 minutes;
    Restore service 8 hours.") so rows stay meaningful after chunking and match
    keyword and semantic search."""
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if (
            lines[i].lstrip().startswith("|")
            and i + 1 < len(lines)
            and set(lines[i + 1]) <= set("|-: ")
        ):
            header = _cells(lines[i])
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                row = _cells(lines[i])
                pairs = "; ".join(f"{h} {v}" for h, v in zip(header[1:], row[1:], strict=False))
                out.append(f"- {row[0]}: {pairs}.")
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def _parse_markdown(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    if match := _FRONT_MATTER.match(raw):
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        raw = raw[match.end() :]
    return Document(
        doc_id=meta.get("id", path.stem),
        title=meta.get("title", path.stem.replace("-", " ").title()),
        category=meta.get("category", "general"),
        source=path.name,
        text=linearize_tables(raw.strip()),
    )


def _parse_pdf(path: Path) -> Document:
    raw = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
    text = _WRAPPED_LINE.sub(" ", raw)
    first_line = text.splitlines()[0] if text else path.stem
    id_match = _PDF_ID.search(first_line)
    return Document(
        doc_id=id_match.group(1) if id_match else path.stem,
        title=_PDF_ID.sub("", first_line).strip(),
        category="pdf",
        source=path.name,
        text=text,
    )


def load_documents(directory: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(directory.iterdir()):
        if path.suffix == ".md":
            documents.append(_parse_markdown(path))
        elif path.suffix == ".pdf":
            documents.append(_parse_pdf(path))
    return documents
