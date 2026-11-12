"""Sentence splitting and the numeric consistency guard (docs/06)."""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def split_sentences(text: str) -> list[str]:
    """Split an answer draft into sentences, keeping citation markers attached."""
    return [sentence.strip() for sentence in _SENTENCE_SPLIT.split(text) if sentence.strip()]


def numbers_in(text: str) -> set[str]:
    """Normalize numeric tokens found in text (strip thousands separators)."""
    return {match.group(0).replace(",", "") for match in _NUMBER.finditer(text)}


def numeric_guard_passes(sentence: str, source_text: str) -> bool:
    """True unless the sentence cites numbers that appear nowhere in its source.

    Citation markers like [1] are excluded from the check; they are pointers, not
    claims. A sentence without numbers always passes; a sentence whose numbers
    exist in the source passes. This guard is deterministic and overrides the
    model judge.
    """
    claim = re.sub(r"\[\d+\]", "", sentence)
    sentence_numbers = numbers_in(claim)
    if not sentence_numbers:
        return True
    source_numbers = numbers_in(source_text)
    return sentence_numbers.issubset(source_numbers)
