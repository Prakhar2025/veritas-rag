"""Fetch the public demo corpus with a reproducible manifest (docs/04).

Each catalog slot lists a title, categories and one or more candidate URLs; the
first URL that returns a valid PDF wins. Downloads land in data/corpus/ and are
committed so the repository clones ready to run. The script rewrites SOURCES.md
and catalog.json on every run from what actually landed.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

USER_AGENT = "veritas-rag-corpus-fetch/0.1 (contact: prakhar230125@gmail.com)"
CORPUS_DIR = Path("data/corpus")
MAX_BYTES = 20 * 1024 * 1024

# Each entry: filename, title, category, departments, license, candidate URLs in
# preference order. Slots without a working URL are reported and skipped.
CATALOG: list[dict[str, object]] = [
    {
        "filename": "fed-monetary-policy-report.pdf",
        "title": "Federal Reserve Monetary Policy Report",
        "category": "business and economic report with tables",
        "departments": ["economy", "general"],
        "license": "US Federal Reserve public report",
        "urls": [
            "https://www.federalreserve.gov/monetarypolicy/files/20250627_mprfullreport.pdf",
            "https://www.federalreserve.gov/monetarypolicy/files/20240731_mprfullreport.pdf",
        ],
    },
    {
        "filename": "apple-fy24-q4-financial-statements.pdf",
        "title": "Apple Inc. FY2024 Q4 Consolidated Financial Statements",
        "category": "financial statements with tables",
        "departments": ["finance"],
        "license": "Apple public investor materials",
        "urls": [
            "https://www.apple.com/newsroom/pdfs/fy2024-q4/FY24_Q4_Consolidated_Financial_Statements.pdf",
        ],
    },
    {
        "filename": "berkshire-hathaway-2024-letter.pdf",
        "title": "Berkshire Hathaway 2024 Chairman's Letter",
        "category": "business narrative report",
        "departments": ["business"],
        "license": "Berkshire Hathaway public letter",
        "urls": [
            "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
        ],
    },
    {
        "filename": "nist-sp-800-63b.pdf",
        "title": "NIST Special Publication 800-63B, Digital Identity Guidelines",
        "category": "regulatory and standards text with numbered clauses",
        "departments": ["legal"],
        "license": "NIST public publication",
        "urls": [
            "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63b.pdf",
        ],
    },
    {
        "filename": "attention-is-all-you-need.pdf",
        "title": "Attention Is All You Need (arXiv 1706.03762)",
        "category": "technical whitepaper",
        "departments": ["engineering"],
        "license": "arXiv non-exclusive license",
        "urls": [
            "https://arxiv.org/pdf/1706.03762",
        ],
    },
    {
        "filename": "rag-lewis-et-al-2020.pdf",
        "title": (
            "Retrieval Augmented Generation for Knowledge Intensive NLP Tasks (arXiv 2005.11401)"
        ),
        "category": "technical whitepaper",
        "departments": ["engineering"],
        "license": "arXiv non-exclusive license",
        "urls": [
            "https://arxiv.org/pdf/2005.11401",
        ],
    },
    {
        "filename": "pro-git-book.pdf",
        "title": "Pro Git, second edition",
        "category": "operations and procedure manual",
        "departments": ["engineering", "general"],
        "license": "CC BY-NC-SA 3.0",
        "urls": [
            "https://github.com/progit/progit2/releases/download/2.1.416/progit.pdf",
        ],
    },
]


def _looks_like_pdf(payload: bytes) -> bool:
    return payload[:5] == b"%PDF-" and len(payload) > 10_000


def fetch_one(url: str) -> bytes | None:
    """Download a URL with a proper user agent; None on any failure."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            print(f"    too large: {url}")
            return None
        if not _looks_like_pdf(payload):
            print(f"    not a pdf: {url}")
            return None
        return payload
    except Exception as exc:  # noqa: BLE001, per URL resilience by design
        print(f"    failed: {url} ({exc})")
        return None


def main() -> int:
    """Fetch every catalog slot and regenerate SOURCES.md and catalog.json."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    landed: list[dict[str, object]] = []
    for entry in CATALOG:
        target = CORPUS_DIR / str(entry["filename"])
        if target.exists() and target.stat().st_size > 10_000:
            print(f"have: {entry['filename']}")
            landed.append(entry)
            continue
        print(f"fetching: {entry['title']}")
        for url in entry["urls"]:  # type: ignore[union-attr]
            payload = fetch_one(url)
            if payload is None:
                continue
            target.write_bytes(payload)
            print(f"    saved {target.name} ({len(payload) / 1e6:.1f} MB)")
            landed.append(entry)
            break
        else:
            print(f"    SLOT MISSED: {entry['title']}")

    catalog_payload = [
        {
            "filename": entry["filename"],
            "title": entry["title"],
            "category": entry["category"],
            "departments": entry["departments"],
        }
        for entry in landed
    ]
    (CORPUS_DIR / "catalog.json").write_text(
        json.dumps(catalog_payload, indent=2), encoding="utf-8"
    )

    lines = [
        "# Corpus Sources",
        "",
        "Every document is a public report fetched for the demo corpus.",
        "",
    ]
    for entry in landed:
        size_mb = (CORPUS_DIR / str(entry["filename"])).stat().st_size / 1e6
        lines.append(f"## {entry['title']}")
        lines.append("")
        lines.append(f"- File: `{entry['filename']}` ({size_mb:.1f} MB)")
        lines.append(f"- Category: {entry['category']}")
        lines.append(f"- Departments: {', '.join(entry['departments'])}")  # type: ignore[arg-type]
        lines.append(f"- License: {entry['license']}")
        lines.append(f"- Source: {entry['urls'][0]}")  # type: ignore[index]
        lines.append("")
    (CORPUS_DIR / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")
    total_mb = sum((CORPUS_DIR / str(entry["filename"])).stat().st_size for entry in landed) / 1e6
    print(f"\ncorpus: {len(landed)} documents, {total_mb:.1f} MB total")
    return 0 if landed else 1


if __name__ == "__main__":
    sys.exit(main())
