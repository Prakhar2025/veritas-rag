"""Integration tests for the FastAPI contract, zero network."""

from __future__ import annotations

import base64
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from tests.conftest import ingest_fixture

from app.api.app import create_app
from app.core.config import get_settings


def _client(
    tmp_path: Path,
    fixture_corpus: Path,
    monkeypatch: Any,
    extra_env: dict[str, str] | None = None,
) -> TestClient:
    data_dir = ingest_fixture(tmp_path, fixture_corpus)
    monkeypatch.setenv("VERITAS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("VERITAS_CHAT_PROVIDER", "fake")
    monkeypatch.setenv("VERITAS_EMBEDDINGS_PROVIDER", "hash")
    monkeypatch.setenv("VERITAS_RERANKER_PROVIDER", "identity")
    for key, value in (extra_env or {}).items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.app._STATE", None)
    monkeypatch.setattr("app.api.app._RATE_BUCKETS", defaultdict(deque))
    return TestClient(create_app())


def test_health_reports_index_version(
    tmp_path: Path, fixture_corpus: Path, monkeypatch: Any
) -> None:
    client = _client(tmp_path, fixture_corpus, monkeypatch)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["index_version"] >= 1


def test_chat_non_stream_returns_answer(
    tmp_path: Path, fixture_corpus: Path, monkeypatch: Any
) -> None:
    client = _client(tmp_path, fixture_corpus, monkeypatch)
    response = client.post(
        "/v1/chat",
        json={"session_id": "s1", "question": "operating margin", "stream": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["citations"]
    history = client.get("/v1/sessions/s1/history")
    assert history.status_code == 200
    assert len(history.json()["messages"]) == 2


def test_chat_sse_event_order(tmp_path: Path, fixture_corpus: Path, monkeypatch: Any) -> None:
    client = _client(tmp_path, fixture_corpus, monkeypatch)
    events: list[str] = []
    token_seen = False
    with client.stream(
        "POST", "/v1/chat", json={"session_id": "s1", "question": "operating margin"}
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ").strip()
                if event == "token":
                    if not token_seen:
                        events.append("first_token")
                        token_seen = True
                else:
                    events.append(event)
    assert "first_token" in events
    assert events.index("first_token") < events.index("citations") < events.index("meta")


def test_invalid_request_maps_to_400(
    tmp_path: Path, fixture_corpus: Path, monkeypatch: Any
) -> None:
    client = _client(tmp_path, fixture_corpus, monkeypatch)
    response = client.post("/v1/chat", json={"session_id": "s1", "question": ""})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_unknown_session_maps_to_404(
    tmp_path: Path, fixture_corpus: Path, monkeypatch: Any
) -> None:
    client = _client(tmp_path, fixture_corpus, monkeypatch)
    response = client.get("/v1/sessions/nope/history")
    assert response.status_code == 404


def test_rate_limit_maps_to_429(
    tmp_path: Path, fixture_corpus: Path, monkeypatch: Any
) -> None:
    client = _client(
        tmp_path, fixture_corpus, monkeypatch, {"VERITAS_RATE_LIMIT_PER_MINUTE": "2"}
    )
    codes = []
    for _ in range(3):
        response = client.post(
            "/v1/chat", json={"session_id": "s1", "question": "operating margin"}
        )
        codes.append(response.status_code)
    assert codes[:2] == [200, 200]
    assert codes[2] == 429


def test_ingest_endpoint_indexes_a_pdf(
    tmp_path: Path, fixture_corpus: Path, monkeypatch: Any
) -> None:
    client = _client(tmp_path, fixture_corpus, monkeypatch)
    from tests.conftest import build_pdf

    extra = tmp_path / "extra.pdf"
    build_pdf(extra, ["# Gamma Note", "Gamma documents the quarterly review process."])
    payload = base64.b64encode(extra.read_bytes()).decode("ascii")
    response = client.post(
        "/v1/ingest",
        json={"documents": [
            {"filename": "extra.pdf", "content_base64": payload, "departments": ["general"]}
        ]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["status"] == "indexed"
    assert body["index_version"] >= 2


def test_traces_record_requests(tmp_path: Path, fixture_corpus: Path, monkeypatch: Any) -> None:
    client = _client(tmp_path, fixture_corpus, monkeypatch)
    client.post(
        "/v1/chat", json={"session_id": "s1", "question": "operating margin", "stream": False}
    )
    response = client.get("/v1/trace/recent")
    traces = response.json()["traces"]
    assert traces
    assert traces[-1]["session_id"] == "s1"
    assert "total_ms" in traces[-1]


