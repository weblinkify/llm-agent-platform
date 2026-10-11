import math
from collections import Counter

from rag.embeddings import _STOP, _TOKEN, _normalise


def tokenize(text: str) -> list[str]:
    return [_normalise(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25Index:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(doc.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        out: list[float] = []
        for doc, length in zip(self.docs, self.lengths, strict=True):
            score = 0.0
            for term in terms:
                tf = doc.get(term)
                if tf:
                    denom = tf + self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
                    score += self.idf[term] * tf * (self.k1 + 1) / denom
            out.append(score)
        return out
