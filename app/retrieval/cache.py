"""Semantic question cache with index version invalidation (docs/05).

Entries store the index version that produced them; any ingestion that changes
content bumps the version and invalidates entries in one comparison. The payload
is generic: at the answer layer it holds the generated response, at the retrieval
layer it can hold a prior retrieval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class CacheEntry:
    """One cached question with its embedding, version and payload."""

    question: str
    index_version: int
    payload: dict[str, object]
    embedding: list[float] = field(default_factory=list)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two vectors; zero vectors never match."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


class QuestionCache:
    """JSONL backed semantic cache."""

    def __init__(self, path: Path, threshold: float = 0.95) -> None:
        self._path = path
        self._threshold = threshold
        self._entries: list[CacheEntry] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    data = json.loads(line)
                    self._entries.append(
                        CacheEntry(
                            question=str(data["question"]),
                            index_version=int(data["index_version"]),
                            payload=dict(data.get("payload", {})),
                            embedding=[float(x) for x in data.get("embedding", [])],
                        )
                    )

    def lookup(
        self,
        question: str,
        question_embedding: np.ndarray,
        index_version: int,
    ) -> CacheEntry | None:
        """Return the first same version entry above the similarity threshold."""
        for entry in self._entries:
            if entry.index_version != index_version:
                continue
            stored = np.array(entry.embedding, dtype="float32")
            if stored.size and _cosine(question_embedding, stored) >= self._threshold:
                return entry
        return None

    def put(
        self,
        question: str,
        question_embedding: np.ndarray,
        index_version: int,
        payload: dict[str, object],
    ) -> CacheEntry:
        """Append an entry and persist the file atomically."""
        entry = CacheEntry(
            question=question,
            index_version=index_version,
            payload=payload,
            embedding=[float(x) for x in question_embedding],
        )
        self._entries.append(entry)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload_lines = [
            json.dumps(
                {
                    "question": e.question,
                    "index_version": e.index_version,
                    "payload": e.payload,
                    "embedding": e.embedding,
                }
            )
            for e in self._entries
        ]
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text("\n".join(payload_lines) + "\n", encoding="utf-8")
        tmp.replace(self._path)
        return entry

    def clear(self) -> None:
        """Drop all entries (used after full rebuilds)."""
        self._entries = []
        if self._path.exists():
            self._path.unlink()
