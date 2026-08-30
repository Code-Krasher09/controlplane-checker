"""Hybrid evidence repository combining semantic similarity and lexical overlap."""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4
from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet
from .base import BaseEvidenceRepository
from .chunking import DocumentChunk
from .embedding import EmbeddingProvider
from .lexical_repo import LexicalEvidenceRepository
from .semantic_repo import SemanticEvidenceRepository


class HybridEvidenceRepository(BaseEvidenceRepository):
    """Combines semantic vector similarity and lexical stem matching with transparent convex scoring."""

    def __init__(
        self,
        semantic_repo: Optional[SemanticEvidenceRepository] = None,
        lexical_repo: Optional[LexicalEvidenceRepository] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        chunks: Optional[List[DocumentChunk]] = None,
        alpha: float = 0.5,
    ):
        self.alpha = alpha  # Weight on semantic score, (1 - alpha) on lexical score
        self.semantic_repo = semantic_repo or SemanticEvidenceRepository(
            embedding_provider=embedding_provider,
            chunks=chunks,
        )
        self.lexical_repo = lexical_repo or LexicalEvidenceRepository()

    def _extract_stems(self, text: str) -> Set[str]:
        words = re.findall(r"\b[a-z0-9]{3,}\b", text.lower().replace("$", " ").replace(",", ""))
        stems = set()
        for w in words:
            stems.add(w)
            if w.endswith("s") and len(w) > 3:
                stems.add(w[:-1])
            if w.endswith("ed") and len(w) > 4:
                stems.add(w[:-2])
            if w.endswith("ing") and len(w) > 5:
                stems.add(w[:-3])
        return stems

    def _calculate_lexical_score(self, query_stems: Set[str], snippet_text: str) -> float:
        if not query_stems:
            return 0.0
        snippet_stems = self._extract_stems(snippet_text)
        overlap = query_stems.intersection(snippet_stems)
        return len(overlap) / max(1, len(query_stems))

    def retrieve(
        self,
        query: str,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        top_k: int = 3,
    ) -> List[EvidenceSnippet]:
        """Combine semantic and lexical candidates, compute normalized hybrid scores, return top-k."""
        if not query:
            return []

        # 1. Fetch wider candidate sets from both retrievers
        candidate_k = max(top_k * 4, 10)
        semantic_candidates = self.semantic_repo.retrieve(
            query=query,
            application_profile=application_profile,
            policy=policy,
            top_k=candidate_k,
        )
        lexical_candidates = self.lexical_repo.retrieve(
            query=query,
            application_profile=application_profile,
            policy=policy,
            top_k=candidate_k,
        )

        query_stems = self._extract_stems(query)

        # 2. Merge candidates by content/chunk_id
        candidate_map: Dict[str, Tuple[EvidenceSnippet, float, float]] = {}

        # Process semantic candidates
        for snip in semantic_candidates:
            key = snip.content_snippet.strip()
            sem_score = snip.quality.relevance if snip.quality else 0.5
            lex_score = self._calculate_lexical_score(query_stems, snip.content_snippet)
            candidate_map[key] = (snip, float(sem_score), float(lex_score))

        # Process lexical candidates
        for snip in lexical_candidates:
            key = snip.content_snippet.strip()
            if key not in candidate_map:
                lex_score = self._calculate_lexical_score(query_stems, snip.content_snippet)
                # Compute semantic score using semantic provider or default to 0.4
                sem_score = 0.4
                candidate_map[key] = (snip, float(sem_score), float(lex_score))
            else:
                # Update lexical score if not already set
                snip_existing, sem_s, _ = candidate_map[key]
                lex_score = self._calculate_lexical_score(query_stems, key)
                candidate_map[key] = (snip_existing, sem_s, float(lex_score))

        # 3. Compute normalized hybrid scores
        scored_results: List[Tuple[float, EvidenceSnippet]] = []
        for key, (snip, sem_s, lex_s) in candidate_map.items():
            # Normalized score calculation
            hybrid_score = self.alpha * sem_s + (1.0 - self.alpha) * lex_s

            # Update quality relevance
            updated_quality = snip.quality
            if updated_quality:
                updated_quality.relevance = float(hybrid_score)
                authority_w = 1.0 if updated_quality.authority == "HIGH" else 0.8
                updated_quality.quality_score = float(0.5 * hybrid_score + 0.3 * authority_w + 0.2 * updated_quality.freshness)

            scored_results.append((hybrid_score, snip))

        # 4. Sort and return top_k
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results[:top_k]]
