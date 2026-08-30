"""Unified Evidence Repository interface and factory for ControlPlane Tier 1."""

from typing import Any, Dict, List, Optional
from app.domain.models import EvidenceSnippet
from app.tier1.retrieval.base import BaseEvidenceRepository
from app.tier1.retrieval.lexical_repo import LexicalEvidenceRepository
from app.tier1.retrieval.semantic_repo import SemanticEvidenceRepository
from app.tier1.retrieval.hybrid_repo import HybridEvidenceRepository


class EvidenceRepository(LexicalEvidenceRepository):
    """Default backward-compatible in-memory evidence repository with multi-mode retrieval support."""

    def __init__(
        self,
        mode: str = "LEXICAL",
        semantic_repo: Optional[SemanticEvidenceRepository] = None,
        hybrid_repo: Optional[HybridEvidenceRepository] = None,
        snippets: Optional[List[EvidenceSnippet]] = None,
    ):
        super().__init__(snippets=snippets)
        self.mode = mode.upper()
        self._semantic_repo = semantic_repo
        self._hybrid_repo = hybrid_repo

    def retrieve(
        self,
        query: str,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        top_k: int = 3,
    ) -> List[EvidenceSnippet]:
        """Delegate retrieval to active mode implementation."""
        mode = getattr(self, "mode", "LEXICAL")
        sem_repo = getattr(self, "_semantic_repo", None)
        hyb_repo = getattr(self, "_hybrid_repo", None)

        if mode == "SEMANTIC" and sem_repo is not None:
            return sem_repo.retrieve(
                query=query,
                application_profile=application_profile,
                policy=policy,
                top_k=top_k,
            )
        elif mode == "HYBRID" and hyb_repo is not None:
            return hyb_repo.retrieve(
                query=query,
                application_profile=application_profile,
                policy=policy,
                top_k=top_k,
            )
        # Default fallback: Lexical
        return super().retrieve(
            query=query,
            application_profile=application_profile,
            policy=policy,
            top_k=top_k,
        )
