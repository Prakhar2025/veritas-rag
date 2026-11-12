"""Unit tests for sentence splitting and the numeric consistency guard."""

from __future__ import annotations

from app.attribution.sentences import (
    numbers_in,
    numeric_guard_passes,
    split_sentences,
)


def test_split_keeps_citations_attached() -> None:
    draft = "The margin reached 23.4 percent [1]. Supply costs stayed volatile [2]."
    sentences = split_sentences(draft)
    assert len(sentences) == 2
    assert "[1]" in sentences[0]
    assert "[2]" in sentences[1]


def test_numbers_normalization() -> None:
    assert numbers_in("revenue of 1,234 and 56.7") == {"1234", "56.7"}


def test_guard_passes_sentence_without_numbers() -> None:
    assert numeric_guard_passes("Costs stayed volatile [1].", "anything at all")


def test_guard_passes_when_numbers_exist_in_source() -> None:
    assert numeric_guard_passes(
        "The margin reached 23.4 percent [1].", "margin was 23.4 percent in FY2025"
    )


def test_guard_fails_when_numbers_absent_from_source() -> None:
    assert not numeric_guard_passes(
        "The margin reached 99.9 percent [1].", "margin was 23.4 percent in FY2025"
    )
