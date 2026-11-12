"""Section aware chunking: small chunks for embedding, parent blocks for generation.

Design notes (docs/04): pages are extracted as markdown with page numbers. Heading
lines define section paths; blocks never span pages, so every chunk carries an exact
page range for citations. Small chunks (about 300 tokens, line aligned overlap) feed
embedding and BM25; parents (up to 1200 tokens) feed generation (small to big).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import estimate_tokens

if TYPE_CHECKING:
    from app.ingest.extract import PageText


@dataclass
class ParentBlock:
    """A parent sized text block covering one section on one page."""

    parent_id: str
    doc_id: str
    page: int
    section_path: str
    text: str


@dataclass
class SmallChunk:
    """An embeddable chunk with citation grade page and section metadata."""

    chunk_id: str
    doc_id: str
    parent_id: str
    page: int
    section_path: str
    text: str


def _split_into_blocks(markdown: str, heading_stack: list[str]) -> list[tuple[str, list[str]]]:
    """Split one page's markdown into (section_path, lines) blocks, updating the stack."""
    blocks: list[tuple[str, list[str]]] = []
    current_path = " / ".join(heading_stack) if heading_stack else "Body"
    current_lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_lines:
                blocks.append((current_path, current_lines))
                current_lines = []
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped.lstrip("#").strip() or "Untitled"
            heading_stack[:] = heading_stack[: max(level - 1, 0)] + [title]
            current_path = " / ".join(heading_stack)
            current_lines.append(stripped)
        elif stripped:
            current_lines.append(line)
    if current_lines:
        blocks.append((current_path, current_lines))
    return blocks


def _chunk_block_text(
    text: str, target_tokens: int, overlap_tokens: int
) -> list[str]:
    """Split block text into overlapping small chunks at line boundaries."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    overlap_chars = overlap_tokens * 4
    pieces: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0
    for line in lines:
        line_tokens = estimate_tokens(line)
        if buffer and buffer_tokens + line_tokens > target_tokens:
            pieces.append("\n".join(buffer))
            tail = "\n".join(buffer)[-overlap_chars:] if overlap_tokens else ""
            carried = tail.splitlines() if tail else []
            buffer = [item for item in carried if item.strip()]
            buffer_tokens = estimate_tokens("\n".join(buffer))
        buffer.append(line)
        buffer_tokens += line_tokens
    if buffer:
        pieces.append("\n".join(buffer))
    return pieces


def _split_parent_parts(text: str, parent_max_tokens: int) -> list[str]:
    """Split oversized block text into parent sized parts at line boundaries."""
    if estimate_tokens(text) <= parent_max_tokens:
        return [text]
    lines = text.splitlines()
    parts: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0
    for line in lines:
        line_tokens = estimate_tokens(line)
        if buffer and buffer_tokens + line_tokens > parent_max_tokens:
            parts.append("\n".join(buffer))
            buffer, buffer_tokens = [], 0
        buffer.append(line)
        buffer_tokens += line_tokens
    if buffer:
        parts.append("\n".join(buffer))
    return parts


def chunk_document(
    pages: list[PageText],
    doc_id: str,
    target_tokens: int = 300,
    overlap_tokens: int = 45,
    parent_max_tokens: int = 1200,
) -> tuple[list[SmallChunk], list[ParentBlock]]:
    """Chunk one document into small chunks and parent blocks with stable ids."""
    typed_pages = list(pages)
    heading_stack: list[str] = []
    small_chunks: list[SmallChunk] = []
    parent_blocks: list[ParentBlock] = []
    small_seq = 0
    parent_seq = 0

    for page in typed_pages:
        for section_path, lines in _split_into_blocks(page.markdown, heading_stack):
            text = "\n".join(lines).strip()
            if not text:
                continue
            parts = _split_parent_parts(text, parent_max_tokens)
            block_parent_id = f"{doc_id}:p{parent_seq:04d}"
            for part_index, part in enumerate(parts):
                parent_id = block_parent_id if part_index == 0 else f"{doc_id}:p{parent_seq:04d}"
                parent_blocks.append(
                    ParentBlock(
                        parent_id=parent_id,
                        doc_id=doc_id,
                        page=page.page,
                        section_path=section_path,
                        text=part,
                    )
                )
                parent_seq += 1
            for piece in _chunk_block_text(text, target_tokens, overlap_tokens):
                small_chunks.append(
                    SmallChunk(
                        chunk_id=f"{doc_id}:s{small_seq:04d}",
                        doc_id=doc_id,
                        parent_id=block_parent_id,
                        page=page.page,
                        section_path=section_path,
                        text=piece,
                    )
                )
                small_seq += 1
    return small_chunks, parent_blocks
