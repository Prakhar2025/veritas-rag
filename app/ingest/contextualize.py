"""Contextual blurbs via the cheap grading model, batched and cached (docs/04).

One call covers a batch of ten chunks: the prompt lists numbered chunks and the
model returns one blurb line per marker. Blurbs are cached by chunk text hash, so
re ingestion of unchanged chunks costs nothing and changed chunks recontextualize
individually.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.ingest.chunk import SmallChunk
from app.providers.base import ChatProvider

BATCH_SIZE = 10
_MARKER_PATTERN = re.compile(r"^(C\d{2}):\s*(.+)$", re.MULTILINE)
_SYSTEM_PROMPT = (
    "You write one sentence context blurbs for retrieval chunks. For each numbered "
    "chunk you receive, output exactly one line in the form C01: <blurb>. The blurb "
    "states what the chunk contains and where it sits in its document. No preamble, "
    "no extra lines."
)


def _cache_path(cache_dir: Path, text: str) -> Path:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{digest}.json"


def _fallback_blurb(title: str, section_path: str, text: str) -> str:
    """Deterministic blurb used when a batch line is missing or malformed."""
    snippet = " ".join(text.split())[:140]
    return f"Part of {title}, section {section_path}. Content: {snippet}"


def _batch_user_prompt(batch: list[tuple[str, str, str, str]]) -> str:
    """Build the numbered batch prompt: marker, title, section, truncated text."""
    lines = [
        "Write one blurb line for each chunk below, in the exact form C01: <blurb>."
    ]
    for index, (_chunk_id, title, section_path, text) in enumerate(batch):
        marker = f"C{index + 1:02d}"
        snippet = " ".join(text.split())[:600]
        lines.append(f"{marker} | {title} | {section_path} | {snippet}")
    return "\n".join(lines)


def contextualize_chunks(
    chunks: list[SmallChunk],
    doc_titles: dict[str, str],
    provider: ChatProvider,
    model_id: str,
    cache_dir: Path,
) -> dict[str, str]:
    """Return chunk_id to blurb mapping, cache first, batched provider calls second."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    blurbs: dict[str, str] = {}
    pending: list[tuple[str, str, str, str]] = []
    for chunk in chunks:
        cache_file = _cache_path(cache_dir, chunk.text)
        if cache_file.exists():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            blurbs[chunk.chunk_id] = str(cached["blurb"])
            continue
        title = doc_titles.get(chunk.doc_id, chunk.doc_id)
        pending.append((chunk.chunk_id, title, chunk.section_path, chunk.text))

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        result = provider.complete(
            purpose="contextualize",
            model_id=model_id,
            system=_SYSTEM_PROMPT,
            user=_batch_user_prompt(batch),
            max_tokens=400,
        )
        found = dict(_MARKER_PATTERN.findall(result.text))
        for index, (chunk_id, title, section_path, text) in enumerate(batch):
            marker = f"C{index + 1:02d}"
            blurb = found.get(marker, "").strip() or _fallback_blurb(title, section_path, text)
            blurbs[chunk_id] = blurb
            _cache_path(cache_dir, text).write_text(
                json.dumps({"blurb": blurb}, ensure_ascii=False), encoding="utf-8"
            )
    return blurbs
