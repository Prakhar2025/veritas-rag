"""Unit tests for the semantic question cache."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.retrieval.cache import QuestionCache


def _vec(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(8)
    return (vector / np.linalg.norm(vector)).astype("float32")


def test_hit_on_same_question_same_version(tmp_path: Path) -> None:
    cache = QuestionCache(tmp_path / "questions.jsonl", threshold=0.95)
    cache.put("What was Apple net sales?", _vec(1), 3, {"answer": "x"})
    entry = cache.lookup("What was Apple net sales?", _vec(1), 3)
    assert entry is not None
    assert entry.payload == {"answer": "x"}


def test_miss_on_version_mismatch(tmp_path: Path) -> None:
    cache = QuestionCache(tmp_path / "questions.jsonl", threshold=0.95)
    cache.put("question one", _vec(1), 3, {"answer": "old"})
    assert cache.lookup("question one", _vec(1), 4) is None, "version bump invalidates"


def test_miss_on_different_question(tmp_path: Path) -> None:
    cache = QuestionCache(tmp_path / "questions.jsonl", threshold=0.95)
    cache.put("question one", _vec(1), 3, {"answer": "x"})
    assert cache.lookup("question two", _vec(2), 3) is None


def test_persistence_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "questions.jsonl"
    first = QuestionCache(path, threshold=0.95)
    first.put("question one", _vec(1), 3, {"answer": "x"})
    second = QuestionCache(path, threshold=0.95)
    assert second.lookup("question one", _vec(1), 3) is not None


def test_clear_drops_everything(tmp_path: Path) -> None:
    path = tmp_path / "questions.jsonl"
    cache = QuestionCache(path, threshold=0.95)
    cache.put("question one", _vec(1), 3, {"answer": "x"})
    cache.clear()
    assert cache.lookup("question one", _vec(1), 3) is None
    assert not path.exists()
