"""Contract schema and invariant validation tests."""

from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.domain.models import (
    ActionType,
    AdjudicationRequest,
    AdjudicationResponse,
    AdjudicationTrigger,
    ClaimVerificationItem,
    PreflightRequest,
    PreflightResponse,
    RiskAssessmentResult,
    RiskLevel,
    RiskRequest,
    RiskResponse,
    SeverityLevel,
    UncertaintyReason,
    VerificationStatus,
    VerifierRequest,
    VerifierResponse,
)


def test_action_types_vocabulary():
    """Verify exact canonical action vocabulary."""
    expected_actions = {"ALLOW", "WARN", "ABSTAIN", "REPAIR", "BLOCK", "ESCALATE"}
    actual_actions = {a.value for a in ActionType}
    assert actual_actions == expected_actions


def test_verification_status_vocabulary():
    """Verify controlled verification status values."""
    expected_statuses = {"DIRECT_NLI", "ADJUDICATED", "ADJUDICATION_INCONCLUSIVE", "INSUFFICIENT_EVIDENCE"}
    actual_statuses = {s.value for s in VerificationStatus}
    assert actual_statuses == expected_statuses


def test_adjudication_triggers_vocabulary():
    """Verify controlled adjudication triggers."""
    expected_triggers = {
        "NONE",
        "NLI_LOW_CONFIDENCE",
        "NLI_CLOSE_TOP2",
        "NLI_EVIDENCE_LABEL_CONFLICT",
        "HIGH_SEVERITY_MARGINAL_NLI",
    }
    actual_triggers = {t.value for t in AdjudicationTrigger}
    assert actual_triggers == expected_triggers


def test_uncertainty_reasons_vocabulary():
    """Verify controlled uncertainty reasons."""
    expected_reasons = {
        "NONE",
        "NLI_LOW_CONFIDENCE",
        "NLI_CLOSE_TOP2",
        "NLI_EVIDENCE_LABEL_CONFLICT",
        "HIGH_SEVERITY_MARGINAL_NLI",
        "JUDGE_LOW_CONFIDENCE",
        "ADJUDICATION_BUDGET_EXHAUSTED",
    }
    actual_reasons = {r.value for r in UncertaintyReason}
    assert actual_reasons == expected_reasons


def test_adjudication_inconclusive_contract():
    """Verify AdjudicationResponse supports inconclusive judge with null label."""
    resp = AdjudicationResponse(
        verification_status=VerificationStatus.ADJUDICATION_INCONCLUSIVE,
        final_label=None,
        adjudicator_confidence=0.44,
        uncertainty_reason=UncertaintyReason.JUDGE_LOW_CONFIDENCE,
    )
    assert resp.verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE
    assert resp.final_label is None
    assert resp.uncertainty_reason == UncertaintyReason.JUDGE_LOW_CONFIDENCE


def test_claim_verification_item_adjudication_budget_exhausted():
    """Verify ClaimVerificationItem supports budget exhausted state without silent skip."""
    item = ClaimVerificationItem(
        claim_text="Example claim",
        verification_status=VerificationStatus.DIRECT_NLI,
        final_label=None,
        adjudication_trigger=AdjudicationTrigger.NLI_LOW_CONFIDENCE,
        uncertainty_reason=UncertaintyReason.ADJUDICATION_BUDGET_EXHAUSTED,
    )
    assert item.verification_status == VerificationStatus.DIRECT_NLI
    assert item.adjudication_trigger == AdjudicationTrigger.NLI_LOW_CONFIDENCE
    assert item.uncertainty_reason == UncertaintyReason.ADJUDICATION_BUDGET_EXHAUSTED
