# Demo Script

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Active |
| Owner | Prakhar Shukla |
| Last updated | 2026-11-13 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial 75 second script for recording |

Target: 60 to 75 seconds, 1080p, narrated screen recording of the console at
http://localhost:3000 with the API running (`make api`, `make console`).

| Second | On screen | Narration |
|---|---|---|
| 0 to 8 | Banner or README top, then the console opens | "This is Veritas RAG. Every sentence in an answer is verified against the document chunk it cites before you ever see it." |
| 8 to 18 | Type "What was Apples total net sales in fiscal 2024?" | "Multiple PDF reports are already ingested: financial statements, a regulatory standard, technical papers, an operations manual. Ask a question in plain language." |
| 18 to 30 | Stage indicators, then the answer with the citation chip | "The pipeline retrieves with hybrid search, grades the evidence, drafts with Llama 3.3 70B, then verifies each sentence against its cited chunk. The citation names the document and page." |
| 30 to 40 | Click follow up "Summarize that for an investor" | "Follow ups work: the session persists in SQLite, so 'that' resolves without repeating context." |
| 40 to 50 | Ask "What did Apples stock close at yesterday?" | "Questions the corpus cannot answer are refused, not invented. Refusals are a gated metric, not a failure state." |
| 50 to 60 | Switch role to engineer, ask about net sales again | "Access control runs at retrieval time. The strongest evidence sits in a finance document this role cannot see, so the request fails closed." |
| 60 to 72 | Show the trace panel on the right | "Every request leaves a trace: stage latencies, verdicts and costs. The README publishes the golden set results: recall 0.818, refusals 8 of 8, permission 4 of 4, and delivered citation precision 1.0 by construction." |
| 72 to 75 | End card: repo URL | "Models propose, code decides." |

## Recording checklist

- [ ] Start `make api` and `make console`, confirm /health shows index version 2
- [ ] Pre warm the first chat so model latency does not stall the recording
- [ ] Record at 1080p, dark console theme, zoom 125 percent for legibility
- [ ] Narrate slowly; the seven beats above land inside 75 seconds
- [ ] Upload, then put the link in the README demo section above the fold
