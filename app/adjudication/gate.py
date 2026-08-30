"""Post-NLI Confidence Gate for Selective Adjudication.

CRITICAL INVARIANTS:
1. Evidence insufficiency NEVER triggers adjudication.
2. Only valid triggers are evaluated:
   - NLI_LOW_CONFIDENCE
   - NLI_CLOSE_TOP2
   - NLI_EVIDENCE_LABEL_CONFLICT
   - HIGH_SEVERITY_MARGINAL_NLI
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.domain.models import (
    AdjudicationTrigger,
    ClaimVerificationItem,
    EvidenceSnippet,
    SeverityLevel,
    VerificationStatus,
)


class ConfidenceGateResult(BaseModel):
    """Result of Confidence Gate evaluation."""
    adjudication_required: bool
    trigger: AdjudicationTrigger
    reason: str


class ConfidenceGate:
    """Evaluates NLI output ambiguity to determine if Selective Adjudication is required."""

    DEFAULT_NLI_CONFIDENCE_THRESHOLD: float = 0.75
    DEFAULT_TOP2_MARGIN: float = 0.15
    DEFAULT_HIGH_SEVERITY_THRESHOLD: float = 0.85

    def evaluate(
        self,
        claim: ClaimVerificationItem,
        evidence: List[EvidenceSnippet],
        policy_thresholds: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceGateResult:
        """Evaluate claim verification ambiguity against policy thresholds."""
        # -------------------------------------------------------------
        # INVARIANT 1: Evidence insufficiency NEVER triggers adjudication
        # -------------------------------------------------------------
        if not evidence or claim.verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE:
            return ConfidenceGateResult(
                adjudication_required=False,
                trigger=AdjudicationTrigger.NONE,
                reason="INSUFFICIENT_EVIDENCE_EXCLUDED_FROM_ADJUDICATION",
            )

        thresholds = policy_thresholds or {}
        nli_conf_thresh = float(thresholds.get("nli_confidence_threshold", self.DEFAULT_NLI_CONFIDENCE_THRESHOLD))
        top2_margin_thresh = float(thresholds.get("adjudication_top2_margin", self.DEFAULT_TOP2_MARGIN))
        high_sev_thresh = float(thresholds.get("high_severity_nli_threshold", self.DEFAULT_HIGH_SEVERITY_THRESHOLD))

        confidence = claim.nli_confidence or 0.0

        # -------------------------------------------------------------
        # TRIGGER 1: NLI_CLOSE_TOP2
        # -------------------------------------------------------------
        if claim.top2_scores and len(claim.top2_scores) >= 2:
            sorted_scores = sorted(claim.top2_scores.values(), reverse=True)
            diff = sorted_scores[0] - sorted_scores[1]
            if diff < top2_margin_thresh:
                return ConfidenceGateResult(
                    adjudication_required=True,
                    trigger=AdjudicationTrigger.NLI_CLOSE_TOP2,
                    reason=f"Top-2 NLI score margin ({round(diff, 3)}) is within ambiguity window (< {top2_margin_thresh})",
                )

        # -------------------------------------------------------------
        # TRIGGER 2: NLI_LOW_CONFIDENCE
        # -------------------------------------------------------------
        if confidence < nli_conf_thresh:
            return ConfidenceGateResult(
                adjudication_required=True,
                trigger=AdjudicationTrigger.NLI_LOW_CONFIDENCE,
                reason=f"NLI confidence ({round(confidence, 3)}) is below policy threshold ({nli_conf_thresh})",
            )

        # -------------------------------------------------------------
        # TRIGGER 3: HIGH_SEVERITY_MARGINAL_NLI
        # -------------------------------------------------------------
        if claim.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) and confidence < high_sev_thresh:
            return ConfidenceGateResult(
                adjudication_required=True,
                trigger=AdjudicationTrigger.HIGH_SEVERITY_MARGINAL_NLI,
                reason=f"High-severity claim confidence ({round(confidence, 3)}) is below strict threshold ({high_sev_thresh})",
            )

        # -------------------------------------------------------------
        # Clean / Confident NLI
        # -------------------------------------------------------------
        return ConfidenceGateResult(
            adjudication_required=False,
            trigger=AdjudicationTrigger.NONE,
            reason="NLI_CONFIDENT_DIRECT_VERIFICATION",
        )
