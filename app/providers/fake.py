"""Deterministic fake provider for tests. Same interface as BedrockChat, zero network."""

from __future__ import annotations

import hashlib

from app.core.spend import SpendMeter
from app.providers.base import ChatResult


class FakeChat:
    """Purpose keyed deterministic responses. Extends as pipeline purposes land."""

    def __init__(self, meter: SpendMeter) -> None:
        self._meter = meter

    def complete(
        self,
        purpose: str,
        model_id: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> ChatResult:
        """Return a deterministic response for a known purpose."""
        if purpose == "contextualize":
            return ChatResult(text=self._contextualize(user), input_tokens=10, output_tokens=6)
        raise KeyError(f"fake provider has no behavior for purpose '{purpose}'")

    def _contextualize(self, user: str) -> str:
        """Deterministic blurb list: one BLUR line per numbered chunk in the batch."""
        lines: list[str] = []
        for raw in user.splitlines():
            line = raw.strip()
            if line.startswith("C") and "|" in line:
                marker, _, body = line.partition("|")
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:6]
                lines.append(f"{marker}: This chunk belongs to the ingested corpus; "
                             f"content digest {digest}.")
        return "\n".join(lines)
