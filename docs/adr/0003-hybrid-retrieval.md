# ADR-0003: Hybrid retrieval with RRF, a similarity gate and offline embeddings

**Status:** accepted

## Context

Ops questions mix exact identifiers (`P2`, `INC-1003`, `MOB-5G-PLUS`, `l2-fixed-access`) with paraphrased language ("how fast must it be fixed"). Pure vector search misses exact tokens, and pure keyword search misses paraphrases. A wrong but confident answer is worse than none.

## Decision

* BM25 and vector search, merged with **reciprocal rank fusion** (k=60), which needs no score calibration between the two retrievers.
* An optional cross-encoder reranker (`RERANKER_MODEL`).
* A **similarity gate**: if the best chunk is below `MIN_SIMILARITY`, the agent says it lacks context.
* **Table linearisation** at ingestion, so table rows stay meaningful after chunking (found by the evals).
* The **offline hashing embedder** is the default, so the demo and CI need no keys. OpenAI or Azure embeddings are a setting.

## Consequences

* Out-of-domain questions are refused (3/3 in the evals).
* Hashing embeddings are weaker semantically. One eval case (`rag-02`) misses because of them, and that is reported, not hidden. `MIN_SIMILARITY` must be recalibrated when the embedding model changes (about 0.3 for `text-embedding-3-small`).
