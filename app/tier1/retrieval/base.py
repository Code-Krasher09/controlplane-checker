"""Base evidence repository interface for all retrieval implementations."""

import abc
from typing import Any, Dict, List, Optional
from app.domain.models import EvidenceSnippet


class BaseEvidenceRepository(abc.ABC):
    """Abstract interface for evidence retrieval in ControlPlane Tier 1."""

    @abc.abstractmethod
    def retrieve(
        self,
        query: str,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        top_k: int = 3,
    ) -> List[EvidenceSnippet]:
        """Retrieve relevant evidence snippets for a query under optional scope filters."""
        pass

    def find_relevant_evidence(
        self,
        claim_text: str,
        top_k: int = 3,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
    ) -> List[EvidenceSnippet]:
        """Compatibility method for legacy Tier 1 caller interface."""
        return self.retrieve(
            query=claim_text,
            application_profile=application_profile,
            policy=policy,
            top_k=top_k,
        )
