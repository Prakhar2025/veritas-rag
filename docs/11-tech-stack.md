# 11. Technology Stack

## Runtime libraries

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Pipeline | LangGraph | state graph with checkpointer |
| LLM client | langchain-core chat models + provider adapters | uniform interface across providers |
| Vector index | faiss-cpu | flat index, cosine |
| Sparse index | rank-bm25 | persisted tokenized artifact |
| PDF extraction | pymupdf4llm | layout and page map aware markdown |
| Embeddings | sentence-transformers, BAAI bge-small-en-v1.5 | local default |
| Reranker | sentence-transformers, BAAI bge-reranker-base | local cross encoder, CPU |
| API | FastAPI, uvicorn, sse-starlette | SSE streaming |
| Config | pydantic-settings | typed environment configuration |
| UI | Streamlit | chat with sources panel |
| Quality | pytest, ruff, mypy | gates in CI |

Dependencies are pinned in `requirements.txt`. The provider adapter layer keeps langgraph logic independent of any single vendor SDK.

## Model matrix (verified by test invocations, 2026-11-12)

Verified against AWS Bedrock, region us-east-1, by actual one token invocations, not by listing alone. Listing a model in a region does not mean the account can invoke it.

| Model | Status | Role in this project |
|---|---|---|
| Meta Llama 3.3 70B | working, via inference profile | default generator |
| Amazon Nova Micro | working, direct | rewrite, grade, judge |
| Amazon Nova Lite / Pro | working, direct | generation options |
| Amazon Nova 2 Lite | working, via global profile | generation option |
| Meta Llama 4 Scout | working, via profile | generation option |
| Mistral Ministral 3 8B | working, direct | small generation option |
| OpenAI GPT-OSS 20B | working, direct | generation option |
| Z.ai GLM 4.7 Flash | working, direct | budget generation option |
| Amazon Titan Embed Text v2 | working, direct, 1024 dims | embeddings option |
| Anthropic Claude family | blocked, payment instrument required | not used |
| Cohere Rerank 3.5 | blocked, payment instrument required | replaced by local cross encoder |

The matrix is published because reproducibility requires knowing which model served which answer, and because honest verification (invoke, not list) is part of the engineering standard here.

## Deprecation guards

Model providers retire models. The system is structured so that a retirement is a configuration change, not a code change:

1. All model identifiers live in environment configuration, never in source.
2. Provider selection is an environment switch: `bedrock`, `ollama`, or any OpenAI compatible endpoint.
3. Llama models are invoked through their inference profiles, the current recommended path.
4. The eval report records the model ids and prompt versions that produced each result, so a model swap is visible in evaluation history.

## Portability

The same codebase runs with no cloud account: set the provider to `ollama` with a local model for fully offline operation, or point the OpenAI compatible adapter at any hosted endpoint. Integration tests always run on the fake provider, so CI needs no credentials at all.

## Platform notes

Windows is a first class development environment here. Scripts avoid shell specific constructs, Make recipes pin to the project virtualenv, and provider payload serialization goes through the adapter rather than CLI tools, which sidesteps the Windows command line quoting pitfalls encountered during model verification.
