# 07. API Specification

Base URL (local): `http://localhost:8000`. All bodies are JSON. Optional bearer token auth when configured; local default runs without it.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, provider status, index version |
| POST | `/v1/ingest` | Ingest one or more PDFs, idempotent per document |
| POST | `/v1/chat` | Ask a question, Server Sent Events response |
| GET | `/v1/sessions` | List sessions |
| GET | `/v1/sessions/{id}/history` | Full message history with citations |
| DELETE | `/v1/sessions/{id}` | Delete a session and its history |
| GET | `/v1/trace/recent` | Recent request traces |

## Ingest

```json
POST /v1/ingest
{
  "documents": [
    {"filename": "annual_report.pdf", "content_base64": "...", "departments": ["finance"]}
  ]
}
```

```json
200 OK
{
  "results": [
    {"filename": "annual_report.pdf", "status": "indexed", "chunks": 412},
    {"filename": "old_report.pdf", "status": "unchanged", "reason": "sha256 match"}
  ],
  "index_version": 7
}
```

Status values: `indexed`, `unchanged`, `failed` with a reason. Index version increments only when content changed.

## Chat (streaming)

```json
POST /v1/chat
{
  "session_id": "b7c2...",
  "question": "What drove the operating margin change in FY2025?",
  "role": "analyst"
}
```

The response is an SSE stream. Event types:

| Event | Payload | Notes |
|---|---|---|
| `status` | `{"stage": "retrieving"}` | pipeline stage notifications |
| `token` | `{"text": "..."}` | answer tokens, in order |
| `citations` | `{"citations": [...]}` | verified citation list, sent after tokens |
| `meta` | `{"cache_hit": true, "index_version": 7, "latency_ms": {...}, "usage": {...}}` | final event on success |
| `error` | `{"code": "...", "message": "..."}` | terminal event on failure |

The stream always ends with `meta` on success or `error` on failure. Non streaming mode is available with `"stream": false` for tests.

## Sessions

```json
GET /v1/sessions
200 OK
{"sessions": [{"id": "b7c2...", "created_at": "...", "messages": 6}]}

GET /v1/sessions/{id}/history
200 OK
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "...", "citations": [...]}]}
```

`DELETE /v1/sessions/{id}` removes the session and returns `204`.

## Errors

```json
{"code": "index_empty", "message": "No documents ingested yet. Call /v1/ingest first."}
```

| HTTP | Code | Cause |
|---|---|---|
| 400 | `invalid_request` | malformed body, empty question |
| 404 | `session_not_found` | unknown session id |
| 413 | `payload_too_large` | document over size limit |
| 422 | `unsupported_document` | not a readable PDF |
| 429 | `rate_limited` | over the request rate limit |
| 503 | `provider_unavailable` | model provider unreachable |

## Traces

```json
GET /v1/trace/recent
200 OK
{"traces": [{"ts": "...", "session_id": "...", "stage_ms": {...}, "usage": {...}, "verdicts": {"grade": "relevant", "attribution": "4 of 5 sentences supported"}}]}
```

Traces are append only JSONL on disk; this endpoint reads the tail. Trace content carries no document bodies, only identifiers and verdicts.
