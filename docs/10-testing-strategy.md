# 10. Testing Strategy

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

## Layers

| Layer | Scope | Model provider | Runs |
|---|---|---|---|
| Unit | chunker boundaries, RRF ordering, attribution splitter, numeric guard, cache threshold, schemas, role resolution | none, pure functions | every push |
| Integration | full pipeline over a synthetic mini corpus with a stub provider | fake provider implementing the same interface | every push |
| End to end smoke | real provider, one ingest and one chat over the real corpus | real Bedrock | nightly and manual, explicitly marked |

The fake provider returns deterministic, fixture driven responses (a fixed rewrite, fixed grades, a draft answer built from fixture evidence), so integration tests never pay for or depend on a live model and are reproducible byte for byte.

## Fixtures

Tests never download anything. A tiny 3 page PDF fixture is constructed in test code (a minimal valid PDF with known text per page), giving deterministic chunk ids, page ranges and section paths. Corpus scale paths are exercised with the fixture duplicated under different titles.

## Coverage policy

- Coverage gate: **85 percent** on the application package, enforced in CI.
- The attribution verifier, role filter and refusal paths get targeted tests because they are the trust boundary: each refusal condition and each permission leak scenario has a named test.
- Type checking with mypy and lint with ruff run alongside tests.

## Concurrency and streaming

The SSE path is tested with an HTTP client against a running app instance: event order (tokens before citations before meta), terminal event always present, and client disconnect mid stream leaves a valid trace. Session store behavior is tested under sequential requests with a fresh event loop per test.

## What is deliberately not tested

- Model quality (that is the evaluation suite's job, doc 09).
- Provider availability beyond the health check.
- UI rendering internals; the UI has one smoke test that it starts and posts a question.

## CI wiring

`ci.yml` runs lint, types, unit and integration on every push and pull request. The evaluation smoke subset runs after they pass. The nightly workflow runs the full evaluation suite and the end to end smoke against the real corpus. Test runtime for the push path stays under three minutes.
