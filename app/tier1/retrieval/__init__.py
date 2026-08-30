"""Retrieval subsystem package for ControlPlane Tier 1."""

from .base import BaseEvidenceRepository
from .chunking import DocumentChunk, DocumentChunker
from .embedding import (
    DeterministicMockEmbeddingProvider,
    EmbeddingProvider,
    RealEmbeddingProvider,
)
from .hybrid_repo import HybridEvidenceRepository
from .lexical_repo import LexicalEvidenceRepository
from .semantic_repo import SemanticEvidenceRepository

__all__ = [
    "BaseEvidenceRepository",
    "DocumentChunk",
    "DocumentChunker",
    "EmbeddingProvider",
    "RealEmbeddingProvider",
    "DeterministicMockEmbeddingProvider",
    "LexicalEvidenceRepository",
    "SemanticEvidenceRepository",
    "HybridEvidenceRepository",
]
