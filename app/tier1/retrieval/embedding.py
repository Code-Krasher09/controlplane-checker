"""Embedding provider abstractions for semantic retrieval."""

import abc
import hashlib
import numpy as np
from typing import List, Optional


class EmbeddingProvider(abc.ABC):
    """Abstract interface for generating text embeddings."""

    @abc.abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string into a 1D float32 numpy array."""
        pass

    @abc.abstractmethod
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed multiple text strings into a 2D float32 numpy array (N, dim)."""
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimensionality."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Name of the embedding model."""
        pass


class RealEmbeddingProvider(EmbeddingProvider):
    """Real local SentenceTransformer embedding provider (default: all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dimension = 384

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            if hasattr(self._model, "get_embedding_dimension"):
                self._dimension = self._model.get_embedding_dimension()
            elif hasattr(self._model, "get_sentence_embedding_dimension"):
                self._dimension = self._model.get_sentence_embedding_dimension()
            else:
                self._dimension = 384
        return self._model

    def embed_text(self, text: str) -> np.ndarray:
        model = self._get_model()
        vec = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return vec.astype(np.float32)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        model = self._get_model()
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vecs.astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name


class DeterministicMockEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based embedding provider for ultra-fast unit testing."""

    def __init__(self, dimension: int = 384, model_name: str = "mock-hash-embedding-384"):
        self._dimension = dimension
        self._model_name = model_name

    def _hash_to_vec(self, text: str) -> np.ndarray:
        words = text.lower().split()
        vec = np.zeros(self._dimension, dtype=np.float32)
        for i, word in enumerate(words):
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimension
            sign = 1.0 if ((h >> 4) % 2 == 0) else -1.0
            vec[idx] += sign * (1.0 / (i + 1.0))
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec /= norm
        else:
            vec[0] = 1.0
        return vec.astype(np.float32)

    def embed_text(self, text: str) -> np.ndarray:
        return self._hash_to_vec(text)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)
        return np.vstack([self._hash_to_vec(t) for t in texts]).astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name
