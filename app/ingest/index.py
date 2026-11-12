"""Hybrid index artifacts: FAISS over normalized embeddings plus a BM25 snapshot.

Rebuilds are atomic: artifacts are written to temp paths and replaced. Metadata
snapshots (chunks and parents) are full JSONL rewrites, which keeps rebuild logic
deterministic and simple at corpus scale.
"""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from app.ingest.chunk import ParentBlock, SmallChunk

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenization for BM25."""
    return _TOKEN_PATTERN.findall(text.lower())


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def write_jsonl_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a JSONL snapshot atomically."""
    payload = ("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n").encode(
        "utf-8"
    )
    _atomic_write_bytes(path, payload)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read a JSONL file; missing file means empty."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def chunk_rows(chunks: list[SmallChunk], blurbs: dict[str, str]) -> list[dict[str, object]]:
    """Serialize small chunks to metadata rows."""
    return [
        {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "parent_id": chunk.parent_id,
            "page": chunk.page,
            "section_path": chunk.section_path,
            "text": chunk.text,
            "blurb": blurbs.get(chunk.chunk_id, ""),
        }
        for chunk in chunks
    ]


def parent_rows(parents: list[ParentBlock]) -> list[dict[str, object]]:
    """Serialize parent blocks to metadata rows."""
    return [
        {
            "parent_id": parent.parent_id,
            "doc_id": parent.doc_id,
            "page": parent.page,
            "section_path": parent.section_path,
            "text": parent.text,
        }
        for parent in parents
    ]


def build_faiss(index_dir: Path, vectors: np.ndarray) -> None:
    """Write the flat inner product index over normalized vectors, atomically."""
    index_dir.mkdir(parents=True, exist_ok=True)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(np.ascontiguousarray(vectors))
    tmp = index_dir / "faiss.index.tmp"
    faiss.write_index(index, str(tmp))
    tmp.replace(index_dir / "faiss.index")


def build_bm25(index_dir: Path, texts: list[str]) -> None:
    """Write the BM25 artifact over tokenized texts, atomically."""
    corpus = [tokenize(text) for text in texts]
    bm25 = BM25Okapi(corpus)
    _atomic_write_bytes(index_dir / "bm25.pkl", pickle.dumps(bm25))


def load_faiss(index_dir: Path):  # type: ignore[no-untyped-def]
    """Load the FAISS index if present."""
    path = index_dir / "faiss.index"
    if not path.exists():
        return None
    return faiss.read_index(str(path))


def load_bm25(index_dir: Path):  # type: ignore[no-untyped-def]
    """Load the BM25 artifact if present."""
    path = index_dir / "bm25.pkl"
    if not path.exists():
        return None
    return pickle.loads(path.read_bytes())
