"""Isolated evidence repository for evaluation benchmark cases."""

from typing import Any, Dict, List
from uuid import uuid4
from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet
from app.tier1.evidence_store import EvidenceRepository


class EvaluationEvidenceRepository(EvidenceRepository):
    """In-memory evidence repository explicitly seeded with a test case's reference evidence."""

    def __init__(self, reference_evidence: List[Dict[str, Any]]):
        # Do not call super().__init__() to avoid seeding the default enterprise corpus
        self._corpus: List[EvidenceSnippet] = []
        for ev in reference_evidence:
            self._corpus.append(
                EvidenceSnippet(
                    evidence_id=uuid4(),
                    source_type="EVALUATION_FIXTURE",
                    source_id=ev.get("source_id", "test-doc"),
                    content_snippet=ev.get("content", ""),
                    quality=ClaimEvidenceQuality(
                        authority=ev.get("authority", "HIGH"),
                        freshness=1.0,
                        relevance=0.95,
                        completeness=0.95,
                        quality_score=0.95,
                    ),
                )
            )

    def retrieve(
        self,
        query: str,
        application_profile: Optional[str] = None,
        policy: Optional[str] = None,
        top_k: int = 3,
    ) -> List[EvidenceSnippet]:
        """Bypass retrieval and just return the isolated test case evidence."""
        return self._corpus
        
    def find_relevant_evidence(
        self, claim_text: str, application_profile: Optional[str] = None, policy: Optional[str] = None
    ) -> List[EvidenceSnippet]:
        """Bypass retrieval and just return the isolated test case evidence."""
        return self._corpus
