"""High-Severity Selective Gemini Hybrid Verifier for Tier-1 Semantic Verification."""

import logging
import os
import time
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.domain.models import (
    AdjudicationTrigger,
    ClaimVerificationItem,
    EvidenceSnippet,
    SeverityLevel,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)
from app.tier1.nli_verifier import DeterministicNLIVerifier, NLIVerifier
from app.tier1.semantic_verifier import GeminiSemanticVerifier, SemanticVerificationResult

logger = logging.getLogger(__name__)


class HighSeverityHybridVerifier(NLIVerifier):
    """Production Tier-1 Two-Stage Hybrid Verifier.
    
    Routing Rules:
    - Low/Medium Severity: Local semantic verifier (Fast path, ~10ms).
    - High/Critical Severity or genuine Ambiguity: Gemini LLM-as-a-Judge (High-rigor path).
    - Inadequate/Missing Evidence: Strictly returns INSUFFICIENT_EVIDENCE without invoking Gemini.
    - Graceful Fallback: On API failure/timeout, preserves failure state for conservative Action Engine handling.
    """

    def __init__(
        self,
        local_verifier: Optional[NLIVerifier] = None,
        gemini_verifier: Optional[GeminiSemanticVerifier] = None,
        high_severity_threshold: float = 0.85,
        enable_gemini: bool = True,
    ):
        self.local_verifier = local_verifier or DeterministicNLIVerifier()
        self.enable_gemini = enable_gemini
        self.high_severity_threshold = high_severity_threshold
        self._gemini_verifier = gemini_verifier
        self.model_name = "hybrid-high-severity-gemini-v1"

        if self.enable_gemini and self._gemini_verifier is None:
            settings = get_settings()
            api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
            if api_key:
                try:
                    self._gemini_verifier = GeminiSemanticVerifier(
                        api_key=api_key,
                        model_name=settings.gemini_model,
                    )
                except Exception as e:
                    logger.warning(f"Could not initialize Gemini in HighSeverityHybridVerifier: {e}")

    def verify(
        self,
        claim: ClaimVerificationItem,
        evidence: List[EvidenceSnippet],
        application_profile: Optional[str] = None,
        policy_scope: Optional[str] = None,
    ) -> VerifierResponse:
        """Verify claim against evidence adhering to High-Severity Selective Gemini routing."""
        # -------------------------------------------------------------
        # INVARIANT 1: Evidence Insufficiency Gate
        # Inadequate evidence MUST NEVER invoke Gemini.
        # -------------------------------------------------------------
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
        is_high_severity = (
            claim.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL)
            or (application_profile and application_profile.upper() in ("DECISION_SUPPORT", "FINANCIAL", "COMPLIANCE"))
        )

        # -------------------------------------------------------------
        # HIGH-SEVERITY PATH -> GEMINI SEMANTIC VERIFIER
        # -------------------------------------------------------------
        if is_high_severity and self._gemini_verifier is not None:
            try:
                snippets = [e.content_snippet for e in evidence]
                res: SemanticVerificationResult = self._gemini_verifier.verify(
                    claim_text=claim.claim_text,
                    evidence_snippets=snippets,
                    policy_context=policy_scope,
                )

                # Check if Gemini returned an internal verifier error
                if res.confidence == 0.0 and "Verifier error" in res.reason:
                    logger.warning(f"Gemini verification error, falling back conservatively: {res.reason}")
                    return VerifierResponse(
                        label="INSUFFICIENT_EVIDENCE",
                        nli_confidence=0.0,
                        top2_scores=None,
                        evidence_ids=evidence_ids,
                        verification_status=VerificationStatus.ADJUDICATION_INCONCLUSIVE,
                        adjudication_trigger=AdjudicationTrigger.HIGH_SEVERITY_MARGINAL_NLI,
                        uncertainty_reason=UncertaintyReason.JUDGE_LOW_CONFIDENCE,
                    )

                return VerifierResponse(
                    label=res.label,
                    nli_confidence=res.confidence,
                    top2_scores={res.label: res.confidence},
                    evidence_ids=evidence_ids,
                    verification_status=VerificationStatus.DIRECT_NLI,
                    adjudication_trigger=AdjudicationTrigger.NONE,
                    uncertainty_reason=UncertaintyReason.NONE,
                )
            except Exception as e:
                logger.error(f"Gemini invocation threw exception: {e}")
                return VerifierResponse(
                    label="INSUFFICIENT_EVIDENCE",
                    nli_confidence=0.0,
                    top2_scores=None,
                    evidence_ids=evidence_ids,
                    verification_status=VerificationStatus.ADJUDICATION_INCONCLUSIVE,
                    adjudication_trigger=AdjudicationTrigger.HIGH_SEVERITY_MARGINAL_NLI,
                    uncertainty_reason=UncertaintyReason.JUDGE_LOW_CONFIDENCE,
                )

        # -------------------------------------------------------------
        # LOW / MEDIUM RISK PATH -> LOCAL SEMANTIC VERIFIER
        # -------------------------------------------------------------
        local_res = self.local_verifier.verify(claim, evidence)

        # Ambiguity check on local path
        if local_res.label != "INSUFFICIENT_EVIDENCE":
            if local_res.nli_confidence is not None and local_res.nli_confidence < 0.75:
                local_res.adjudication_trigger = AdjudicationTrigger.NLI_LOW_CONFIDENCE
            elif local_res.top2_scores and len(local_res.top2_scores) >= 2:
                sorted_scores = sorted(local_res.top2_scores.values(), reverse=True)
                if (sorted_scores[0] - sorted_scores[1]) < 0.15:
                    local_res.adjudication_trigger = AdjudicationTrigger.NLI_CLOSE_TOP2

        return local_res
