"""Grounded pipeline CLI: python -m app.graph "question" --session s1 --role analyst."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.spend import SpendMeter
from app.graph.graph import run_turn
from app.graph.nodes import Runtime
from app.graph.store import SessionStore
from app.providers.base import ChatProvider
from app.providers.bedrock import BedrockChat
from app.providers.embeddings import build_embedder
from app.providers.fake import FakeChat
from app.retrieval.rerank import build_reranker
from app.retrieval.retriever import Retriever


def build_chats(settings, meter):  # type: ignore[no-untyped-def]
    """Build the cheap and main chat providers from configuration."""
    if settings.chat_provider == "bedrock":
        cheap: ChatProvider = BedrockChat(settings.aws_region, settings.aws_profile, meter)
        main: ChatProvider = cheap
    elif settings.chat_provider == "fake":
        cheap = FakeChat(meter)
        main = cheap
    else:
        raise ValueError(f"unknown chat provider '{settings.chat_provider}'")
    return cheap, main


def main() -> int:
    """Parse arguments, run one turn, print the answer with citations."""
    parser = argparse.ArgumentParser(description="Run one grounded conversation turn")
    parser.add_argument("question")
    parser.add_argument("--session", default="demo")
    parser.add_argument("--role", default="analyst")
    args = parser.parse_args()

    settings = get_settings()
    data_dir = Path(settings.data_dir)
    meter = SpendMeter(data_dir / "spend.json", settings.spend_cap_usd)
    cheap, main = build_chats(settings, meter)
    embedder = build_embedder(settings.embeddings_provider, settings.embeddings_model)
    reranker = build_reranker("fastembed")
    runtime = Runtime(
        retriever=Retriever(data_dir, embedder, reranker),
        cheap_chat=cheap,
        main_chat=main,
        settings=settings,
        store=SessionStore(data_dir / "sessions.db"),
    )
    final = run_turn(runtime, args.session, args.question, args.role)
    print(final["answer"])
    if final.get("citations"):
        print()
        for citation in final["citations"]:
            print(f"  [{citation['n']}] {citation['doc']}, page {citation['page']}, "
                  f"{citation['section']}")
    print()
    print(json.dumps(final.get("meta", {}), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
