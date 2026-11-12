"""Index manifest: document hashes, config fingerprint and index version (docs/04)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


def config_fingerprint(params: dict[str, object]) -> str:
    """Stable hash of the parameters that define index compatibility."""
    payload = json.dumps(params, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class Manifest:
    """Persistent state deciding what a re ingestion must do."""

    version: int = 0
    fingerprint: str = ""
    documents: dict[str, dict[str, object]] = field(default_factory=dict)

    @staticmethod
    def load(path: Path) -> Manifest | None:
        """Load the manifest if it exists, else None."""
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Manifest(
            version=int(data["version"]),
            fingerprint=str(data.get("fingerprint", "")),
            documents=dict(data.get("documents", {})),
        )

    def save(self, path: Path) -> None:
        """Persist the manifest atomically."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"version": self.version, "fingerprint": self.fingerprint,
                 "documents": self.documents},
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(path)

    def doc_by_sha(self, sha256: str) -> dict[str, object] | None:
        """Return the stored record for a content hash, if present."""
        for record in self.documents.values():
            if record.get("sha256") == sha256:
                return record
        return None

    def upsert(self, doc_id: str, record: dict[str, object]) -> None:
        """Insert or replace one document record."""
        self.documents[doc_id] = record

    def drop(self, doc_id: str) -> None:
        """Remove a document record."""
        self.documents.pop(doc_id, None)
