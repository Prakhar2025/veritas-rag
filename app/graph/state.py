"""Pipeline state shared across graph nodes."""

from __future__ import annotations

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    """State carried through the grounded pipeline."""

    session_id: str
    role: str
    question: str
    rewritten: str
    history: list[dict[str, str]]
    blocks: list[dict[str, object]]
    grade: str
    draft: str
    sentences: list[dict[str, object]]
    answer: str
    citations: list[dict[str, object]]
    refusal: str | None
    meta: dict[str, object]
