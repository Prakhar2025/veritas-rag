"""Unit tests for the manifest: fingerprinting, roundtrip, hash lookup."""

from __future__ import annotations

from pathlib import Path

from app.ingest.manifest import Manifest, config_fingerprint


def test_fingerprint_is_stable_and_order_independent() -> None:
    one = config_fingerprint({"a": 1, "b": "x"})
    two = config_fingerprint({"b": "x", "a": 1})
    assert one == two
    assert len(one) == 16


def test_fingerprint_changes_with_parameters() -> None:
    one = config_fingerprint({"chunk_target_tokens": 300})
    two = config_fingerprint({"chunk_target_tokens": 400})
    assert one != two


def test_manifest_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    manifest = Manifest(version=3, fingerprint="abc123")
    manifest.upsert("doc1", {"sha256": "aa" * 32, "title": "Doc One"})
    manifest.save(path)
    loaded = Manifest.load(path)
    assert loaded is not None
    assert loaded.version == 3
    assert loaded.fingerprint == "abc123"
    assert loaded.doc_by_sha("aa" * 32) is not None


def test_doc_by_sha_miss_returns_none(tmp_path: Path) -> None:
    manifest = Manifest()
    assert manifest.doc_by_sha("ff" * 32) is None


def test_drop_removes_document(tmp_path: Path) -> None:
    manifest = Manifest()
    manifest.upsert("doc1", {"sha256": "aa" * 32})
    manifest.drop("doc1")
    assert "doc1" not in manifest.documents
