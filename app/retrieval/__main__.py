"""Retrieval CLI: standalone queries and baselines without generation.

Examples:
    python -m app.retrieval "What was Apple's FY2024 net sales?"
    python -m app.retrieval "..." --role external
    python -m app.retrieval "..." --mode dense --no-rerank   (dense only baseline)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.providers.embeddings import build_embedder
from app.retrieval.rerank import build_reranker
from app.retrieval.retriever import Retriever


def main() -> int:
    """Parse arguments, run retrieval, print a ranked evidence table."""
    parser = argparse.ArgumentParser(
        description="Query the retrieval engine without generation"
    )
    parser.add_argument("question", help="natural language question")
    parser.add_argument("--role", default="analyst", help="role name for access filtering")
    parser.add_argument("--mode", default="hybrid", choices=["hybrid", "dense", "bm25"])
    parser.add_argument(
        "--no-rerank", action="store_true", help="skip the cross encoder (baseline)"
    )
    parser.add_argument("--top-n", type=int, default=5, help="evidence blocks to show")
    args = parser.parse_args()

    settings = get_settings()
    embedder = build_embedder(settings.embeddings_provider, settings.embeddings_model)
    reranker = None if args.no_rerank else build_reranker("fastembed")
    retriever = Retriever(Path(settings.data_dir), embedder, reranker)

    blocks = retriever.retrieve(
        args.question,
        role=args.role,
        top_n=args.top_n,
        mode=args.mode,
        use_rerank=not args.no_rerank,
    )
    print(f"index version: {retriever.version}")
    print(f"{'#':>2}  {'score':>7}  {'doc':<44}  {'pg':>4}  section")
    for block in blocks:
        score = (
            f"{block.rerank_score:.3f}"
            if block.rerank_score is not None
            else f"{block.fused:.4f}"
        )
        title = block.doc_title[:44]
        print(
            f"{block.number:>2}  {score:>7}  {title:<44}  {block.page:>4}  "
            f"{block.section_path[:60]}"
        )
    if not blocks:
        print("no evidence found for the visible role")
    return 0


if __name__ == "__main__":
    sys.exit(main())
