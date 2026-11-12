"""Spend meter for provider calls (CLAUDE.md Section 8, bounded spend).

Ledger is a local JSON file. Every script that spends money prints its running
total and enforces the configured cap before making calls, not after.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Approximate USD price per token. Nova Micro list price: 0.035 USD per 1M input,
# 0.14 USD per 1M output. Any model without an entry is priced at zero and reported.
PRICE_PER_TOKEN: dict[str, tuple[float, float]] = {
    "amazon.nova-micro": (0.000000035, 0.00000014),
    "amazon.nova-lite": (0.00000006, 0.00000024),
    "amazon.nova-pro": (0.0000008, 0.0000032),
}


class SpendCapExceeded(RuntimeError):
    """Raised before a call that would push total spend over the configured cap."""


@dataclass
class SpendRecord:
    """One recorded provider call."""

    purpose: str
    model: str
    input_tokens: int
    output_tokens: int
    usd: float


class SpendMeter:
    """Persistent spend ledger with a hard cap."""

    def __init__(self, ledger_path: Path, cap_usd: float) -> None:
        self._path = ledger_path
        self._cap = cap_usd
        self._usd = 0.0
        self._calls = 0
        self._by_purpose: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._usd = float(data.get("usd", 0.0))
        self._calls = int(data.get("calls", 0))
        self._by_purpose = {
            purpose: {"usd": float(entry.get("usd", 0.0)), "calls": float(entry.get("calls", 0))}
            for purpose, entry in data.get("by_purpose", {}).items()
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"usd": self._usd, "calls": self._calls, "by_purpose": self._by_purpose}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @property
    def total_usd(self) -> float:
        """Total spend recorded so far."""
        return self._usd

    def price_for(self, model: str) -> tuple[float, float]:
        """Return (input, output) price per token for a model id, best prefix match."""
        for prefix, price in PRICE_PER_TOKEN.items():
            if model.startswith(prefix):
                return price
        return (0.0, 0.0)

    def check_headroom(self, estimated_usd: float) -> None:
        """Raise SpendCapExceeded if the estimate would exceed the cap."""
        if self._usd + estimated_usd > self._cap:
            raise SpendCapExceeded(
                f"cap {self._cap:.2f} USD exceeded at {self._usd:.4f} USD "
                f"(estimated call {estimated_usd:.4f} USD)"
            )

    def record(
        self, purpose: str, model: str, input_tokens: int, output_tokens: int
    ) -> SpendRecord:
        """Record one call and persist the ledger."""
        price_in, price_out = self.price_for(model)
        cost = price_in * input_tokens + price_out * output_tokens
        record = SpendRecord(purpose, model, input_tokens, output_tokens, cost)
        self._usd += cost
        self._calls += 1
        entry = self._by_purpose.setdefault(purpose, {"usd": 0.0, "calls": 0.0})
        entry["usd"] += cost
        entry["calls"] += 1.0
        self._save()
        return record

    def summary(self) -> str:
        """Human readable spend summary."""
        lines = [
            f"spend: {self._usd:.4f} USD of {self._cap:.2f} USD cap, {self._calls} calls"
        ]
        for purpose, entry in sorted(self._by_purpose.items()):
            lines.append(f"  {purpose}: {int(entry['calls'])} calls, {entry['usd']:.4f} USD")
        return "\n".join(lines)
