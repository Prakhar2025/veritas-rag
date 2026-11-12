"""Request tracing: append only JSONL per day, tail reads for reviewers (docs/07)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class TraceWriter:
    """Writes one JSONL line per request under data/traces/YYYY-MM-DD.jsonl."""

    def __init__(self, trace_dir: Path) -> None:
        self._dir = trace_dir

    def write(self, record: dict[str, object]) -> None:
        """Append one trace record with a server timestamp."""
        self._dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        payload = {"ts": datetime.now(UTC).isoformat(), **record}
        path = self._dir / f"{day}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def recent(self, count: int = 20) -> list[dict[str, object]]:
        """Read the newest records across the latest trace files."""
        if not self._dir.exists():
            return []
        lines: list[str] = []
        for path in sorted(self._dir.glob("*.jsonl"), reverse=True):
            lines.extend(reversed(path.read_text(encoding="utf-8").splitlines()))
            if len(lines) >= count:
                break
        return [json.loads(line) for line in lines[:count] if line.strip()]
