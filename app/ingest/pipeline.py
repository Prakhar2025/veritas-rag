"""Ingestion orchestration with SHA-256 idempotency and atomic index rebuilds.

Flow (docs/04): scan corpus, hash each PDF, skip unchanged documents, extract and
chunk changed ones, contextualize new chunks, merge metadata with surviving
documents, rebuild the hybrid indexes atomically, bump the index version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings
from app.ingest.chunk import ParentBlock, SmallChunk, chunk_document
from app.ingest.contextualize import contextualize_chunks
from app.ingest.extract import PageText, extract_pages, sha256_path
from app.ingest.index import (
    build_bm25,
    build_faiss,
    chunk_rows,
    parent_rows,
    read_jsonl,
    write_jsonl_atomic,
)
from app.ingest.manifest import Manifest, config_fingerprint
from app.providers.base import ChatProvider
from app.providers.embeddings import Embedder


@dataclass
class IngestReport:
    """Outcome of one ingestion run."""

    indexed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    new_chunks: int = 0
    version: int = 0
    changed: bool = False

    def summary(self) -> str:
        """Human readable run summary."""
        lines = [
            f"index version: {self.version}",
            f"indexed: {len(self.indexed)} ({', '.join(self.indexed) or 'none'})",
            f"unchanged: {len(self.unchanged)} ({', '.join(self.unchanged) or 'none'})",
            f"failed: {len(self.failed)} ({', '.join(self.failed) or 'none'})",
            f"new chunks: {self.new_chunks}",
        ]
        return "\n".join(lines)


def _load_catalog(corpus_dir: Path) -> dict[str, dict[str, object]]:
    """Read the corpus catalog written by scripts/fetch_corpus.py."""
    catalog_path = corpus_dir / "catalog.json"
    if not catalog_path.exists():
        return {}
    return {
        entry["filename"]: entry
        for entry in json.loads(catalog_path.read_text(encoding="utf-8"))
    }


def run_ingest(
    corpus_dir: Path,
    data_dir: Path,
    chat: ChatProvider,
    embedder: Embedder,
    settings: Settings,
    skip_contextualize: bool = False,
    force: bool = False,
) -> IngestReport:
    """Run one idempotent ingestion pass and return the report."""
    indexes_dir = data_dir / "indexes"
    meta_dir = indexes_dir / "meta"
    cache_dir = data_dir / "cache" / "blurbs"
    manifest_path = indexes_dir / "manifest.json"

    manifest = Manifest.load(manifest_path) or Manifest()
    fingerprint = config_fingerprint(
        {
            "embeddings_model": embedder.model_name,
            "chunk_target_tokens": settings.chunk_target_tokens,
            "chunk_overlap_tokens": settings.chunk_overlap_tokens,
            "parent_max_tokens": settings.parent_max_tokens,
        }
    )
    fingerprint_changed = manifest.fingerprint != fingerprint and manifest.fingerprint != ""

    report = IngestReport()
    catalog = _load_catalog(corpus_dir)
    pdfs = sorted(corpus_dir.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"no PDFs found in {corpus_dir}; run scripts/fetch_corpus.py first")

    new_small: list[SmallChunk] = []
    new_parents: list[ParentBlock] = []
    doc_titles: dict[str, str] = {}
    superseded_doc_ids: set[str] = set()

    for pdf_path in pdfs:
        sha = sha256_path(pdf_path)
        catalog_entry = catalog.get(pdf_path.name, {})
        stored = manifest.doc_by_sha(sha)
        if stored is not None and not fingerprint_changed and not force:
            report.unchanged.append(pdf_path.name)
            continue
        prior = next(
            (
                record
                for record in manifest.documents.values()
                if record.get("filename") == pdf_path.name
            ),
            None,
        )
        prior_doc_id = str(prior["doc_id"]) if prior else None
        try:
            pages: list[PageText] = extract_pages(pdf_path)
            if not pages:
                raise RuntimeError("no extractable text")
            doc_id = sha[:12]
            small, parents = chunk_document(
                pages,
                doc_id,
                target_tokens=settings.chunk_target_tokens,
                overlap_tokens=settings.chunk_overlap_tokens,
                parent_max_tokens=settings.parent_max_tokens,
            )
            new_small.extend(small)
            new_parents.extend(parents)
            doc_titles[doc_id] = str(catalog_entry.get("title", pdf_path.stem))
            record = {
                "doc_id": doc_id,
                "sha256": sha,
                "title": doc_titles[doc_id],
                "filename": pdf_path.name,
                "pages": max(page.page for page in pages),
                "departments": catalog_entry.get("departments", ["general"]),
                "chunks": len(small),
            }
            manifest.upsert(doc_id, record)
            if prior_doc_id and prior_doc_id != doc_id:
                # Same filename re ingested with changed content: retire the old id.
                manifest.drop(prior_doc_id)
                superseded_doc_ids.add(prior_doc_id)
            report.indexed.append(pdf_path.name)
            report.new_chunks += len(small)
        except Exception as exc:  # noqa: BLE001, reported per document by design
            report.failed.append(f"{pdf_path.name} ({exc})")

    changed = bool(report.indexed) or fingerprint_changed or force
    if not changed:
        report.version = manifest.version
        return report

    if skip_contextualize:
        blurbs: dict[str, str] = {}
    else:
        blurbs = contextualize_chunks(
            chunks=new_small,
            doc_titles=doc_titles,
            provider=chat,
            model_id=settings.nova_micro_model_id,
            cache_dir=cache_dir,
        )

    # Merge metadata: keep rows of surviving documents, drop rows of superseded docs.
    existing_chunk_rows = read_jsonl(meta_dir / "chunks.jsonl")
    existing_parent_rows = read_jsonl(meta_dir / "parents.jsonl")
    if fingerprint_changed or force:
        existing_chunk_rows, existing_parent_rows = [], []
    else:
        existing_chunk_rows = [
            row for row in existing_chunk_rows if row["doc_id"] not in superseded_doc_ids
        ]
        existing_parent_rows = [
            row for row in existing_parent_rows if row["doc_id"] not in superseded_doc_ids
        ]

    all_chunk_rows = existing_chunk_rows + chunk_rows(new_small, blurbs)
    all_parent_rows = existing_parent_rows + parent_rows(new_parents)
    write_jsonl_atomic(meta_dir / "chunks.jsonl", all_chunk_rows)
    write_jsonl_atomic(meta_dir / "parents.jsonl", all_parent_rows)

    embed_texts = [f"{row['blurb']}\n{row['text']}" for row in all_chunk_rows]
    vectors = embedder.embed(embed_texts)
    build_faiss(indexes_dir, vectors)
    build_bm25(indexes_dir, [str(row["text"]) for row in all_chunk_rows])

    manifest.version += 1
    manifest.fingerprint = fingerprint
    manifest.save(manifest_path)
    report.version = manifest.version
    report.changed = True
    return report
