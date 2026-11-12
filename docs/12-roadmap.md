# 12. Roadmap

## Delivery plan

Capabilities land in vertical slices, each slice committed and green in CI before the next begins. The order below is dependency order; each entry describes user visible capability, not internal phases.

| Order | Capability | What exists when it lands |
|---|---|---|
| 1 | Documentation suite | This document set, repository scaffold, conventions |
| 2 | Ingestion | PDFs to contextual chunks to indexed store, idempotent, with an ingest command |
| 3 | Retrieval engine | Role filtered hybrid search with fusion, rerank and parent expansion, callable standalone |
| 4 | Grounded pipeline | Full graph with memory, grading, generation, sentence attribution and refusal |
| 5 | Service and UI | FastAPI with streaming sessions and the Streamlit chat client |
| 6 | Evaluation gate | Golden set harness, report generation, CI wiring, coverage gates |
| 7 | Polish | README with diagram and demo video, branding assets, deployment notes |

## Production scale out path

The items below are out of scope for this delivery (doc 02) and are documented as the path a production deployment would take:

| Area | Approach |
|---|---|
| Multi tenant isolation | Per tenant index namespaces or separate collections; tenant resolved at request time from identity, never from request body |
| OCR and scans | Fallback extraction with OCR for image only pages, flagged chunks with lower trust metadata |
| Connector sync | Scheduled incremental ingestion from document stores with permission sync on change, reusing the sha256 idempotency model |
| Canary and A/B | Two index versions side by side with traffic splitting on the chat route, evaluation gates as promotion criteria |
| Serving the reranker | GPU hosted cross encoder or hosted reranking service behind the same interface when corpus size outgrows CPU latency |
| Orchestration | Containerized deployment behind a queue based ingestion worker; the current single service design keeps this a packaging change, not a rewrite |
| Observability | Trace records already structured for ingestion into an external observability backend |

## Risks and open questions

| Risk | Mitigation |
|---|---|
| Contextualization cost at scale | Blurbs are cached by chunk text hash; re ingestion recontextualizes only new chunks. At larger corpus scale, blurbs are computed in batch jobs off the request path |
| CPU rerank latency growth | rerank_top_n and candidate limits are configuration; the interface accepts a hosted reranker without code change |
| Corpus growth | Ingestion is per document idempotent; index version invalidation keeps cache correctness independent of corpus size |
| Judge drift | Attribution micro benchmark (doc 09) catches verifier regression independently of answer quality |

## Immediate next steps

Land capability 2: the ingestion pipeline with its command line entry point, tests and fixtures, followed by capability 3 as a callable retrieval engine before any UI exists, so every layer is provable in isolation.
