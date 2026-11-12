# 05. Retrieval Design

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Active specification |
| Owner | Prakhar Shukla |
| Last updated | 2026-11-12 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |
| 0.1.1 | Reranker runtime specified as the fastembed ONNX cross encoder, matching the implementation |

## Design goal

Find the few chunks that actually answer the question, in the right order, without leaking evidence the role is not allowed to see, and without paying full latency for questions already answered.

## Pipeline

```mermaid
flowchart LR
    Q[Standalone question] --> F[Role filter on metadata]
    F --> D[Dense search, FAISS top k]
    F --> S[Sparse search, BM25 top k]
    D --> U[Reciprocal rank fusion]
    S --> U
    U --> R[Cross encoder rerank]
    R --> P[Expand to parents]
    P --> E[Evidence blocks for generation]
```

Access filtering happens before scoring, on candidate metadata, never after. Post filtering results leaks information through relative ranking and counts; pre filtering means the restricted role never sees an out of scope document exist.

## Stage one: hybrid search

Dense and sparse retrieval run in parallel over the role filtered candidate set, each returning its own top k by similarity.

| Signal | Index | Strength | Weakness |
|---|---|---|---|
| Dense (bge-small over chunk plus contextual blurb) | FAISS, cosine | Paraphrase, conceptual questions | Weak on identifiers, exact figures, clause numbers |
| Sparse (BM25) | tokenized corpus | Exact terms, codes, numbers, names | No synonymy |

The contextual blurb from doc 04 is part of the embedded text, which anchors chunks that are ambiguous in isolation.

## Stage two: fusion

Reciprocal rank fusion merges the two lists. For each chunk, `score = sum over lists of 1 / (rrf_k + rank)` with `rrf_k = 60`, using only the ranks within each list. RRF is rank based, so no similarity scale calibration is needed between the two scorers, and a chunk appearing high in both lists dominates.

## Stage three: rerank

The fused top 20 goes through a local cross encoder (ms-marco MiniLM L 6 v2 via fastembed, ONNX) that scores each question and chunk pair jointly, which catches relevance that independent scoring misses. The top 5 survive. The reranker runs on CPU; at this corpus size the latency budget holds, and the design keeps a config switch for a hosted reranker later.

## Small to big expansion

Each surviving small chunk is replaced by its parent section for generation. Embedding precision comes from small chunks; reading fluency comes from parents. Citations still resolve to the small chunk's page range, so the citation stays precise even though the generator sees more text.

## Semantic cache

Before retrieval, the question embedding is compared against cached question embeddings from the same index version. A cosine similarity of 0.95 or higher is a hit: the cached answer is returned with a `cache_hit` marker in the response metadata and no model calls are made. Cache entries store their index version; any ingestion that changes content bumps the version and invalidates entries in one comparison.

## Configuration knobs and defaults

| Knob | Default | Notes |
|---|---|---|
| `dense_k` | 20 | per signal candidate count |
| `sparse_k` | 20 | per signal candidate count |
| `rrf_k` | 60 | fusion smoothing constant |
| `rerank_top_n` | 5 | evidence blocks presented for generation |
| `grade_threshold` | tuned on golden set | evidence relevance floor before generation |
| `cache_similarity` | 0.95 | question cache hit threshold |
| `chunk_target_tokens` | 300 | small chunk target |
| `parent_max_tokens` | 1200 | parent section ceiling |
| `contextualize_model` | Nova Micro | blurb writer |

## Failure behavior

If the role filtered candidate set is empty, or every fused candidate grades below the relevance floor, the pipeline goes to refusal directly. Retrieval never fabricates a candidate, and a permission block is reported as a permission block, not as no results, so the trace distinguishes the two.
