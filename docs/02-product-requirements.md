# 02. Product Requirements

## Personas

| Persona | What they do | What they need |
|---|---|---|
| Knowledge analyst | Asks business and technical questions across a document set | Accurate answers with citations they can open and verify |
| Reviewer | Audits the system's trustworthiness | Visible evidence trail, refusal honesty, per request trace |
| Operator | Ingests and maintains the corpus | Idempotent ingestion, index status, clear errors |

## Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | Ingest multiple PDF documents in one call and report per document status |
| FR-02 | Re ingesting an identical document is a no op, detected by SHA-256 content hash |
| FR-03 | Answers are produced from retrieved evidence only, with inline citations in `[n]` form |
| FR-04 | Each citation resolves to document title, page range and section path |
| FR-05 | Every factual sentence in an answer is verified against its cited chunk; unsupported sentences are removed |
| FR-06 | Questions the corpus cannot answer are refused with an explicit message, not answered from model memory |
| FR-07 | Follow up questions resolve references from conversation history without the user restating context |
| FR-08 | Session history persists across service restarts |
| FR-09 | Documents carry access tags and requests carry a role; retrieval filters evidence by role before scoring |
| FR-10 | Answers stream token by token; citations and sources arrive as structured events |
| FR-11 | Semantically repeated questions are served from a cache and marked as cache hits |
| FR-12 | Every request writes a trace record with latency, token usage and verdicts |

## Non functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | First token latency (cache miss) | under 2.5 s at p95 |
| NFR-02 | Full answer latency (cache miss, 5 evidence blocks) | under 15 s at p95 |
| NFR-03 | Cache hit answer latency | under 1 s at p95 |
| NFR-04 | Cost per answer | under USD 0.01 on the default routing |
| NFR-05 | Reproducibility | pinned dependencies, deterministic eval harness with recorded model versions |
| NFR-06 | Portability | provider abstraction; the same code runs on Bedrock, Ollama or any OpenAI compatible endpoint via environment config |
| NFR-07 | Observability | one JSONL trace line per request, human readable summary per session |

## Non goals

- OCR of scanned or image only PDFs. The corpus is text based by design; scale out handling is described in the roadmap (doc 12).
- Multi tenant index isolation at cloud scale. Access control is modeled at the document and role level inside one deployment.
- Fine tuning or continued pretraining. Retrieval quality comes from chunking, hybrid search and reranking, not weight changes.
- Connectors to live systems (SharePoint, Confluence). The roadmap describes the path; this delivery uses explicit PDF ingestion.

## Acceptance criteria

The release is accepted when the evaluation suite (doc 09) passes its gates on the golden set, the API contract (doc 07) is covered by tests (doc 10), and a cold start run of the quickstart reproduces the demo session end to end.
