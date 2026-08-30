"""Semantic evidence repository using FAISS CPU and sentence embeddings."""

import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import numpy as np
import faiss

from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet
from .base import BaseEvidenceRepository
from .chunking import DocumentChunk
from .embedding import EmbeddingProvider, RealEmbeddingProvider

logger = logging.getLogger(__name__)


class SemanticEvidenceRepository(BaseEvidenceRepository):
    """FAISS-backed vector search repository with metadata filtering and caching."""

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        index_path: Optional[str] = None,
        metadata_path: Optional[str] = None,
        chunks: Optional[List[DocumentChunk]] = None,
        cache_size: int = 512,
    ):
        self.embedding_provider = embedding_provider or RealEmbeddingProvider()
        self.cache_size = cache_size
        self._index: Optional[faiss.IndexFlatIP] = None
        self._chunks: List[DocumentChunk] = []
        self._chunk_map: Dict[int, DocumentChunk] = {}
        
        # In-memory query embedding and result cache
        self._query_cache: Dict[str, Tuple[List[EvidenceSnippet], float]] = {}
        self._query_cache_order: List[str] = []

        # Load from file or initialize
        if index_path and metadata_path and os.path.exists(index_path) and os.path.exists(metadata_path):
            self.load_index(index_path, metadata_path)
        elif chunks:
            self.index_chunks(chunks)
        else:
            self._seed_default_semantic_corpus()

    def _seed_default_semantic_corpus(self):
        """Seed baseline enterprise chunks if no custom index is provided."""
        default_chunks = [
            DocumentChunk(
                chunk_id="chunk-ret-30d",
                source_id="doc-returns-2026",
                document_id="doc-returns",
                document_version="v2.1",
                timestamp="2026-01-01T00:00:00Z",
                authority="HIGH",
                application_profile="CUSTOMER_SUPPORT",
                policy_scope="RETAIL",
                content="Standard retail return policy permits full refunds within 30 days of product delivery in original packaging.",
            ),
            DocumentChunk(
                chunk_id="chunk-waiver-cap",
                source_id="doc-waivers-2026",
                document_id="doc-waivers",
                document_version="v1.4",
                timestamp="2026-01-01T00:00:00Z",
                authority="HIGH",
                application_profile="DECISION_SUPPORT",
                policy_scope="FINANCIAL",
                content="Customer courtesy fee waivers are strictly capped at $200 per account and require formal supervisor signoff. Unlimited or $1000 waivers are strictly prohibited.",
            ),
            DocumentChunk(
                chunk_id="chunk-fairness-01",
                source_id="doc-eeo-policy",
                document_id="doc-eeo",
                document_version="v3.0",
                timestamp="2026-01-01T00:00:00Z",
                authority="HIGH",
                application_profile="INTERNAL_KNOWLEDGE",
                policy_scope="HR",
                content="Company hiring and technical performance evaluations must be based solely on objective skills without bias regarding age, gender, or background.",
            ),
            DocumentChunk(
                chunk_id="chunk-roam-45c",
                source_id="doc-roaming-plan-b",
                document_id="doc-roaming",
                document_version="v1.0",
                timestamp="2026-01-01T00:00:00Z",
                authority="HIGH",
                application_profile="CUSTOMER_SUPPORT",
                policy_scope="TELECOM",
                content="Plan B provides complimentary international roaming across 45 designated countries in North America and Europe, but roaming in other territories is excluded and requires an add-on pass.",
            ),
        ]
        self.index_chunks(default_chunks)

    def index_chunks(self, chunks: List[DocumentChunk]):
        """Index a collection of DocumentChunks into FAISS."""
        self._chunks = list(chunks)
        self._chunk_map = {i: chunk for i, chunk in enumerate(self._chunks)}
        self._query_cache.clear()
        self._query_cache_order.clear()

        if not chunks:
            self._index = faiss.IndexFlatIP(self.embedding_provider.dimension)
            return

        texts = [c.content for c in self._chunks]
        embeddings = self.embedding_provider.embed_batch(texts)
        
        # Ensure L2 normalization for exact cosine similarity (Inner Product)
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embeddings)

    def save_index(self, index_path: str, metadata_path: str, manifest_path: Optional[str] = None):
        """Save FAISS index and metadata to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(index_path)), exist_ok=True)
        faiss.write_index(self._index, index_path)

        metadata = [chunk.model_dump() for chunk in self._chunks]
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        if manifest_path:
            manifest = {
                "corpus_version": "v1.0-enterprise",
                "embedding_model": self.embedding_provider.model_name,
                "dimension": self.embedding_provider.dimension,
                "document_count": len(set(c.document_id for c in self._chunks)),
                "chunk_count": len(self._chunks),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "index_version": "1.0.0",
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

    def load_index(self, index_path: str, metadata_path: str):
        """Load FAISS index and metadata from disk."""
        self._index = faiss.read_index(index_path)
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        self._chunks = [DocumentChunk(**item) for item in metadata]
        self._chunk_map = {i: chunk for i, chunk in enumerate(self._chunks)}
        self._query_cache.clear()
        self._query_cache_order.clear()

    def _matches_filters(
        self,
        chunk: DocumentChunk,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        min_authority: Optional[str] = None,
    ) -> bool:
        """Filter chunks based on enterprise metadata BEFORE top-k selection."""
        # 1. Application Profile isolation
        if application_profile and application_profile not in ["ALL", "*"]:
            if chunk.application_profile and chunk.application_profile not in [application_profile, "ALL", "*"]:
                return False

        # 2. Policy scope isolation
        if policy and policy not in ["ALL", "*"]:
            if chunk.policy_scope and chunk.policy_scope not in [policy, "ALL", "*"]:
                return False

        # 3. Authority requirement
        if min_authority == "HIGH" and chunk.authority != "HIGH":
            return False

        return True

    def retrieve(
        self,
        query: str,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        top_k: int = 3,
    ) -> List[EvidenceSnippet]:
        """Retrieve top-k evidence snippets using cosine similarity and pre-filtering."""
        if not query or not self._chunks or self._index is None or self._index.ntotal == 0:
            return []

        cache_key = f"{query}__app={application_profile}__pol={policy}__k={top_k}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key][0]

        # 1. Embed query
        query_vec = self.embedding_provider.embed_text(query).reshape(1, -1)
        faiss.normalize_L2(query_vec)

        # 2. Search broader candidate pool to allow metadata filtering
        search_k = min(self._index.ntotal, max(top_k * 5, 20))
        sims, indices = self._index.search(query_vec, search_k)

        # 3. Filter candidates and construct EvidenceSnippets
        results: List[EvidenceSnippet] = []
        for sim, idx in zip(sims[0], indices[0]):
            if idx == -1 or idx not in self._chunk_map:
                continue
            chunk = self._chunk_map[idx]

            # Pre-filter by metadata
            if not self._matches_filters(chunk, application_profile, policy):
                continue

            similarity_score = float(sim)
            # Bound cosine similarity in [0.0, 1.0] for quality score calculations
            bounded_sim = max(0.0, min(1.0, (similarity_score + 1.0) / 2.0 if similarity_score < 0 else similarity_score))

            # Quality heuristic: combine authority + freshness + relevance
            authority_weight = 1.0 if chunk.authority == "HIGH" else (0.8 if chunk.authority == "MEDIUM" else 0.5)
            quality_score = 0.5 * bounded_sim + 0.3 * authority_weight + 0.2 * 1.0

            snippet = EvidenceSnippet(
                evidence_id=uuid4(),
                source_type=chunk.policy_scope or "POLICY_DOC",
                source_id=chunk.source_id,
                document_version=chunk.document_version,
                chunk_id=chunk.chunk_id,
                content_snippet=chunk.content,
                quality=ClaimEvidenceQuality(
                    authority=chunk.authority,
                    freshness=1.0,
                    relevance=float(bounded_sim),
                    completeness=0.90,
                    quality_score=float(quality_score),
                ),
            )
            results.append(snippet)
            if len(results) >= top_k:
                break

        # Cache management (LRU)
        if len(self._query_cache) >= self.cache_size:
            oldest = self._query_cache_order.pop(0)
            self._query_cache.pop(oldest, None)
        self._query_cache[cache_key] = (results, time.perf_counter())
        self._query_cache_order.append(cache_key)

        return results
