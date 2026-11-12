"""Unit tests for reciprocal rank fusion and role resolution."""

from __future__ import annotations

import pytest

from app.retrieval.roles import allows, resolve_role
from app.retrieval.search import reciprocal_rank_fusion


def test_rrf_known_ordering() -> None:
    scores = reciprocal_rank_fusion([[0, 1, 2], [1, 3]], rrf_k=60)
    # index 1 appears second in list one and first in list two, so it wins.
    assert sorted(scores, key=scores.get, reverse=True) == [1, 0, 3, 2]  # type: ignore[arg-type]


def test_rrf_single_list_preserves_order() -> None:
    scores = reciprocal_rank_fusion([[7, 9, 2]])
    assert sorted(scores, key=scores.get, reverse=True) == [7, 9, 2]  # type: ignore[arg-type]


def test_rrf_k_changes_spread_not_order_for_single_list() -> None:
    one = reciprocal_rank_fusion([[0, 1]], rrf_k=1)
    two = reciprocal_rank_fusion([[0, 1]], rrf_k=100)
    assert sorted(one, key=one.get, reverse=True) == sorted(  # type: ignore[arg-type]
        two, key=two.get, reverse=True
    )


def test_resolve_known_roles() -> None:
    analyst = resolve_role("analyst")
    assert analyst.departments is None
    external = resolve_role("external")
    assert external.departments == frozenset({"general"})


def test_resolve_unknown_role_raises() -> None:
    with pytest.raises(KeyError):
        resolve_role("nobody")


def test_allows_semantics() -> None:
    external = resolve_role("external")
    assert allows(external, {"general"})
    assert not allows(external, {"finance"})
    analyst = resolve_role("analyst")
    assert allows(analyst, {"finance", "anything"})
