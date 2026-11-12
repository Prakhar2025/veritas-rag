"""PDF extraction with page maps via pymupdf4llm, plus content hashing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm


@dataclass
class PageText:
    """One page of extracted markdown, 1-based page number preserved."""

    page: int
    markdown: str


def sha256_path(path: Path) -> str:
    """Return the full SHA-256 hex digest of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_pages(pdf_path: Path) -> list[PageText]:
    """Extract per page markdown; page numbers are normalized to 1-based."""
    raw_pages = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
    pages: list[PageText] = []
    for index, item in enumerate(raw_pages):
        meta = item.get("metadata") or {}
        number = int(meta.get("page", index)) + 1
        text = (item.get("text") or "").strip()
        if text:
            pages.append(PageText(page=number, markdown=text))
    return pages
