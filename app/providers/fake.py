"""Deterministic fake provider for tests. Same interface as BedrockChat, zero network.

Default behaviors cover every pipeline purpose. Tests can override any purpose
with a literal response via the responses mapping to drive refusal paths.
"""

from __future__ import annotations

import hashlib
import re

from app.core.spend import SpendMeter
from app.providers.base import ChatResult

_QUESTION_PATTERN = re.compile(r"Follow up question:\s*(.+?)\n\nStandalone question:")


class FakeChat:
    """Purpose keyed deterministic responses, optionally scripted per purpose."""

    def __init__(self, meter: SpendMeter, responses: dict[str, str] | None = None) -> None:
        self._meter = meter
        self._responses = responses or {}

    def complete(
        self,
        purpose: str,
        model_id: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> ChatResult:
        """Return the scripted response for a purpose, else its default."""
        scripted = self._responses.get(purpose)
        if scripted is not None:
            return ChatResult(text=scripted, input_tokens=5, output_tokens=5)
        if purpose == "contextualize":
            return ChatResult(text=self._contextualize(user), input_tokens=10, output_tokens=6)
        if purpose == "condense":
            match = _QUESTION_PATTERN.search(user)
            return ChatResult(
                text=match.group(1).strip() if match else user.strip(),
                input_tokens=5,
                output_tokens=5,
            )
        if purpose == "grade":
            return ChatResult(text="relevant", input_tokens=5, output_tokens=1)
        if purpose == "generate":
            return ChatResult(
                text="The documents discuss this topic directly [1].",
                input_tokens=5,
                output_tokens=10,
            )
        if purpose == "attribute":
            return ChatResult(text="supported", input_tokens=5, output_tokens=1)
        raise KeyError(f"fake provider has no behavior for purpose '{purpose}'")

    def _contextualize(self, user: str) -> str:
        """Deterministic blurb list: one BLUR line per numbered chunk in the batch."""
        lines: list[str] = []
        for raw in user.splitlines():
            line = raw.strip()
            if line.startswith("C") and "|" in line:
                marker, _, body = line.partition("|")
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:6]
                lines.append(
                    f"{marker}: This chunk belongs to the ingested corpus; "
                    f"content digest {digest}."
                )
        return "\n".join(lines)
