"""Sentence attribution: the model judge plus deterministic guards (docs/06)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.attribution.sentences import numeric_guard_passes, split_sentences
from app.graph.prompts import ATTRIBUTE_SYSTEM, ATTRIBUTE_USER
from app.providers.base import ChatProvider


@dataclass
class SentenceVerdict:
    """One draft sentence with its verification outcome."""

    text: str
    citation: int | None
    verdict: str  # supported | unsupported | unverifiable
    reason: str


def _citation_of(sentence: str) -> int | None:
    """Extract the first [n] citation marker from a sentence."""

    match = re.search(r"\[(\d+)\]", sentence)
    return int(match.group(1)) if match else None


def verify_draft(
    draft: str,
    blocks: list[dict[str, object]],
    chat: ChatProvider,
    model_id: str,
) -> tuple[list[SentenceVerdict], bool]:
    """Verify every draft sentence against its cited block.

    Returns the verdicts and whether any sentence carries a citation at all. A
    sentence without a citation is dropped (no evidence, no sentence). The
    numeric consistency guard overrides the judge: a sentence citing numbers
    that exist nowhere in its source chunk is unsupported regardless of the
    verdict word.
    """
    verdicts: list[SentenceVerdict] = []
    any_citation = False
    for sentence in split_sentences(draft):
        citation = _citation_of(sentence)
        if citation is None:
            verdicts.append(
                SentenceVerdict(text=sentence, citation=None, verdict="unsupported",
                                reason="no citation marker")
            )
            continue
        any_citation = True
        if citation < 1 or citation > len(blocks):
            verdicts.append(
                SentenceVerdict(text=sentence, citation=citation, verdict="unsupported",
                                reason="citation out of range")
            )
            continue
        source = str(blocks[citation - 1].get("text", ""))
        if not numeric_guard_passes(sentence, source):
            verdicts.append(
                SentenceVerdict(text=sentence, citation=citation, verdict="unsupported",
                                reason="numeric guard: numbers absent from source")
            )
            continue
        result = chat.complete(
            purpose="attribute",
            model_id=model_id,
            system=ATTRIBUTE_SYSTEM,
            user=ATTRIBUTE_USER.format(sentence=sentence, source=source[:2000]),
            max_tokens=8,
        )
        verdict = result.text.strip().lower()
        if verdict not in ("supported", "unsupported", "unverifiable"):
            verdict = "unverifiable"
        verdicts.append(
            SentenceVerdict(text=sentence, citation=citation, verdict=verdict, reason="judge")
        )
    return verdicts, any_citation
