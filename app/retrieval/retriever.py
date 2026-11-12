"""Retrieval orchestration: role scoped hybrid search, rerank, parent expansion.

Small chunks are what get scored; parents are what generation reads (docs/05 small
to big). Citations resolve to the small chunk's page, so precision survives the
expansion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.providers.embeddings import Embedder
from app.retrieval.rerank import Reranker
from app.retrieval.roles import resolve_role
from app.retrieval.search import HybridSearcher, ScoredChunk, load_chunk_rows


@dataclass
class EvidenceBlock:
    """A numbered evidence block for generation."""

    number: int
    doc_id: str
    doc_title: str
    page: int
    section_path: str
    text: str
    chunk_ids: list[str] = field(default_factory=list)
    fused: float = 0.0
    rerank_score: float | None = None


class Retriever:
    """Loads artifacts once and answers role scoped questions with evidence blocks."""

    def __init__(
        self,
        data_dir: Path,
        embedder: Embedder,
        reranker: Reranker | None = None,
    ) -> None:
        index_dir = data_dir / "indexes"
        self._searcher = HybridSearcher(index_dir, load_chunk_rows(index_dir / "meta"))
        manifest_rows = self._load_parents(index_dir / "meta" / "parents.jsonl")
        self._parents: dict[str, dict[str, object]] = {
            str(row["parent_id"]): row for row in manifest_rows
        }
        from app.ingest.manifest import Manifest

        manifest = Manifest.load(index_dir / "manifest.json")
        self._doc_titles: dict[str, str] = {
            doc_id: str(record.get("title", doc_id))
            for doc_id, record in (manifest.documents.items() if manifest else [])
        }
        self.version = self._searcher.version
        self._embedder = embedder
        self._reranker = reranker

    @staticmethod
    def _load_parents(path: Path) -> list[dict[str, object]]:
        """Load parent rows from the snapshot."""
        from app.ingest.index import read_jsonl

        return read_jsonl(path)

    def retrieve(
        self,
        question: str,
        role: str = "analyst",
        k_dense: int = 20,
        k_sparse: int = 20,
        rrf_k: int = 60,
        top_n: int = 5,
        mode: str = "hybrid",
        use_rerank: bool = True,
    ) -> list[EvidenceBlock]:
        """Run retrieval and return numbered parent evidence blocks."""
        resolved = resolve_role(role)
        candidates: list[ScoredChunk] = self._searcher.search(
            question,
            resolved,
            self._embedder,
            k_dense=k_dense,
            k_sparse=k_sparse,
            rrf_k=rrf_k,
            mode=mode,
        )
        selected = candidates[:top_n]
        score_by_id: dict[str, float] = {}
        if use_rerank and self._reranker is not None and len(selected) > 1:
            scores = self._reranker.rerank(
                question, [f"{chunk.row.blurb}\n{chunk.row.text}" for chunk in selected]
            )
            pairs = sorted(
                zip(selected, scores, strict=True), key=lambda pair: pair[1], reverse=True
            )
            selected = [chunk for chunk, _score in pairs[:top_n]]
            score_by_id = {chunk.row.chunk_id: score for chunk, score in pairs}

        blocks: list[EvidenceBlock] = []
        seen_parents: set[str] = set()
        for chunk in selected:
            if chunk.row.parent_id in seen_parents:
                continue
            seen_parents.add(chunk.row.parent_id)
            parent = self._parents.get(chunk.row.parent_id, {})
            blocks.append(
                EvidenceBlock(
                    number=len(blocks) + 1,
                    doc_id=chunk.row.doc_id,
                    doc_title=self._doc_titles.get(chunk.row.doc_id, chunk.row.doc_id),
                    page=chunk.row.page,
                    section_path=chunk.row.section_path,
                    text=str(parent.get("text", chunk.row.text)),
                    chunk_ids=[chunk.row.chunk_id],
                    fused=chunk.fused,
                    rerank_score=score_by_id.get(chunk.row.chunk_id),
                )
            )
        return blocks
