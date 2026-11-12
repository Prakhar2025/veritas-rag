"""Shared test fixtures: fixture PDFs built in code, never downloaded."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def build_pdf(path: Path, page_texts: list[str]) -> None:
    """Write a minimal valid PDF whose pages carry the given text lines."""
    import fitz

    document = fitz.open()
    for text in page_texts:
        page = document.new_page()
        y = 72
        for line in text.splitlines():
            size = 16 if line.strip().startswith("#") else 11
            page.insert_text((72, y), line, fontsize=size)
            y += size + 8
    document.save(str(path))
    document.close()


@pytest.fixture
def fixture_corpus(tmp_path: Path) -> Path:
    """A two document corpus with a catalog, built entirely in code."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    build_pdf(
        corpus_dir / "alpha-report.pdf",
        [
            "# Alpha Overview",
            "Alpha is a demonstration document about operating margins.",
            "The FY2025 operating margin reached 23.4 percent, up 340 basis points.",
            "# Alpha Risk Factors",
            "Supply chain costs stay volatile and currency swings keep hurting imports.",
        ],
    )
    build_pdf(
        corpus_dir / "beta-manual.pdf",
        [
            "# Beta Operations Manual",
            "Step one: power the device and wait for the green status light.",
            "Step two: run calibration, which takes about four minutes.",
            "Troubleshooting: a blinking amber light means the sensor door is open.",
        ],
    )
    catalog = [
        {"filename": "alpha-report.pdf", "title": "Alpha Report", "departments": ["finance"]},
        {"filename": "beta-manual.pdf", "title": "Beta Manual", "departments": ["engineering"]},
    ]
    (corpus_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    return corpus_dir


def ingest_fixture(tmp_path: Path, fixture_corpus: Path) -> Path:
    """Ingest the fixture corpus with deterministic providers; return the data dir."""
    from app.core.config import Settings
    from app.core.spend import SpendMeter
    from app.ingest.pipeline import run_ingest
    from app.providers.embeddings import HashEmbedder
    from app.providers.fake import FakeChat

    settings = Settings(
        data_dir=str(tmp_path / "data"),
        chat_provider="fake",
        embeddings_provider="hash",
        _env_file=None,  # type: ignore[call-arg]
    )
    meter = SpendMeter(Path(settings.data_dir) / "spend.json", settings.spend_cap_usd)
    run_ingest(
        corpus_dir=fixture_corpus,
        data_dir=Path(settings.data_dir),
        chat=FakeChat(meter),
        embedder=HashEmbedder(),
        settings=settings,
    )
    return Path(settings.data_dir)
