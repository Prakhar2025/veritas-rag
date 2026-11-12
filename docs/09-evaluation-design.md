# 09. Evaluation Design

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
| 0.1.1 | Metric clarified: the gated number is the draft support rate; delivered precision is 1.0 by construction; CI smoke runs offline over a fixture world with behavior gates |

## Principle

A RAG system is only as good as its measured behavior on questions that matter, including the ones it should refuse. The evaluation suite is a gate, not a decoration: it runs in CI and blocks the build when quality regresses.

## Golden set

Thirty questions written against the demo corpus, each with the expected behavior recorded:

| Category | Count | Example shape |
|---|---|---|
| Single document factual | 10 | "What was the operating margin in FY2025?" |
| Multi document synthesis | 4 | "Compare the margin trend with the industry outlook in the business report." |
| Table and figure questions | 4 | Numbers that only appear in tables, exact figures and units |
| Follow up chains | 4 | Second turn questions ("summarize that for a CFO") that require memory |
| Out of scope | 4 | Questions the corpus cannot answer; refusal expected |
| Permission denied | 4 | Answerable questions asked under a restricted role; denial expected |

Out of scope and permission categories exist because honest refusal and access enforcement are features with their own accuracy bars. "Should return nothing" cases are the standard failure mode of unmeasured RAG systems.

## Metrics

| Metric | Definition | Gate |
|---|---|---|
| Retrieval recall@5 | answerable questions where a supporting chunk is in the top 5 evidence blocks | at least 0.85 |
| Retrieval MRR | mean reciprocal rank of the first supporting chunk | reported |
| Draft support rate | generated sentences that survive verification; delivered citation precision is 1.0 by construction because unsupported sentences are stripped | at least 0.75 |
| Refusal accuracy | correct refusals over out of scope questions | 4 of 4 |
| Permission accuracy | correct denials over restricted role questions, with zero evidence leaks | 4 of 4, zero leaks |
| Groundedness | LLM judge score, 1 to 5, on delivered answers | mean at least 4.0 |
| Latency | p50 and p95 per stage and end to end | reported, targets in doc 02 |
| Cost | USD per answer on default routing | reported, target under 0.01 |

The judge for groundedness is the cheap grading model with a fixed rubric prompt, and its verdicts are recorded per question so disagreements are auditable.

## Gates and cadence

- **Per push:** a 10 question smoke subset runs in CI. Gates: recall@5, citation precision, permission accuracy.
- **Full suite:** manual or nightly; produces `evals/report.md` with metric tables per category, per question verdicts and config fingerprint (model ids, prompt versions, index version).
- A gate failure blocks merge. The report is regenerated, never hand edited.

## Attribution micro benchmark

The sentence attribution gate itself is evaluated separately: a labeled set of 20 sentence and chunk pairs (supported, contradicted, unverifiable) measures verifier precision and recall, so the honesty mechanism is measured like any other component rather than trusted.

## Honesty about baselines

The report includes a dense only baseline and a no rerank baseline on recall@5 and MRR, so the hybrid and rerank design decisions are justified by numbers, not vibes. This mirrors the practice of publishing baselines even when they lose.
