"""Integration tests for the grounded pipeline on fixture data, zero network."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import ingest_fixture

from app.core.config import Settings
from app.core.spend import SpendMeter
from app.graph.graph import run_turn
from app.graph.nodes import Runtime
from app.graph.store import SessionStore, StoredMessage
from app.providers.embeddings import HashEmbedder
from app.providers.fake import FakeChat
from app.retrieval.rerank import IdentityReranker
from app.retrieval.retriever import Retriever


def _runtime(
    tmp_path: Path, fixture_corpus: Path, responses: dict[str, str] | None = None
) -> Runtime:
    data_dir = ingest_fixture(tmp_path, fixture_corpus)
    settings = Settings(
        data_dir=str(data_dir),
        chat_provider="fake",
        embeddings_provider="hash",
        _env_file=None,  # type: ignore[call-arg]
    )
    meter = SpendMeter(Path(settings.data_dir) / "spend.json", settings.spend_cap_usd)
    chat = FakeChat(meter, responses=responses)
    return Runtime(
        retriever=Retriever(Path(settings.data_dir), HashEmbedder(), IdentityReranker()),
        cheap_chat=chat,
        main_chat=chat,
        settings=settings,
        store=SessionStore(Path(settings.data_dir) / "sessions.db"),
    )


def test_happy_path_answer_with_citation(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(tmp_path, fixture_corpus)
    final = run_turn(runtime, "s1", "operating margin", role="analyst")
    assert final["refusal"] is None
    assert final["answer"]
    assert final["citations"], "supported sentences must produce citations"
    assert final["meta"]["prompt_version"]
    stored = runtime.store.messages("s1")
    assert [m.role for m in stored] == ["user", "assistant"]


def test_unsupported_draft_refuses(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(tmp_path, fixture_corpus, responses={"attribute": "unsupported"})
    final = run_turn(runtime, "s1", "operating margin", role="analyst")
    assert final["refusal"] == "unsupported"
    assert final["citations"] == []
    assert "no sentence" in final["answer"]


def test_irrelevant_evidence_refuses(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(tmp_path, fixture_corpus, responses={"grade": "irrelevant"})
    final = run_turn(runtime, "s1", "operating margin", role="analyst")
    assert final["refusal"] == "irrelevant_evidence"


def test_permission_refusal_for_restricted_role(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(tmp_path, fixture_corpus)
    final = run_turn(runtime, "s1", "operating margin", role="external")
    assert final["refusal"] == "permission", (
        "the fixture has no general department documents, so external must be denied"
    )


def test_numeric_guard_strips_invented_numbers(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(
        tmp_path,
        fixture_corpus,
        responses={"generate": "The margin reached 99.9 percent [1].", "attribute": "supported"},
    )
    final = run_turn(runtime, "s1", "operating margin", role="analyst")
    assert final["refusal"] == "unsupported", (
        "a number absent from the source must fail the guard even when the judge agrees"
    )


def test_uncited_sentences_are_dropped(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(
        tmp_path,
        fixture_corpus,
        responses={
            "generate": (
                "Based on my own knowledge: The documents discuss margins [1]. "
                "This claim has no citation at all."
            )
        },
    )
    final = run_turn(runtime, "s1", "operating margin", role="analyst")
    assert final["refusal"] is None
    assert "no citation at all" not in final["answer"]
    assert "The documents discuss margins" in final["answer"]


def test_follow_up_persists_history(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(tmp_path, fixture_corpus)
    run_turn(runtime, "s1", "operating margin", role="analyst")
    run_turn(runtime, "s1", "summarize that for a CFO", role="analyst")
    stored = runtime.store.messages("s1")
    assert len(stored) == 4, "two turns must persist four messages"
    assert stored[2].role == "user"
    assert stored[2].content == "summarize that for a CFO"


def test_sessions_are_isolated(tmp_path: Path, fixture_corpus: Path) -> None:
    runtime = _runtime(tmp_path, fixture_corpus)
    run_turn(runtime, "s1", "operating margin", role="analyst")
    run_turn(runtime, "s2", "calibration", role="analyst")
    assert len(runtime.store.messages("s1")) == 2
    assert len(runtime.store.messages("s2")) == 2
    runtime.store.delete_session("s1")
    assert runtime.store.messages("s1") == []


def test_store_roundtrip(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    store.append("s1", StoredMessage(role="user", content="hello", citations=[]))
    store.append("s1", StoredMessage(role="assistant", content="hi", citations=[{"n": 1}]))
    messages = store.messages("s1")
    assert messages[1].citations == [{"n": 1}]
    sessions = store.list_sessions()
    assert sessions and sessions[0]["id"] == "s1"
