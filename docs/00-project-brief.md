# 00 Project Brief

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

## Context

Humanli.ai, a seed stage GenAI product company in Jaipur (Bhamasha Techno Hub), is hiring for two parallel roles (Data Scientist and Junior Data Scientist, both on site Jaipur, both via Google Forms) that share one technical assignment: complete exactly one of three problem statements and submit the GitHub repository. Deadline: Sunday, November 15, 2026. The two forms ask the same profile questions, so one repository serves both submissions.

The selection funnel is a mass funnel (promoted listings, 100+ applicants, three day window), so the working assumptions here are: the repository must stand on its own for an evaluator who spends ten minutes, and it must remain portfolio material worth owning regardless of the hiring outcome.

## The assignment we chose (verbatim from the assignment document)

> Develop an intelligent Retrieval-Augmented Generation (RAG) system that allows users to upload multiple PDF documents and ask questions using natural language. The system should retrieve relevant information from the uploaded documents and generate accurate, context-aware responses using a Large Language Model (LLM).
>
> The system must provide answers grounded in the uploaded documents, include relevant source references and handle situations where the requested information is unavailable. It should also maintain conversational context so users can ask follow-up questions without repeatedly providing the same information.
>
> For dataset: Use any sample reports, such as annual reports, financial reports, technical reports, business reports, or operational documents in PDF format. Upload multiple sample reports into the RAG system and use them to test document retrieval, question answering, source references, chat history, and conversational memory.

## Why this option (summary, reasoning recorded at decision time)

1. It is the company's actual product domain. Humanli.ai builds conversational bots over enterprise knowledge; a multi document RAG system is day one work for this team, so the evaluator reads the submission and sees the job itself.
2. It has the most checkable rubric. The problem statement names five testable capabilities (retrieval, question answering, source references, chat history, conversational memory) and most submissions will miss at least two of them; every one of them can be hit and then exceeded one level here.
3. It is the least crowded option. Fraud detection (option 1) and CNN classification (option 2) attract the classic student submissions; option 3 demands the most engineering and filters out the rest.
4. It fills the one gap in the existing portfolio. Sentinel and Gatehouse cover fraud defense, TruthLayer covers claim verification; nothing covers document grounded retrieval with citations.
5. It plays to existing strengths: hallucination verification design (TruthLayer), agent loops with closed tools (Gatehouse), honest evaluation publishing (Sentinel).

## Deliverables checklist (from the assignment text)

- [ ] Multiple PDF documents ingested and searchable (assignment: "upload multiple sample reports")
- [ ] Natural language question answering grounded in the documents
- [ ] Source references that resolve to document and page
- [ ] Graceful handling when information is unavailable
- [ ] Chat history and conversational memory across follow up questions
- [ ] Working system the evaluator can run, with setup instructions and README (assignment submission guidelines)

Each bullet is exceeded one level in the delivery plan: sentence level attribution on top of references, explicit refusal taxonomy on top of graceful handling, persistent restart proof sessions on top of chat history, a role based access filter on top of retrieval, and a gated evaluation suite on top of "test the system".

## Hard constraints

- **No Docker.** It does not work reliably on this machine. Never suggest it, not in docs, not in the roadmap, not as an optional extra.
- **Python 3.12 via the py launcher** on Windows (Git Bash). `python` is not on PATH; make targets pin to the project virtualenv.
- **No em dash or en dash characters anywhere**, in any file or message.
- **No secrets in the repository.** `.env` is gitignored; `.env.example` is the template. AWS access rides the default credential chain.
- **Corpus is public documents only**, committed in small files (each well under 20 MB) with sources recorded, so the repository clones ready to run.
- **Bounded spend.** Soft budget USD 5 of Bedrock spend during development, metered, with call caps in scripts.
- **Evaluator experience first.** Clone to working demo in under 10 minutes following only the README.

## Non goals

- OCR of scanned or image only PDFs (roadmap notes the production path).
- Multi tenant cloud scale out; access control is modeled at document and role level in one deployment.
- Fine tuning; retrieval quality comes from chunking, hybrid search and reranking.
- Live connectors to document stores; ingestion is explicit PDF upload.

## Success criteria

1. An evaluator can clone the repository, follow the README with their own AWS or local setup, and reach a working cited conversation in under 10 minutes.
2. Every assignment bullet is visible in the demo and exceeded one level in the implementation.
3. The evaluation suite (doc 09) passes its gates, and the README publishes results with baselines and honest limitations.
4. The package (docs, demo video, evals, traces) makes the engineering standard visible: models propose, code decides.
