# 12 Roadmap

## Document Control

| Field | Value |
|---|---|
| Version | 0.2.0 |
| Status | Active specification |
| Owner | Prakhar Shukla |
| Last updated | 2026-11-12 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft, capability order |
| 0.2.0 | Restructured into phase gated P0 to P7 with acceptance criteria and status table |
| 0.2.1 | P1 accepted with measured results; checklist updated to the delivered corpus and batching |
| 0.2.2 | P2 accepted; retrieval runtime choices documented |
| 0.2.3 | P3 accepted; generator pinned to the inference profile |
| 0.2.4 | P4 accepted; console replaced the planned Streamlit client with a Next.js app per owner direction |

Source of truth for progress. Check a box only when its acceptance criteria are met, and keep the status table at the bottom in sync. Build protocol per CLAUDE.md: build the phase scope only, verify (lint, types, tests, phase acceptance), one commit, one push, report, then wait for the owner's explicit go before the next phase.

## P0: repository, docs, scaffold

- [x] git init, .gitignore, MIT LICENSE, README stub with document table
- [x] docs suite 01 to 12: problem statement, product requirements, architecture, data design, retrieval design, grounding, API spec, security, evaluation design, testing strategy, tech stack, roadmap
- [x] project brief with assignment verbatim, option rationale and hard constraints (this file set)
- [x] document control tables and changelog sections on every document
- [x] CLAUDE.md engineering constitution
- [x] docs/what-broke.md failure log created

Acceptance: the documentation suite alone describes a buildable system; every assignment requirement maps to a design; hard constraints recorded. Met 2026-11-12.

## P1: corpus and ingestion

Goal: public corpus committed with sources, and a tested pipeline that turns PDFs into contextual chunks and indexes them.

- [x] Corpus: 6 public PDFs (financial statements, business narrative, regulatory standards text, two technical whitepapers, operations and procedure manual), each under 20 MB, committed under `data/corpus/` with `SOURCES.md` recording source, license and retrieval date
- [x] `scripts/fetch_corpus.py`: reproducible download with source manifest and per slot candidate URLs
- [x] Extraction with page maps (pymupdf4llm)
- [x] Section aware chunking: small chunks around 300 tokens with line aligned overlap, parents up to 1200 tokens
- [x] Contextual blurbs via Nova Micro in batches of ten, cached by chunk text hash
- [x] SHA-256 idempotency: re ingest of identical content is a reported no op; changed content retires the old document id and bumps the index version
- [x] Indexes: FAISS (bge-small via fastembed), BM25 artifact, metadata JSONL, manifest with index version
- [x] `make setup` and `make ingest` targets pinned to the project virtualenv
- [x] Unit tests for chunker, spend meter, manifest; integration tests on fixture PDFs with the fake provider, including a regression test for the changed document case

Acceptance: `make ingest` runs green on the corpus (6 documents, 1,817 chunks, 0.018 USD), a second run reports every document unchanged with zero new provider calls, `py -3.12 -m pytest` green (19 tests), lint and mypy clean. Met 2026-11-12.

## P2: retrieval engine

Goal: a callable, tested retrieval layer with access control, hybrid search and caching, provable before any UI exists.

- [x] Role resolution and metadata filter applied before scoring (pre filter via FAISS ID selector and restricted BM25 ranking, never post filter)
- [x] Dense (FAISS) and sparse (BM25) search with reciprocal rank fusion
- [x] Local cross encoder rerank (fastembed ONNX ms-marco MiniLM) to top 5 evidence blocks
- [x] Small to big parent expansion, citations resolved to small chunk pages
- [x] Semantic cache on question embeddings with index version invalidation
- [x] Standalone CLI to query retrieval without generation, with hybrid, dense and bm25 modes and a no rerank switch for baselines
- [x] Unit tests for RRF ordering, role semantics and cache threshold; integration tests for role scoping, modes and top n on the fixture index

Acceptance: retrieval callable standalone on the corpus (the Apple net sales query ranks the consolidated statements first), dense only and no rerank baselines measurable from the CLI, 36 tests green, lint and mypy clean. Met 2026-11-13.

## P3: grounded pipeline

Goal: the full LangGraph pipeline with memory, grading, generation, sentence level attribution and refusal.

- [x] LangGraph state graph: condense, retrieve, grade, generate, attribute, finalize, with conditional refusal short circuits
- [x] SQLite session store: sessions persist across restarts, recent turns window plus standalone rewrite of follow up questions
- [x] Grading gate: irrelevant evidence short circuits to refusal
- [x] Generation with numbered evidence blocks and inline citations (Llama 3.3 70B via its inference profile)
- [x] Sentence level attribution with the numeric consistency guard; unsupported and uncited sentences removed; empty result refuses
- [x] Refusal templates for: no relevant evidence, insufficient support, unsupported draft, permission denied
- [x] Prompt module with versions, prompts never embed document content outside evidence slots
- [x] Integration tests on the fake provider: follow up persistence, unsupported sentence stripping, numeric guard, uncited sentence drop, each refusal path, session isolation

Acceptance: 50 tests green including every refusal path and a multi turn chain, no real provider calls in tests; real provider smoke produced a grounded Apple answer (total net sales and services segment, verified sentence by sentence) and a working follow up through session memory. Met 2026-11-13.

## P4: service and console

Goal: the API contract of doc 07 served live, with the Streamlit client demonstrating it.

- [x] FastAPI: health, ingest, chat (SSE), sessions list, history, delete, trace tail
- [x] JSONL trace writer with stage latencies and verdicts per request
- [x] Rate limiting and the full error contract per doc 07
- [x] Next.js console (app router, tailwind): streaming tokens, citations with page numbers, refusal states, role picker, live trace panel
- [x] API tests with HTTP client: SSE event order, error codes, rate limit, upload ingestion, traces

Acceptance: `make api` and the console dev server serve the full demo; live smoke over real providers streamed a cited Apple answer through SSE; 58 tests green, lint and mypy clean. Met 2026-11-13.

## P5: evaluation gate and CI

Goal: measured quality as a build gate, the differentiator almost nobody else ships.

- [ ] Golden set: 30 questions across the six categories of doc 09
- [ ] Runner with per question verdicts, metric tables and config fingerprint
- [ ] Attribution micro benchmark: 20 labeled sentence and chunk pairs
- [ ] Baselines: dense only and no rerank, published beside the main numbers
- [ ] `ci.yml`: lint, types, unit, integration, eval smoke subset
- [ ] `nightly.yml`: full evaluation and end to end smoke
- [ ] Coverage gate 85 percent enforced

Acceptance: CI green on push, smoke gates pass, full report generated into `evals/report.md`.

## P6: polish

Goal: the package the evaluator actually reads first.

- [ ] README rewrite: banner, badges, demo video above the fold, 30 second version, architecture diagram, measured results, honest limitations, quickstart
- [ ] Branding assets: banner, favicon, consistent palette
- [ ] `INTERVIEW-PREP.md` for the owner
- [ ] Final `docs/what-broke.md` review
- [ ] Fresh clone walkthrough following only the README

Acceptance: a fresh clone reaches a cited conversation in under 10 minutes using only the README.

## P7: submission

Goal: convert the work into the application.

- [ ] Secrets sweep: no tokens or account identifiers anywhere, git history included
- [ ] Owner makes the repository public
- [ ] Form answers drafted for both forms (ratings ML 8, DL 7, GenAI 9, experience 0-2, graduation 2026, relocate yes)
- [ ] Both forms submitted with the repository link

Acceptance: both forms submitted with a working, accessible repository.

## Status table

| Phase | Status | Notes |
|---|---|---|
| P0 | Done | Docs suite, brief, control tables, constitution, 2026-11-12 |
| P1 | Done | Corpus 6 docs 28.4 MB, ingestion 1,817 chunks, 0.018 USD, idempotent re run verified, 2026-11-12 |
| P2 | Done | Hybrid retrieval, fusion, rerank, role filter, cache, CLI baselines verified on corpus, 2026-11-13 |
| P3 | Done | LangGraph pipeline, memory, attribution, refusal paths; real smoke verified, 2026-11-13 |
| P4 | Done | FastAPI SSE service + Next.js console; live smoke verified on real providers, 2026-11-13 |
| P5 | Not started | Evaluation gate and CI |
| P6 | Not started | Polish |
| P7 | Not started | Submission, deadline 2026-11-15 |
