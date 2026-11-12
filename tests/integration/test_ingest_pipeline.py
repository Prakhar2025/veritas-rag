"""Integration tests for the ingestion pipeline on fixture PDFs, zero network."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.core.spend import SpendMeter
from app.ingest.index import read_jsonl
from app.ingest.pipeline import IngestReport, run_ingest
from app.providers.embeddings import HashEmbedder
from app.providers.fake import FakeChat


def _settings(tmp_path: Path, corpus_dir: Path) -> Settings:
    return Settings(
        data_dir=str(tmp_path / "data"),
        chat_provider="fake",
        embeddings_provider="hash",
        _env_file=None,  # type: ignore[call-arg]
    )


def _run(tmp_path: Path, corpus_dir: Path, **kwargs: object) -> IngestReport:
    settings = _settings(tmp_path, corpus_dir)
    meter = SpendMeter(tmp_path / "data" / "spend.json", settings.spend_cap_usd)
    return run_ingest(
        corpus_dir=corpus_dir,
        data_dir=Path(settings.data_dir),
        chat=FakeChat(meter),
        embedder=HashEmbedder(),
        settings=settings,
        **kwargs,  # type: ignore[arg-type]
    )


def test_first_ingest_indexes_both_documents(tmp_path: Path, fixture_corpus: Path) -> None:
    report = _run(tmp_path, fixture_corpus)
    assert len(report.indexed) == 2
    assert report.new_chunks > 0
    assert report.version == 1
    assert report.changed is True

    data_dir = tmp_path / "data"
    assert (data_dir / "indexes" / "faiss.index").exists()
    assert (data_dir / "indexes" / "bm25.pkl").exists()
    chunk_rows = read_jsonl(data_dir / "indexes" / "meta" / "chunks.jsonl")
    parent_rows = read_jsonl(data_dir / "indexes" / "meta" / "parents.jsonl")
    assert chunk_rows and parent_rows
    assert all(row["blurb"] for row in chunk_rows), "fake provider must fill every blurb"
    manifest = json.loads((data_dir / "indexes" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 1
    assert len(manifest["documents"]) == 2


def test_second_ingest_is_a_no_op(tmp_path: Path, fixture_corpus: Path) -> None:
    _run(tmp_path, fixture_corpus)
    report = _run(tmp_path, fixture_corpus)
    assert len(report.unchanged) == 2
    assert report.indexed == []
    assert report.changed is False
    assert report.version == 1, "unchanged run must not bump the index version"


def test_modified_document_bumps_version_and_reindexes(
    tmp_path: Path, fixture_corpus: Path
) -> None:
    _run(tmp_path, fixture_corpus)
    target = fixture_corpus / "alpha-report.pdf"
    payload = target.read_bytes()
    target.write_bytes(payload + b"trailing bytes to change the hash")
    report = _run(tmp_path, fixture_corpus)
    assert len(report.indexed) == 1
    assert len(report.unchanged) == 1
    assert report.version == 2
    data_dir = tmp_path / "data"
    chunk_rows = read_jsonl(data_dir / "indexes" / "meta" / "chunks.jsonl")
    doc_ids = {row["doc_id"] for row in chunk_rows}
    assert len(doc_ids) == 2, "both documents must survive the rebuild"


def test_skip_contextualize_produces_empty_blurbs(tmp_path: Path, fixture_corpus: Path) -> None:
    report = _run(tmp_path, fixture_corpus, skip_contextualize=True)
    assert len(report.indexed) == 2
    chunk_rows = read_jsonl(tmp_path / "data" / "indexes" / "meta" / "chunks.jsonl")
    assert all(row["blurb"] == "" for row in chunk_rows)
