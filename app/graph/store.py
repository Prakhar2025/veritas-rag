"""SQLite session store: durable conversation history (docs/03, docs/06)."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StoredMessage:
    """One persisted conversation turn."""

    role: str
    content: str
    citations: list[dict[str, object]]


class SessionStore:
    """Message history per session id, surviving restarts."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # The service runs requests on worker threads; one shared connection is
        # guarded by a lock for writes.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            " session_id TEXT NOT NULL, seq INTEGER NOT NULL,"
            " role TEXT NOT NULL, content TEXT NOT NULL, citations TEXT NOT NULL,"
            " PRIMARY KEY (session_id, seq))"
        )
        self._conn.commit()

    def history(self, session_id: str, limit: int = 6) -> list[dict[str, str]]:
        """Recent turns for the condense node, oldest first."""
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? "
            "ORDER BY seq DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def append(self, session_id: str, message: StoredMessage) -> None:
        """Append one turn."""
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (session_id, seq, role, content, citations)"
                " VALUES (?, ?, ?, ?, ?)",
                (session_id, int(row[0]) + 1, message.role, message.content,
                 json.dumps(message.citations)),
            )
            self._conn.commit()

    def list_sessions(self) -> list[dict[str, object]]:
        """All sessions with message counts, newest first."""
        rows = self._conn.execute(
            "SELECT session_id, COUNT(*), MAX(seq) FROM messages "
            "GROUP BY session_id ORDER BY MAX(seq) DESC"
        ).fetchall()
        return [
            {"id": r[0], "messages": int(r[1])} for r in rows
        ]

    def messages(self, session_id: str) -> list[StoredMessage]:
        """Full history for one session, oldest first."""
        rows = self._conn.execute(
            "SELECT role, content, citations FROM messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [
            StoredMessage(role=r[0], content=r[1], citations=json.loads(r[2]))
            for r in rows
        ]

    def delete_session(self, session_id: str) -> None:
        """Remove a session's history and any graph checkpoint rows."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,)
            )
            for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
                try:
                    self._conn.execute(
                        f"DELETE FROM {table} WHERE thread_id = ?", (session_id,)
                    )
                except sqlite3.OperationalError:
                    pass
            self._conn.commit()
