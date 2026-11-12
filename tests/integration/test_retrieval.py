"""Integration tests for retrieval over the fixture index, zero network."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import ingest_fixture

from app.providers.embeddings import HashEmbedder
from app.retrieval.rerank import IdentityReranker
from app.retrieval.retriever import Retriever


def _retriever(tmp_path: Path, fixture_corpus: Path) -> Retriever:
    data_dir = ingest_fixture(tmp_path, fixture_corpus)
    return Retriever(data_dir, HashEmbedder(), IdentityReranker())


def test_analyst_retrieval_returns_evidence(tmp_path: Path, fixture_corpus: Path) -> None:
    retriever = _retriever(tmp_path, fixture_corpus)
    blocks = retriever.retrieve("operating margin", role="analyst")
    assert blocks, "unrestricted role must see candidates"
    assert all(block.text for block in blocks)
    assert all(1 <= block.page <= 5 for block in blocks)


def test_restricted_role_never_sees_filtered_documents(
    tmp_path: Path, fixture_corpus: Path
) -> None:
    retriever = _retriever(tmp_path, fixture_corpus)
    for question in ["operating margin", "calibration steps", "green status light"]:
        for block in retriever.retrieve(question, role="engineer"):
            assert block.doc_title == "Beta Manual", (
                "engineering role must only see the engineering document"
            )


def test_role_without_visible_documents_returns_empty(
    tmp_path: Path, fixture_corpus: Path
) -> None:
    retriever = _retriever(tmp_path, fixture_corpus)
    blocks = retriever.retrieve("operating margin", role="external")
    assert blocks == [], "no general department documents exist in the fixture"


def test_dense_only_baseline_mode(tmp_path: Path, fixture_corpus: Path) -> None:
    retriever = _retriever(tmp_path, fixture_corpus)
    blocks = retriever.retrieve("operating margin", role="analyst", mode="dense")
    assert isinstance(blocks, list)


def test_rerank_disabled_keeps_fusion_order(tmp_path: Path, fixture_corpus: Path) -> None:
    retriever = _retriever(tmp_path, fixture_corpus)
    blocks = retriever.retrieve("operating margin", role="analyst", use_rerank=False)
    assert all(block.rerank_score is None for block in blocks)


def test_top_n_limits_evidence_blocks(tmp_path: Path, fixture_corpus: Path) -> None:
    retriever = _retriever(tmp_path, fixture_corpus)
    blocks = retriever.retrieve("operating margin", role="analyst", top_n=2)
    assert len(blocks) <= 2
