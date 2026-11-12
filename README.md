# Veritas RAG

Grounded multi document RAG with conversational memory and sentence level citation verification, running open source Llama 3.3 70B on AWS Bedrock.

Upload multiple PDF reports, ask questions in natural language, and receive answers where every sentence is verified against the cited evidence before it reaches you. When the documents do not contain the answer, the system says so instead of inventing one.

**Status:** under active development. The full engineering documentation suite below defines the system before code lands, and each document is kept in sync with the implementation as it evolves.

| # | Document | Contents |
|---|----------|----------|
| 01 | [Problem statement](docs/01-problem-statement.md) | Why grounded retrieval matters and what this system solves |
| 02 | [Product requirements](docs/02-product-requirements.md) | Personas, functional and non functional requirements, non goals |
| 03 | [Architecture](docs/03-architecture.md) | Component map, pipeline design, model routing |
| 04 | [Data design](docs/04-data-design.md) | Corpus, chunking, schemas, index layout |
| 05 | [Retrieval design](docs/05-retrieval-design.md) | Hybrid search, fusion, reranking, access filtering, caching |
| 06 | [Generation and grounding](docs/06-generation-and-grounding.md) | Citation format, sentence level attribution, refusal policy, memory |
| 07 | [API specification](docs/07-api-specification.md) | Endpoints, streaming protocol, error contract |
| 08 | [Security and privacy](docs/08-security-and-privacy.md) | Access control, audit trail, injection stance |
| 09 | [Evaluation design](docs/09-evaluation-design.md) | Golden set, metrics, gates |
| 10 | [Testing strategy](docs/10-testing-strategy.md) | Test layers, stubs, coverage policy |
| 11 | [Technology stack](docs/11-tech-stack.md) | Libraries, verified model matrix, deprecation guards |
| 12 | [Roadmap](docs/12-roadmap.md) | Delivery plan and production scale out path |

License: [MIT](LICENSE)
