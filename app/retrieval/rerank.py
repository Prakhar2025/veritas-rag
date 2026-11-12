"""Cross encoder reranking via fastembed ONNX (torch free), with deterministic doubles."""

from __future__ import annotations

from typing import Protocol


class Reranker(Protocol):
    """Uniform reranker interface: relevance scores for query and chunk pairs."""

    model_name: str

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Score every text against the query; higher means more relevant."""
        ...


class FastEmbedReranker:
    """ONNX cross encoder via fastembed. Model loads lazily on first use."""

    def __init__(self, model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._model: object | None = None

    def _ensure_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            # fastembed 0.4.x keeps the cross encoder outside the top level namespace
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(model_name=self.model_name)
        return self._model

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Score query and chunk pairs with the local cross encoder."""
        model = self._ensure_model()
        return [float(score) for score in model.rerank(query, texts)]


class IdentityReranker:
    """Deterministic double for tests: preserves input order, scores by rank."""

    model_name = "identity"

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Score by input position so the first text always wins."""
        return [float(len(texts) - position) for position in range(len(texts))]


def build_reranker(provider: str, model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2") -> Reranker:
    """Build the configured reranker; identity is the deterministic test path."""
    if provider == "fastembed":
        return FastEmbedReranker(model_name)
    if provider == "identity":
        return IdentityReranker()
    raise ValueError(f"unknown reranker provider '{provider}'")
