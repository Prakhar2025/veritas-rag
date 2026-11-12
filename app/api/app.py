"""FastAPI service: the contract of docs/07 served over the grounded pipeline.

Singletons build once at startup; chat streams stage events, verified tokens,
citations and metadata per the SSE protocol; every request appends a trace.
"""

from __future__ import annotations

import base64
import binascii
import json
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    CitationModel,
    IngestItemResult,
    IngestRequest,
    IngestResponse,
)
from app.core.config import get_settings
from app.core.spend import SpendMeter
from app.core.tracing import TraceWriter
from app.graph.graph import build_graph
from app.graph.nodes import Runtime
from app.graph.store import SessionStore
from app.ingest.pipeline import run_ingest
from app.providers.base import ChatProvider
from app.providers.bedrock import BedrockChat
from app.providers.embeddings import build_embedder
from app.providers.fake import FakeChat
from app.retrieval.rerank import build_reranker
from app.retrieval.retriever import Retriever

_STAGE_ORDER = [
    ("condense", "condense_ms"),
    ("retrieve", "retrieve_ms"),
    ("grade", "grade_ms"),
    ("generate", "generate_ms"),
    ("attribute", "attribute_ms"),
]


class _State:
    """Singletons shared across requests."""

    settings: object
    store: SessionStore
    tracer: TraceWriter
    meter: SpendMeter
    runtime: Runtime
    compiled: object = None

    @classmethod
    def build(cls) -> _State:
        state = cls()
        state.settings = get_settings()
        s0 = state.settings
        data_dir = Path(s0.data_dir)
        state.meter = SpendMeter(data_dir / "spend.json", s0.spend_cap_usd)
        chat: ChatProvider
        if s0.chat_provider == "bedrock":
            chat = BedrockChat(s0.aws_region, s0.aws_profile, state.meter)
        else:
            chat = FakeChat(state.meter)
        state.runtime = Runtime(
            retriever=Retriever(
                data_dir,
                build_embedder(s0.embeddings_provider, s0.embeddings_model),
                build_reranker(s0.reranker_provider, s0.reranker_model),
            ),
            cheap_chat=chat,
            main_chat=chat,
            settings=s0,
            store=SessionStore(data_dir / "sessions.db"),
        )
        state.compiled = build_graph(state.runtime)
        state.store = state.runtime.store
        state.tracer = TraceWriter(data_dir / "traces")
        return state


_STATE: _State | None = None
_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def get_state() -> _State:
    """Build or return the singleton service state."""
    global _STATE
    if _STATE is None:
        _STATE = _State.build()
    return _STATE


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def _rate_limited(request: Request, limit: int) -> bool:
    """Sliding window per client for the chat route."""
    bucket = _RATE_BUCKETS[request.client.host if request.client else "unknown"]
    now = time.monotonic()
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


def _rebuild_runtime(state: _State) -> None:
    """Rebuild retriever and compiled graph after ingestion changes the index."""
    s = state.settings
    data_dir = Path(state.settings.data_dir)  # type: ignore[attr-defined]
    state.runtime = Runtime(
        retriever=Retriever(
            data_dir,
            build_embedder(s.embeddings_provider, s.embeddings_model),  # type: ignore[attr-defined]
            build_reranker(s.reranker_provider, s.reranker_model),  # type: ignore[attr-defined]
        ),
        cheap_chat=state.runtime.cheap_chat,
        main_chat=state.runtime.main_chat,
        settings=state.settings,  # type: ignore[arg-type]
        store=state.runtime.store,
    )
    state.compiled = build_graph(state.runtime)


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title="Veritas RAG", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        state = get_state()
        return {
            "status": "ok",
            "index_version": state.runtime.retriever.version,
            "chat_provider": state.settings.chat_provider,  # type: ignore[attr-defined]
            "embeddings": state.settings.embeddings_provider,  # type: ignore[attr-defined]
        }

    @app.post("/v1/ingest")
    def ingest(request: IngestRequest) -> JSONResponse:
        state = get_state()
        uploads_dir = Path(state.settings.data_dir) / "uploads"  # type: ignore[attr-defined]
        results: list[IngestItemResult] = []
        try:
            uploads_dir.mkdir(parents=True, exist_ok=True)
            for document in request.documents:
                safe_name = Path(document.filename).name
                target = uploads_dir / safe_name
                try:
                    target.write_bytes(base64.b64decode(document.content_base64))
                except (binascii.Error, ValueError):
                    results.append(
                        IngestItemResult(filename=safe_name, status="failed",
                                         reason="invalid base64")
                    )
            report = run_ingest(
                corpus_dir=uploads_dir,
                data_dir=Path(state.settings.data_dir),  # type: ignore[attr-defined]
                chat=state.runtime.cheap_chat,
                embedder=build_embedder(
                    state.settings.embeddings_provider,  # type: ignore[attr-defined]
                    state.settings.embeddings_model,  # type: ignore[attr-defined]
                ),
                settings=state.settings,  # type: ignore[arg-type]
            )
            for name in report.indexed:
                results.append(IngestItemResult(filename=name, status="indexed"))
            for name in report.unchanged:
                results.append(IngestItemResult(filename=name, status="unchanged"))
            for failure in report.failed:
                filename, _, reason = failure.partition(" (")
                results.append(
                    IngestItemResult(filename=filename, status="failed", reason=reason.rstrip(")"))
                )
            _rebuild_runtime(state)
            return JSONResponse(
                IngestResponse(results=results, index_version=report.version).model_dump()
            )
        except Exception as exc:  # noqa: BLE001, contract maps failures to codes
            return _error("provider_unavailable", str(exc), 503)

    @app.post("/v1/chat")
    def chat(request: Request, body: dict[str, object]) -> object:
        settings = get_settings()
        if _rate_limited(request, settings.rate_limit_per_minute):
            return _error("rate_limited", "too many requests, slow down", 429)
        try:
            parsed = ChatRequest.model_validate(body)
        except ValidationError as exc:
            message = str(exc.errors()[0].get("msg", "invalid"))
            return _error("invalid_request", message, 400)
        state = get_state()
        if state.runtime.retriever.version == 0:
            return _error(
                "index_empty", "No documents ingested yet. Call /v1/ingest first.", 503
            )
        started = time.perf_counter()
        history = state.store.history(parsed.session_id)
        final = state.compiled.invoke(  # type: ignore[attr-defined]
            {"session_id": parsed.session_id, "role": parsed.role,
             "question": parsed.question, "history": history},
        )
        citations = [CitationModel(**c) for c in final.get("citations", [])]
        state.tracer.write({
            "session_id": parsed.session_id,
            "role": parsed.role,
            "question": parsed.question[:120],
            "refusal": final.get("refusal"),
            "citations": len(citations),
            "stage_ms": final.get("meta", {}),
            "total_ms": round((time.perf_counter() - started) * 1000, 1),
        })
        if not parsed.stream:
            return ChatResponse(
                answer=final["answer"], citations=citations, meta=final.get("meta", {})
            )

        meta = dict(final.get("meta", {}))

        def events() -> Iterator[str]:
            def frame(event: str, data: str) -> str:
                return f"event: {event}\ndata: {data}\n\n"

            for stage, key in _STAGE_ORDER:
                if key in meta:
                    yield frame("status", json.dumps({"stage": stage, "ms": meta[key]}))
            words = final["answer"].split(" ")
            for index in range(0, len(words), 3):
                chunk = " ".join(words[index : index + 3])
                yield frame("token", json.dumps({"text": chunk}))
            yield frame("citations", json.dumps(
                {"citations": [c.model_dump() for c in citations]}
            ))
            yield frame("meta", json.dumps(meta, default=str))

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/v1/sessions")
    def sessions() -> dict[str, object]:
        return {"sessions": get_state().store.list_sessions()}

    @app.get("/v1/sessions/{session_id}/history")
    def history(session_id: str) -> object:
        state = get_state()
        messages = state.store.messages(session_id)
        if not messages:
            return _error("session_not_found", f"unknown session {session_id}", 404)
        return {
            "messages": [
                {"role": m.role, "content": m.content, "citations": m.citations}
                for m in messages
            ]
        }

    @app.delete("/v1/sessions/{session_id}")
    def delete_session(session_id: str) -> Response:
        state = get_state()
        if not state.store.messages(session_id):
            return _error("session_not_found", f"unknown session {session_id}", 404)
        state.store.delete_session(session_id)
        return Response(status_code=204)

    @app.get("/v1/trace/recent")
    def traces(count: int = 20) -> dict[str, object]:
        return {"traces": get_state().tracer.recent(count)}

    return app
