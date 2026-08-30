"""Gemini adapter implementing the NLIVerifier interface for Tier-1 verification."""

import logging
from typing import List, Optional
from app.domain.models import (
    AdjudicationTrigger,
    ClaimVerificationItem,
    EvidenceSnippet,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)
from app.tier1.nli_verifier import NLIVerifier
from app.tier1.semantic_verifier import GeminiSemanticVerifier

logger = logging.getLogger(__name__)


class GeminiNLIVerifier(NLIVerifier):
    """Adapter bridging GeminiSemanticVerifier to Tier 1 NLIVerifier."""

    def __init__(self, gemini_verifier: Optional[GeminiSemanticVerifier] = None):
        self.verifier = gemini_verifier or GeminiSemanticVerifier()

    def verify(self, claim: ClaimVerificationItem, evidence: List[EvidenceSnippet]) -> VerifierResponse:
        """Evaluate claim against evidence using Gemini LLM."""
        if not evidence:
            return VerifierResponse(
                label="INSUFFICIENT_EVIDENCE",
                nli_confidence=0.0,
                top2_scores=None,
                evidence_ids=[],
                verification_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                adjudication_trigger=AdjudicationTrigger.NONE,
                uncertainty_reason=UncertaintyReason.NONE,
            )

        evidence_ids = [e.evidence_id for e in evidence]
        evidence_snippets = [e.content_snippet for e in evidence]

        res = self.verifier.verify(claim.claim_text, evidence_snippets)

        return VerifierResponse(
            label=res.label,
            nli_confidence=res.confidence,
            top2_scores={res.label: res.confidence},
            evidence_ids=evidence_ids,
            verification_status=VerificationStatus.DIRECT_NLI,
            adjudication_trigger=AdjudicationTrigger.NONE,
            uncertainty_reason=UncertaintyReason.NONE,
        )
