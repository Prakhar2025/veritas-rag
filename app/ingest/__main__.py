"""Ingestion CLI: python -m app.ingest [--skip-contextualize] [--force]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.spend import SpendMeter
from app.ingest.pipeline import run_ingest
from app.providers.base import ChatProvider
from app.providers.bedrock import BedrockChat
from app.providers.embeddings import build_embedder
from app.providers.fake import FakeChat


def build_chat(settings: Settings, meter: SpendMeter) -> ChatProvider:
    """Build the configured chat provider."""
    if settings.chat_provider == "bedrock":
        return BedrockChat(settings.aws_region, settings.aws_profile, meter)
    if settings.chat_provider == "fake":
        return FakeChat(meter)
    raise ValueError(f"unknown chat provider '{settings.chat_provider}'")


def main() -> int:
    """Parse arguments, run ingestion, print the report and spend summary."""
    parser = argparse.ArgumentParser(description="Ingest the PDF corpus into the hybrid index")
    parser.add_argument(
        "--skip-contextualize", action="store_true", help="offline run, no LLM calls"
    )
    parser.add_argument("--force", action="store_true", help="reprocess even unchanged documents")
    args = parser.parse_args()

    settings = get_settings()
    data_dir = Path(settings.data_dir)
    meter = SpendMeter(data_dir / "spend.json", settings.spend_cap_usd)
    chat = build_chat(settings, meter)
    embedder = build_embedder(settings.embeddings_provider, settings.embeddings_model)

    report = run_ingest(
        corpus_dir=Path("data/corpus"),
        data_dir=data_dir,
        chat=chat,
        embedder=embedder,
        settings=settings,
        skip_contextualize=args.skip_contextualize,
        force=args.force,
    )
    print(report.summary())
    print(meter.summary())
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
