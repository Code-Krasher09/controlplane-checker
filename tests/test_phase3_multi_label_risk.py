"""Phase 3C — Multi-Label Risk Model and Overlapping Action Resolution Tests."""

from uuid import uuid4
import pytest
from app.domain.models import (
    ActionType,
    ClaimVerificationItem,
    PolicyEventItem,
    RiskAssessmentResult,
    RiskLevel,
    SeverityLevel,
    VerificationStatus,
)
from app.persistence.models import PolicyConfig, PolicyVersion
from app.risk.multi_label import MultiLabelRiskAggregator


def test_8_pii_plus_hallucination_precedence_block():
    """Test 8: Simultaneous PII (Critical) and Hallucination (High) resolves to BLOCK."""
    aggregator = MultiLabelRiskAggregator()
    pii_event = PolicyEventItem(
        event_type="PII",
        detector="PIIDetector",
        severity=SeverityLevel.CRITICAL,
        matched_text="123-45-6789",
    )
    contradicted_claim = ClaimVerificationItem(
        claim_text="Unlimited $1,000 cash waivers are provided.",
        final_label="CONTRADICTED",
        severity=SeverityLevel.HIGH,
    )
    base_risk = RiskAssessmentResult(
        risk_level=RiskLevel.CRITICAL,
        severity=SeverityLevel.CRITICAL,
        verification_required=False,
    )
    policy = PolicyConfig(block_on_pii=True, max_repair_attempts=2)

    risk_types, highest_sev, candidate_actions, resolved_action, reason = aggregator.aggregate_risks(
        policy_events=[pii_event],
        claims=[contradicted_claim],
        base_risk_result=base_risk,
        policy_config=policy,
        current_repair_attempt=0,
    )

    assert "PII" in risk_types
    assert "HALLUCINATION" in risk_types
    assert highest_sev == SeverityLevel.CRITICAL
    assert ActionType.BLOCK in candidate_actions
    assert ActionType.REPAIR in candidate_actions
    assert resolved_action == ActionType.BLOCK
    assert "BLOCK" in reason


def test_9_bias_plus_hallucination_precedence_repair():
    """Test 9: Simultaneous Bias (Warn) and Hallucination (Repair) resolves to REPAIR."""
    aggregator = MultiLabelRiskAggregator()
    bias_event = PolicyEventItem(
        event_type="BIAS",
        detector="HeuristicBiasDetector",
        severity=SeverityLevel.MEDIUM,
        matched_text="older workers",
    )
    contradicted_claim = ClaimVerificationItem(
        claim_text="Unlimited $1,000 cash waivers are provided.",
        final_label="CONTRADICTED",
        severity=SeverityLevel.HIGH,
    )
    base_risk = RiskAssessmentResult(
        risk_level=RiskLevel.HIGH,
        severity=SeverityLevel.HIGH,
        verification_required=True,
    )
    policy = PolicyConfig(max_repair_attempts=2)
    version = PolicyVersion(action_rules={"bias_action": "WARN"})

    risk_types, highest_sev, candidate_actions, resolved_action, reason = aggregator.aggregate_risks(
        policy_events=[bias_event],
        claims=[contradicted_claim],
        base_risk_result=base_risk,
        policy_config=policy,
        policy_version=version,
        current_repair_attempt=0,
    )

    assert "BIAS" in risk_types
    assert "HALLUCINATION" in risk_types
    assert ActionType.WARN in candidate_actions
    assert ActionType.REPAIR in candidate_actions
    assert resolved_action == ActionType.REPAIR


def test_10_policy_violation_plus_pii():
    """Test 10: Simultaneous Policy Violation and PII resolves to BLOCK."""
    aggregator = MultiLabelRiskAggregator()
    pii_event = PolicyEventItem(
        event_type="PII",
        detector="PIIDetector",
        severity=SeverityLevel.CRITICAL,
        matched_text="user@domain.com",
    )
    policy_event = PolicyEventItem(
        event_type="POLICY_VIOLATION",
        detector="ToxicityDetector",
        severity=SeverityLevel.HIGH,
        matched_text="prohibited command",
    )
    base_risk = RiskAssessmentResult(
        risk_level=RiskLevel.CRITICAL,
        severity=SeverityLevel.CRITICAL,
        verification_required=False,
    )
    policy = PolicyConfig(block_on_pii=True, block_on_policy_violation=True)

    risk_types, highest_sev, candidate_actions, resolved_action, reason = aggregator.aggregate_risks(
        policy_events=[pii_event, policy_event],
        claims=[],
        base_risk_result=base_risk,
        policy_config=policy,
    )

    assert set(risk_types) == {"PII", "POLICY_VIOLATION"}
    assert resolved_action == ActionType.BLOCK


def test_11_independent_events_preserved():
    """Test 11: Events are stored individually without collapsing."""
    aggregator = MultiLabelRiskAggregator()
    events = [
        PolicyEventItem(event_type="PII", detector="DetectorA", severity=SeverityLevel.HIGH),
        PolicyEventItem(event_type="SECRET", detector="DetectorB", severity=SeverityLevel.CRITICAL),
        PolicyEventItem(event_type="BIAS", detector="DetectorC", severity=SeverityLevel.MEDIUM),
    ]
    base_risk = RiskAssessmentResult(risk_level=RiskLevel.HIGH, severity=SeverityLevel.HIGH, verification_required=False)
    policy = PolicyConfig(block_on_pii=True)

    risk_types, highest_sev, candidate_actions, resolved_action, _ = aggregator.aggregate_risks(
        policy_events=events,
        claims=[],
        base_risk_result=base_risk,
        policy_config=policy,
    )

    assert len(risk_types) == 3
    assert "PII" in risk_types and "SECRET" in risk_types and "BIAS" in risk_types
    assert highest_sev == SeverityLevel.CRITICAL


def test_12_canonical_action_precedence_order():
    """Test 12: Precedence strictly obeys BLOCK > ESCALATE > REPAIR > WARN > ABSTAIN > ALLOW."""
    aggregator = MultiLabelRiskAggregator()
    policy = PolicyConfig(max_repair_attempts=2)

    # 1. BLOCK vs ESCALATE vs REPAIR vs WARN
    all_events = [
        PolicyEventItem(event_type="PII", detector="PII", severity=SeverityLevel.CRITICAL),  # BLOCK
        PolicyEventItem(event_type="POLICY_VIOLATION", detector="Policy", severity=SeverityLevel.HIGH),  # ESCALATE
        PolicyEventItem(event_type="BIAS", detector="Bias", severity=SeverityLevel.MEDIUM),  # WARN
    ]
    claims = [
        ClaimVerificationItem(claim_text="text", final_label="CONTRADICTED", severity=SeverityLevel.HIGH)  # REPAIR
    ]
    base_risk = RiskAssessmentResult(risk_level=RiskLevel.HIGH, severity=SeverityLevel.HIGH, verification_required=True)

    _, _, candidates, resolved, _ = aggregator.aggregate_risks(
        policy_events=all_events,
        claims=claims,
        base_risk_result=base_risk,
        policy_config=policy,
    )

    assert resolved == ActionType.BLOCK
