"""Unit tests for section aware chunking."""

from __future__ import annotations

from app.core.config import estimate_tokens
from app.ingest.chunk import chunk_document
from app.ingest.extract import PageText

DOC_ID = "deadbeef1234"


def test_chunks_carry_exact_page_numbers() -> None:
    pages = [
        PageText(page=1, markdown="# Overview\nAlpha text line one.\nAlpha text line two."),
        PageText(page=2, markdown="# Details\nBeta text line one.\nBeta text line two."),
    ]
    small, parents = chunk_document(pages, DOC_ID)
    assert small, "expected chunks"
    assert {chunk.page for chunk in small} == {1, 2}
    assert {parent.page for parent in parents} == {1, 2}


def test_section_paths_follow_headings() -> None:
    pages = [PageText(page=1, markdown="# Overview\nAlpha text.\n## Margins\nMargin text.")]
    small, _ = chunk_document(pages, DOC_ID)
    paths = {chunk.section_path for chunk in small}
    assert "Overview" in paths
    assert "Overview / Margins" in paths


def test_small_chunks_respect_target_size() -> None:
    body_line = "The operating margin improved by 340 basis points to 23.4 percent in FY2025."
    pages = [PageText(page=1, markdown="# Numbers\n" + "\n".join([body_line] * 60))]
    small, _ = chunk_document(pages, DOC_ID, target_tokens=50, overlap_tokens=10)
    assert len(small) > 1, "long block must split into several small chunks"
    for chunk in small:
        assert estimate_tokens(chunk.text) < 50 + len(body_line)


def test_parents_capped_at_max_tokens() -> None:
    body_line = "The operating margin improved by 340 basis points to 23.4 percent in FY2025."
    pages = [PageText(page=1, markdown="# Numbers\n" + "\n".join([body_line] * 200))]
    _, parents = chunk_document(pages, DOC_ID, parent_max_tokens=200)
    assert len(parents) > 1, "oversized block must split into parent parts"
    for parent in parents:
        assert estimate_tokens(parent.text) <= 200 + len(body_line)


def test_small_chunks_link_to_parents() -> None:
    pages = [PageText(page=1, markdown="# Overview\nAlpha text.\nBeta text.")]
    small, parents = chunk_document(pages, DOC_ID)
    parent_ids = {parent.parent_id for parent in parents}
    assert all(chunk.parent_id in parent_ids for chunk in small)


def test_empty_pages_produce_nothing() -> None:
    pages = [PageText(page=1, markdown="   ")]
    small, parents = chunk_document(pages, DOC_ID)
    assert small == []
    assert parents == []
