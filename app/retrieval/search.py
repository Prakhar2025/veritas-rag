"""Hybrid search: role pre filtering, dense and sparse scoring, RRF fusion (docs/05).

Access filtering happens before ranking decisions: the candidate index set is
restricted by role first, so an out of scope document can never reach evidence.
Dense search restricts inside FAISS with an ID selector; sparse search ranks only
allowed candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

from app.ingest.index import load_bm25, load_faiss, tokenize
from app.ingest.manifest import Manifest
from app.providers.embeddings import Embedder
from app.retrieval.roles import Role, allows


@dataclass
class ChunkRow:
    """One metadata row from chunks.jsonl."""

    chunk_id: str
    doc_id: str
    parent_id: str
    page: int
    section_path: str
    text: str
    blurb: str


@dataclass
class ScoredChunk:
    """A chunk with its fusion provenance."""

    row: ChunkRow
    dense_rank: int | None
    sparse_rank: int | None
    fused: float


def load_chunk_rows(meta_dir: Path) -> list[ChunkRow]:
    """Load metadata rows from the chunk snapshot."""
    import json

    rows: list[ChunkRow] = []
    path = meta_dir / "chunks.jsonl"
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        rows.append(
            ChunkRow(
                chunk_id=str(data["chunk_id"]),
                doc_id=str(data["doc_id"]),
                parent_id=str(data["parent_id"]),
                page=int(data["page"]),
                section_path=str(data["section_path"]),
                text=str(data["text"]),
                blurb=str(data.get("blurb", "")),
            )
        )
    return rows


def reciprocal_rank_fusion(rank_lists: list[list[int]], rrf_k: int = 60) -> dict[int, float]:
    """Fuse ranked index lists; a chunk high in several lists dominates."""
    scores: dict[int, float] = {}
    for ranks in rank_lists:
        for position, index in enumerate(ranks):
            scores[index] = scores.get(index, 0.0) + 1.0 / (rrf_k + position + 1)
    return scores


class HybridSearcher:
    """Loads index artifacts once and answers role scoped queries."""

    def __init__(self, index_dir: Path, rows: list[ChunkRow]) -> None:
        self._index_dir = index_dir
        self._rows = rows
        self._faiss_index = load_faiss(index_dir)
        self._bm25 = load_bm25(index_dir)
        manifest = Manifest.load(index_dir / "manifest.json")
        self._departments: dict[str, set[str]] = {}
        for doc_id, record in (manifest.documents.items() if manifest else []):
            raw = record.get("departments", ["general"])
            raw_list = raw if isinstance(raw, list) else ["general"]
            self._departments[doc_id] = {str(item) for item in raw_list}
        self._allowed_cache: dict[frozenset[str] | None, list[int]] = {}

    @property
    def version(self) -> int:
        """Current index version from the manifest."""
        manifest = Manifest.load(self._index_dir / "manifest.json")
        return manifest.version if manifest else 0

    def _allowed_indices(self, role: Role) -> list[int]:
        """Row indices visible to the role, computed once per role."""
        if role.departments in self._allowed_cache:
            return self._allowed_cache[role.departments]
        allowed = [
            i
            for i, row in enumerate(self._rows)
            if allows(role, self._departments.get(row.doc_id, {"general"}))
        ]
        self._allowed_cache[role.departments] = allowed
        return allowed

    def _dense_order(self, question: str, role: Role, k: int, embedder: Embedder) -> list[int]:
        """Dense ranking restricted to allowed rows via an ID selector, with fallback."""
        if self._faiss_index is None:
            raise RuntimeError("FAISS index missing; run make ingest first")
        allowed = self._allowed_indices(role)
        if not allowed:
            return []
        allowed_set = set(allowed)
        query_vector = embedder.embed([question])
        k_eff = min(k, len(allowed))
        try:
            selector = faiss.IDSelectorBatch(np.array(allowed, dtype="int64"))
            params = faiss.SearchParameters()
            params.sel = selector
            _distances, indices = self._faiss_index.search(query_vector, k_eff, params=params)
        except Exception:  # noqa: BLE001, fallback for faiss builds without selector support
            _distances, indices = self._faiss_index.search(query_vector, k * 3)
        return [int(i) for i in indices[0] if int(i) in allowed_set][:k_eff]

    def _sparse_order(self, question: str, role: Role, k: int) -> list[int]:
        """BM25 ranking over allowed candidates only."""
        if self._bm25 is None:
            raise RuntimeError("BM25 artifact missing; run make ingest first")
        allowed = self._allowed_indices(role)
        if not allowed:
            return []
        scores = self._bm25.get_scores(tokenize(question))
        ranked = sorted(allowed, key=lambda i: scores[i], reverse=True)
        return ranked[:k]

    def search(
        self,
        question: str,
        role: Role,
        embedder: Embedder,
        k_dense: int = 20,
        k_sparse: int = 20,
        rrf_k: int = 60,
        mode: str = "hybrid",
    ) -> list[ScoredChunk]:
        """Role scoped hybrid search returning fused candidates in order."""
        dense_order = (
            self._dense_order(question, role, k_dense, embedder)
            if mode in ("hybrid", "dense")
            else []
        )
        sparse_order = (
            self._sparse_order(question, role, k_sparse) if mode in ("hybrid", "bm25") else []
        )
        rank_lists = [order for order in (dense_order, sparse_order) if order]
        fused = reciprocal_rank_fusion(rank_lists, rrf_k=rrf_k)
        dense_rank = {index: position for position, index in enumerate(dense_order)}
        sparse_rank = {index: position for position, index in enumerate(sparse_order)}
        ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)
        return [
            ScoredChunk(
                row=self._rows[index],
                dense_rank=dense_rank.get(index),
                sparse_rank=sparse_rank.get(index),
                fused=score,
            )
            for index, score in ordered
        ]
