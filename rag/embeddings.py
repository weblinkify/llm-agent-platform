import hashlib
import math
import re
from itertools import pairwise
from typing import Protocol

import numpy as np
import numpy.typing as npt

from core.settings import Settings

Vector = npt.NDArray[np.float32]

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "to",
        "of",
        "in",
        "on",
        "for",
        "and",
        "or",
        "what",
        "which",
        "who",
        "how",
        "when",
        "why",
        "does",
        "do",
        "did",
        "can",
        "could",
        "i",
        "we",
        "you",
        "it",
        "its",
        "this",
        "that",
        "with",
        "by",
        "at",
        "from",
        "as",
        "our",
        "your",
        "my",
        "me",
        "about",
        "there",
        "any",
        "all",
        "must",
        "should",
        "will",
        "would",
        "not",
        "no",
        "if",
        "than",
        "then",
        "into",
    ]
)


class Embedder(Protocol):
    name: str
    dim: int

    async def embed(self, texts: list[str]) -> Vector: ...


def _normalise(token: str) -> str:
    """Light suffix stripping so 'restored'/'restore' and 'activation'/'activate' match."""
    for suffix in ("ing", "ion", "ies", "ed", "es", "s", "e"):
        if len(token) >= len(suffix) + 4 and token.endswith(suffix):
            return token[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return token


class HashingEmbedder:
    """Offline embedding: hashed bag of normalised words, bigrams and character
    trigrams. Deterministic and dependency-free, so the demo and CI need no keys.
    Swap for `OpenAIEmbedder` in production (see ADR-0003)."""

    name = "hashing-v1"

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    def _features(self, text: str) -> dict[str, float]:
        words = [_normalise(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]
        feats: dict[str, float] = {}
        for word in words:
            feats[f"w:{word}"] = feats.get(f"w:{word}", 0.0) + 1.0
            padded = f"#{word}#"
            for i in range(len(padded) - 2):
                key = f"c:{padded[i : i + 3]}"
                feats[key] = feats.get(key, 0.0) + 0.25
        for a, b in pairwise(words):
            feats[f"b:{a}_{b}"] = feats.get(f"b:{a}_{b}", 0.0) + 0.5
        return feats

    def embed_one(self, text: str) -> Vector:
        vec = np.zeros(self.dim, dtype=np.float32)
        for feat, count in self._features(text).items():
            digest = hashlib.blake2b(feat.encode(), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[idx] += sign * (1.0 + math.log(count)) if count >= 1 else sign * count
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec

    async def embed(self, texts: list[str]) -> Vector:
        return (
            np.stack([self.embed_one(t) for t in texts])
            if texts
            else np.zeros((0, self.dim), np.float32)
        )


class OpenAIEmbedder:
    def __init__(self, settings: Settings) -> None:
        if settings.embedding_provider == "azure_openai":
            from langchain_openai import AzureOpenAIEmbeddings

            self._client: object = AzureOpenAIEmbeddings(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key or None,  # type: ignore[arg-type]
                api_version=settings.azure_openai_api_version,
                azure_deployment=settings.azure_openai_embedding_deployment,
            )
        else:
            from langchain_openai import OpenAIEmbeddings

            self._client = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key or None,  # type: ignore[arg-type]
            )
        self.name = settings.embedding_model
        self.dim = 1536

    async def embed(self, texts: list[str]) -> Vector:
        vectors = await self._client.aembed_documents(texts)  # type: ignore[attr-defined]
        arr: Vector = np.asarray(vectors, dtype=np.float32)
        normalised: Vector = arr / np.linalg.norm(arr, axis=1, keepdims=True)
        return normalised


def create_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "hashing":
        return HashingEmbedder()
    return OpenAIEmbedder(settings)
