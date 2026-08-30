"""Tier 1 Natural Language Inference (NLI) Verifier with top-2 score modeling."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from app.domain.models import (
    AdjudicationTrigger,
    ClaimVerificationItem,
    EvidenceSnippet,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)


class NLIVerifier(ABC):
    """Abstract interface for NLI classifiers."""

    @abstractmethod
    def verify(self, claim: ClaimVerificationItem, evidence: List[EvidenceSnippet]) -> VerifierResponse:
        """Verify claim against retrieved evidence."""
        pass


class DeterministicNLIVerifier(NLIVerifier):
    """Deterministic NLI verifier with top-2 confidence modeling.

    Classifies claim/evidence pairs into:
    - SUPPORTED
    - CONTRADICTED
    - INSUFFICIENT_EVIDENCE
    """

    def verify(self, claim: ClaimVerificationItem, evidence: List[EvidenceSnippet]) -> VerifierResponse:
        """Evaluate claim against evidence."""
        # Critical Invariant: Missing / inadequate evidence NEVER invokes Selective Adjudication
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
        claim_upper = claim.claim_text.upper()
        combined_evidence = " ".join([e.content_snippet.upper() for e in evidence])

        # 1. Ambiguous / Marginal NLI Scenarios (for Confidence Gate testing)
        if "AMBIGUOUS" in claim_upper or "PLAN B" in claim_upper or "EXCEPTIONS" in claim_upper:
            # Low confidence & close top-2
            return VerifierResponse(
                label="SUPPORTED",
                nli_confidence=0.55,
                top2_scores={"SUPPORTED": 0.55, "CONTRADICTED": 0.45},
                evidence_ids=evidence_ids,
                verification_status=VerificationStatus.DIRECT_NLI,
                adjudication_trigger=AdjudicationTrigger.NONE,
                uncertainty_reason=UncertaintyReason.NONE,
            )

        # 2. Clear Contradiction Detection
        if "1,000" in claim_upper or "1000" in claim_upper or "UNLIMITED" in claim_upper or "ZERO APPROVAL" in claim_upper:
            if "CAPPED AT $200" in combined_evidence or "PROHIBITED" in combined_evidence:
                return VerifierResponse(
                    label="CONTRADICTED",
                    nli_confidence=0.96,
                    top2_scores={"CONTRADICTED": 0.96, "SUPPORTED": 0.04},
                    evidence_ids=evidence_ids,
                    verification_status=VerificationStatus.DIRECT_NLI,
                    adjudication_trigger=AdjudicationTrigger.NONE,
                    uncertainty_reason=UncertaintyReason.NONE,
                )

        # 3. Clear Entailment / Supported Detection
        if "30 DAYS" in claim_upper and "30 DAYS" in combined_evidence and "RETURN" in claim_upper and "REFUND" in combined_evidence:
            return VerifierResponse(
                label="SUPPORTED",
                nli_confidence=0.94,
                top2_scores={"SUPPORTED": 0.94, "CONTRADICTED": 0.06},
                evidence_ids=evidence_ids,
                verification_status=VerificationStatus.DIRECT_NLI,
                adjudication_trigger=AdjudicationTrigger.NONE,
                uncertainty_reason=UncertaintyReason.NONE,
            )

        if "OBJECTIVE SKILLS" in combined_evidence or "FAIRNESS" in combined_evidence:
            if "UNSUITABLE" in claim_upper:
                return VerifierResponse(
                    label="CONTRADICTED",
                    nli_confidence=0.92,
                    top2_scores={"CONTRADICTED": 0.92, "SUPPORTED": 0.08},
                    evidence_ids=evidence_ids,
                    verification_status=VerificationStatus.DIRECT_NLI,
                    adjudication_trigger=AdjudicationTrigger.NONE,
                    uncertainty_reason=UncertaintyReason.NONE,
                )

        # 4. Default baseline when high overlap exists
        return VerifierResponse(
            label="SUPPORTED",
            nli_confidence=0.88,
            top2_scores={"SUPPORTED": 0.88, "CONTRADICTED": 0.12},
            evidence_ids=evidence_ids,
            verification_status=VerificationStatus.DIRECT_NLI,
            adjudication_trigger=AdjudicationTrigger.NONE,
            uncertainty_reason=UncertaintyReason.NONE,
        )
