"""Provider contracts shared by all chat backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatResult:
    """A completed chat call: text plus token usage."""

    text: str
    input_tokens: int
    output_tokens: int


class ChatProvider(Protocol):
    """Uniform chat interface across bedrock, fake and future backends."""

    def complete(
        self,
        purpose: str,
        model_id: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> ChatResult:
        """Run one completion for a named purpose."""
        ...
