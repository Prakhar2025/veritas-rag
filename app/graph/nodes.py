"""Graph node factories. Each factory closes over the runtime and returns a node
callable with the LangGraph signature: state in, partial state out."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from app.attribution.verifier import verify_draft
from app.core.config import Settings
from app.graph.prompts import (
    CONDENSE_SYSTEM,
    CONDENSE_USER,
    GENERATE_SYSTEM,
    GENERATE_USER,
    GRADE_SYSTEM,
    GRADE_USER,
    PROMPT_VERSION,
)
from app.graph.state import PipelineState
from app.graph.store import SessionStore, StoredMessage
from app.providers.base import ChatProvider
from app.retrieval.retriever import Retriever
from app.retrieval.roles import resolve_role


@dataclass
class Runtime:
    """Shared dependencies for the graph nodes."""

    retriever: Retriever
    cheap_chat: ChatProvider
    main_chat: ChatProvider
    settings: Settings
    store: SessionStore


def _history_text(history: list[dict[str, str]]) -> str:
    """Render recent turns compactly for the condense prompt."""
    lines = [
        f"{turn['role']}: {turn['content'][:200]}" for turn in history
    ]
    return "\n".join(lines) if lines else "(none)"


def _evidence_text(blocks: list[dict[str, object]]) -> str:
    """Render numbered evidence blocks; document content stays inside the slot."""
    parts = []
    for block in blocks:
        parts.append(
            f"[{block['number']}] {block['doc_title']}, page {block['page']}, "
            f"section {block['section_path']}\n{block['text']}"
        )
    return "\n\n".join(parts)


def make_condense(runtime: Runtime) -> Callable[[PipelineState], dict]:
    """Rewrite the question into standalone form when history exists."""

    def condense(state: PipelineState) -> dict:
        start = time.perf_counter()
        question = state["question"]
        rewritten = question
        if state.get("history"):
            result = runtime.cheap_chat.complete(
                purpose="condense",
                model_id=runtime.settings.nova_micro_model_id,
                system=CONDENSE_SYSTEM,
                user=CONDENSE_USER.format(
                    history=_history_text(state["history"]), question=question
                ),
                max_tokens=120,
            )
            candidate = result.text.strip().strip('"')
            if candidate:
                rewritten = candidate
        return {"rewritten": rewritten, "meta": {"condense_ms": _ms(start)}}

    return condense


def make_retrieve(runtime: Runtime) -> Callable[[PipelineState], dict]:
    """Role scoped retrieval with permission versus no evidence distinction."""

    def retrieve(state: PipelineState) -> dict:
        start = time.perf_counter()
        role = resolve_role(state["role"])
        blocks = runtime.retriever.retrieve(state["rewritten"], role=state["role"])
        refusal: str | None = None
        if not blocks:
            if role.departments is not None:
                unrestricted = runtime.retriever.retrieve(
                    state["rewritten"], role="analyst"
                )
                refusal = "permission" if unrestricted else "no_evidence"
            else:
                refusal = "no_evidence"
        elif role.departments is not None:
            # A restricted role that still sees some documents must not answer
            # from wrong domain evidence: if the strongest unrestricted evidence
            # sits outside the set this role can see, deny access. Fail closed.
            unrestricted = runtime.retriever.retrieve(state["rewritten"], role="analyst")
            allowed_ids = {block.doc_id for block in blocks}
            if unrestricted and unrestricted[0].doc_id not in allowed_ids:
                refusal = "permission"
        serialized = [
            {
                "number": block.number,
                "doc_id": block.doc_id,
                "doc_title": block.doc_title,
                "page": block.page,
                "section_path": block.section_path,
                "text": block.text,
            }
            for block in blocks
        ]
        return {"blocks": serialized, "refusal": refusal, "meta": {"retrieve_ms": _ms(start)}}

    return retrieve


def make_grade(runtime: Runtime) -> Callable[[PipelineState], dict]:
    """Evidence relevance gate; weak evidence short circuits to refusal."""

    def grade(state: PipelineState) -> dict:
        start = time.perf_counter()
        result = runtime.cheap_chat.complete(
            purpose="grade",
            model_id=runtime.settings.nova_micro_model_id,
            system=GRADE_SYSTEM,
            user=GRADE_USER.format(
                question=state["rewritten"], evidence=_evidence_text(state["blocks"])
            ),
            max_tokens=4,
        )
        verdict = result.text.strip().lower()
        if "irrelevant" in verdict:
            return {"grade": "irrelevant", "refusal": "irrelevant_evidence",
                    "meta": {"grade_ms": _ms(start)}}
        return {"grade": "relevant", "meta": {"grade_ms": _ms(start)}}

    return grade


def make_generate(runtime: Runtime) -> Callable[[PipelineState], dict]:
    """Grounded draft generation with inline citations."""

    def generate(state: PipelineState) -> dict:
        start = time.perf_counter()
        result = runtime.main_chat.complete(
            purpose="generate",
            model_id=runtime.settings.generator_model_id,
            system=GENERATE_SYSTEM,
            user=GENERATE_USER.format(
                question=state["rewritten"], evidence=_evidence_text(state["blocks"])
            ),
            max_tokens=600,
        )
        draft = result.text.strip()
        refusal: str | None = None
        if "INSUFFICIENT_EVIDENCE" in draft:
            refusal = "insufficient"
        return {"draft": draft, "refusal": refusal, "meta": {"generate_ms": _ms(start)}}

    return generate


def make_attribute(runtime: Runtime) -> Callable[[PipelineState], dict]:
    """Sentence level verification: keep supported sentences, drop the rest."""

    def attribute(state: PipelineState) -> dict:
        start = time.perf_counter()
        verdicts, _any = verify_draft(
            state["draft"], state["blocks"], runtime.cheap_chat,
            runtime.settings.nova_micro_model_id,
        )
        kept = [v for v in verdicts if v.verdict == "supported"]
        refusal: str | None = None
        if not kept:
            refusal = "unsupported"
        sentences = [
            {"text": v.text, "citation": v.citation, "verdict": v.verdict}
            for v in verdicts
        ]
        return {
            "sentences": sentences,
            "refusal": refusal,
            "meta": {"attribute_ms": _ms(start), "kept": len(kept)},
        }

    return attribute


def make_finalize(runtime: Runtime) -> Callable[[PipelineState], dict]:
    """Assemble the final answer, persist the turn, build the citation list."""

    def finalize(state: PipelineState) -> dict:
        start = time.perf_counter()
        refusal = state.get("refusal")
        if refusal:
            from app.graph.prompts import REFUSAL_TEMPLATES

            answer = REFUSAL_TEMPLATES.get(refusal, REFUSAL_TEMPLATES["no_evidence"])
            citations: list[dict[str, object]] = []
        else:
            sentences = [s for s in state.get("sentences", []) if s["verdict"] == "supported"]
            answer = " ".join(str(s["text"]) for s in sentences)
            used = sorted(
                {cast(int, s["citation"]) for s in sentences if s["citation"] is not None}
            )
            citations = [
                {
                    "n": n,
                    "doc": str(block["doc_title"]),
                    "page": block["page"],
                    "section": block["section_path"],
                }
                for n in used
                for block in state["blocks"]
                if block["number"] == n
            ]
        runtime.store.append(
            state["session_id"],
            StoredMessage(role="user", content=state["question"], citations=[]),
        )
        runtime.store.append(
            state["session_id"],
            StoredMessage(role="assistant", content=answer, citations=citations),
        )
        meta = dict(state.get("meta", {}))
        meta["finalize_ms"] = _ms(start)
        meta["refusal"] = refusal
        meta["prompt_version"] = PROMPT_VERSION
        return {"answer": answer, "citations": citations, "meta": meta}

    return finalize


def _ms(start: float) -> float:
    """Elapsed milliseconds since a start timestamp."""
    return round((time.perf_counter() - start) * 1000, 1)
