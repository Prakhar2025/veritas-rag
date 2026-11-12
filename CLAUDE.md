# Repository conventions

## Hard rules

1. No em dashes in any file, any message, any UI copy. Use commas, colons or parentheses.
2. Commit messages follow Conventional Commits (`feat:`, `fix(scope):`, `docs:`, `chore:`, `ci:`, `style:`, `build:`, `refactor:`) and describe what changed. Messages never reference plan indexes or phase numbers.
3. Commits are meaningful work units. A complete piece of work (the documentation suite, the ingestion pipeline, the service layer) lands as one commit, and a push goes out when that unit is done. Never fragment related files into many small commits, and never bundle unrelated changes together.
4. Never commit `.env`, `data/indexes/`, `data/traces/` or any credential.
5. Tests never call real model providers. The fake provider is the only provider in unit and integration tests; real provider runs are explicitly marked and manual.

## Layout

```
app/            application package
  api/          FastAPI routes, streaming, middleware
  core/         configuration, tracing, cache
  ingest/       extraction, chunking, contextualization, indexing
  retrieval/    hybrid search, fusion, rerank, role filter, parents
  graph/        LangGraph nodes and state
  attribution/  sentence verification
  providers/    bedrock, ollama, openai compatible, fake, embeddings
  ui/           Streamlit client
evals/          golden set, runner, judge, report
tests/          unit, integration, fixtures
docs/           numbered engineering documents
data/           corpus (committed), indexes and traces (generated)
```

## Commands

| Command | Does |
|---|---|
| `make setup` | create venv, install pinned requirements |
| `make ingest` | ingest or refresh the corpus |
| `make api` | run the FastAPI service locally |
| `make ui` | run the Streamlit client |
| `make test` | lint, types, unit and integration tests |
| `make eval` | run the golden set evaluation, regenerate the report |

## Documentation discipline

The `docs/` suite is the specification. Behavior changes update the relevant document in the same change set. The README stays honest: metrics in it come from generated reports, never hand written.

## Principle

Models propose, code decides. Deterministic code owns every decision that affects what the user sees: citation attachment, sentence removal, refusal, access denial.
