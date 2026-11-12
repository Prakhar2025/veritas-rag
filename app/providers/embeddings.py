"""Embedding providers: fastembed (torch free) and a deterministic hash embedder for tests."""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """Uniform embedding interface. Vectors come back L2 normalized."""

    model_name: str

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts, returning a (n, dim) float32 matrix with unit rows."""
        ...


class FastEmbedEmbedder:
    """ONNX based embeddings via fastembed. Model loads lazily on first use."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: object | None = None

    def _ensure_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts with the local ONNX model and normalize rows."""
        model = self._ensure_model()
        vectors = np.array(list(model.embed(texts)), dtype="float32")
        return _normalize(vectors)


class HashEmbedder:
    """Deterministic pseudo embeddings from sha256 seeds, dim 64. Tests only."""

    model_name = "hash-64"

    def embed(self, texts: list[str]) -> np.ndarray:
        """Map each text deterministically to a unit vector."""
        out = np.zeros((len(texts), 64), dtype="float32")
        for i, text in enumerate(texts):
            seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
            rng = np.random.default_rng(seed)
            out[i] = rng.standard_normal(64)
        return _normalize(out)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2 normalize rows, guarding zero vectors."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return (vectors / norms).astype("float32")


def build_embedder(provider: str, model_name: str) -> Embedder:
    """Build the configured embedder; hash is the deterministic test path."""
    if provider == "fastembed":
        return FastEmbedEmbedder(model_name)
    if provider == "hash":
        return HashEmbedder()
    raise ValueError(f"unknown embeddings provider '{provider}'")
