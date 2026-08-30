"""Comprehensive unit and integration tests for Confidence Gate and Selective Adjudication."""

from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.adjudication.gate import ConfidenceGate
from app.adjudication.service import AdjudicationService
from app.domain.models import (
    ActionType,
    AdjudicationTrigger,
    ClaimEvidenceQuality,
    ClaimVerificationItem,
    EvidenceSnippet,
    GatewayInspectRequest,
    SeverityLevel,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)
from app.gateway.service import GatewayService
from app.persistence import (
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    PolicyConfig,
    PolicyVersion,
    RuntimeStateStore,
    seed_database_async,
)


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    """Seed standard database profiles."""
    await seed_database_async(async_session)


def create_sample_evidence() -> list[EvidenceSnippet]:
    """Helper to create valid evidence snippet."""
    return [
        EvidenceSnippet(
            evidence_id=uuid4(),
            source_type="TELECOM_DOC",
            source_id="doc-roaming-01",
            content_snippet="Plan B international roaming is supported across 45 countries in Europe.",
            quality=ClaimEvidenceQuality(quality_score=0.95),
        )
    ]


# =====================================================================
# CONFIDENCE GATE UNIT TESTS
# =====================================================================

def test_gate_high_confidence_no_adjudication():
    """1. High-confidence NLI bypasses adjudication."""
    gate = ConfidenceGate()
    claim = ClaimVerificationItem(
        claim_text="Plan B covers roaming in 45 countries.",
        nli_confidence=0.92,
        top2_scores={"SUPPORTED": 0.92, "CONTRADICTED": 0.08},
        severity=SeverityLevel.MEDIUM,
    )
    res = gate.evaluate(claim, create_sample_evidence())
    assert res.adjudication_required is False
    assert res.trigger == AdjudicationTrigger.NONE


def test_gate_low_confidence_triggers_adjudication():
    """2. Low NLI confidence triggers NLI_LOW_CONFIDENCE."""
    gate = ConfidenceGate()
    claim = ClaimVerificationItem(
        claim_text="Plan B covers roaming.",
        nli_confidence=0.60,  # Below default 0.75 threshold
        top2_scores={"SUPPORTED": 0.60, "CONTRADICTED": 0.40},
        severity=SeverityLevel.MEDIUM,
    )
    res = gate.evaluate(claim, create_sample_evidence(), {"nli_confidence_threshold": 0.75})
    assert res.adjudication_required is True
    assert res.trigger in (AdjudicationTrigger.NLI_LOW_CONFIDENCE, AdjudicationTrigger.NLI_CLOSE_TOP2)


def test_gate_close_top2_triggers_adjudication():
    """3. Close top-2 label margin triggers NLI_CLOSE_TOP2."""
    gate = ConfidenceGate()
    claim = ClaimVerificationItem(
        claim_text="Plan B roaming is available subject to exceptions.",
        nli_confidence=0.78,
        top2_scores={"SUPPORTED": 0.52, "CONTRADICTED": 0.48},  # margin 0.04 < 0.15
        severity=SeverityLevel.MEDIUM,
    )
    res = gate.evaluate(claim, create_sample_evidence(), {"adjudication_top2_margin": 0.15})
    assert res.adjudication_required is True
    assert res.trigger == AdjudicationTrigger.NLI_CLOSE_TOP2


def test_gate_high_severity_marginal_nli_triggers():
    """4. High-severity claim with marginal NLI triggers HIGH_SEVERITY_MARGINAL_NLI."""
    gate = ConfidenceGate()
    claim = ClaimVerificationItem(
        claim_text="Financial contract liability clause is active.",
        nli_confidence=0.80,  # Below strict high severity threshold 0.85
        top2_scores={"SUPPORTED": 0.80, "CONTRADICTED": 0.20},
        severity=SeverityLevel.HIGH,
    )
    res = gate.evaluate(claim, create_sample_evidence(), {"high_severity_nli_threshold": 0.85})
    assert res.adjudication_required is True
    assert res.trigger == AdjudicationTrigger.HIGH_SEVERITY_MARGINAL_NLI


def test_gate_insufficient_evidence_never_triggers_adjudication():
    """5 & 6. Invariant Rule: Missing or inadequate evidence MUST NEVER trigger adjudication."""
    gate = ConfidenceGate()
    # Case 1: Empty evidence list
    claim1 = ClaimVerificationItem(
        claim_text="Quantum teleportation is active.",
        nli_confidence=0.0,
        verification_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
        severity=SeverityLevel.HIGH,
    )
    res1 = gate.evaluate(claim1, [])
    assert res1.adjudication_required is False
    assert res1.trigger == AdjudicationTrigger.NONE
    assert "INSUFFICIENT_EVIDENCE" in res1.reason


# =====================================================================
# ADJUDICATION OUTCOME & INCONCONCLUSIVE TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_adjudication_confident_outcome(async_session: AsyncSession):
    """7. Confident adjudicator produces ADJUDICATED with final_label."""
    service = AdjudicationService()
    claim = ClaimVerificationItem(
        claim_text="Plan B roaming is active.",
        nli_confidence=0.55,
        top2_scores={"SUPPORTED": 0.55, "CONTRADICTED": 0.45},
        severity=SeverityLevel.HIGH,
    )
    pseudo_nli = VerifierResponse(
        label="SUPPORTED",
        nli_confidence=0.55,
        top2_scores={"SUPPORTED": 0.55, "CONTRADICTED": 0.45},
    )
    policy_config = PolicyConfig(max_request_cost=0.05)
    policy_version = PolicyVersion(thresholds={"adjudication_budget_usd": 0.05})

    updated_claim, was_invoked, cost = await service.evaluate_and_adjudicate(
        claim=claim,
        evidence=create_sample_evidence(),
        nli_result=pseudo_nli,
        policy_config=policy_config,
        policy_version=policy_version,
        scenario="CONFIDENT_SUPPORTED",
    )
    assert was_invoked is True
    assert updated_claim.verification_status == VerificationStatus.ADJUDICATED
    assert updated_claim.final_label == "SUPPORTED"
    assert updated_claim.adjudicator_confidence >= 0.80
    assert updated_claim.uncertainty_reason == UncertaintyReason.NONE


@pytest.mark.asyncio
async def test_adjudication_inconclusive_outcome(async_session: AsyncSession):
    """8. Inconclusive adjudicator produces ADJUDICATION_INCONCLUSIVE with final_label = NULL."""
    service = AdjudicationService()
    claim = ClaimVerificationItem(
        claim_text="Plan B roaming is active under complex exceptions.",
        nli_confidence=0.55,
        top2_scores={"SUPPORTED": 0.55, "CONTRADICTED": 0.45},
        severity=SeverityLevel.HIGH,
    )
    pseudo_nli = VerifierResponse(
        label="SUPPORTED",
        nli_confidence=0.55,
        top2_scores={"SUPPORTED": 0.55, "CONTRADICTED": 0.45},
    )
    policy_config = PolicyConfig(max_request_cost=0.05)
    policy_version = PolicyVersion(thresholds={"adjudication_budget_usd": 0.05})

    updated_claim, was_invoked, cost = await service.evaluate_and_adjudicate(
        claim=claim,
        evidence=create_sample_evidence(),
        nli_result=pseudo_nli,
        policy_config=policy_config,
        policy_version=policy_version,
        scenario="INCONCLUSIVE",
    )
    assert was_invoked is True
    assert updated_claim.verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE
    assert updated_claim.final_label is None  # CRITICAL INVARIANT: MUST BE NULL
    assert updated_claim.uncertainty_reason == UncertaintyReason.JUDGE_LOW_CONFIDENCE


# =====================================================================
# ADJUDICATION BUDGET EXHAUSTION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_adjudication_budget_exhaustion(async_session: AsyncSession):
    """9 & 10. Budget exhaustion preserves trigger and sets ADJUDICATION_BUDGET_EXHAUSTED."""
    store = RuntimeStateStore()
    session_id = f"test-sess-{uuid4()}"

    # Consume all available budget ($0.02)
    await store.consume_adjudication_budget(session_id, 0.02)

    service = AdjudicationService(state_store=store)
    claim = ClaimVerificationItem(
        claim_text="Plan B roaming is active.",
        nli_confidence=0.55,
        top2_scores={"SUPPORTED": 0.55, "CONTRADICTED": 0.45},
        severity=SeverityLevel.HIGH,
    )
    pseudo_nli = VerifierResponse(label="SUPPORTED", nli_confidence=0.55)
    policy_config = PolicyConfig(max_request_cost=0.05)
    policy_version = PolicyVersion(thresholds={"adjudication_budget_usd": 0.02})

    updated_claim, was_invoked, cost = await service.evaluate_and_adjudicate(
        claim=claim,
        evidence=create_sample_evidence(),
        nli_result=pseudo_nli,
        policy_config=policy_config,
        policy_version=policy_version,
        session_id=session_id,
    )
    # Judge was NOT invoked due to budget exhaustion
    assert was_invoked is False
    assert updated_claim.verification_status == VerificationStatus.DIRECT_NLI
    assert updated_claim.adjudication_trigger != AdjudicationTrigger.NONE  # Trigger is PRESERVED!
    assert updated_claim.uncertainty_reason == UncertaintyReason.ADJUDICATION_BUDGET_EXHAUSTED


# =====================================================================
# END-TO-END DEMO FIXTURES (DEMOS 12, 13, 14)
# =====================================================================

@pytest.mark.asyncio
async def test_demo_12_ambiguous_nli_adjudicated_to_allow(async_session: AsyncSession):
    """Demo 12: Ambiguous NLI -> Confidence Gate -> Selective Adjudication -> ADJUDICATED -> ALLOW."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Tell me if Plan B provides international roaming across designated regions.",
        scenario="AMBIGUOUS_NLI",
        judge_scenario="CONFIDENT_SUPPORTED",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert resp.adjudication_invocations == 1
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.ADJUDICATED
    assert resp.claims[0].final_label == "SUPPORTED"
    assert resp.timing_telemetry.adjudication_ms > 0.0


@pytest.mark.asyncio
async def test_demo_13_insufficient_evidence_no_adjudication_escalates(async_session: AsyncSession):
    """Demo 13: Insufficient evidence -> INSUFFICIENT_EVIDENCE -> NO Adjudication -> ESCALATE."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Explain quantum teleportation parcel shipping under domestic warranty.",
        scenario="INSUFFICIENT",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ESCALATE
    assert resp.adjudication_invocations == 0  # Invariant: Never invoke judge!
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE
    assert resp.claims[0].adjudication_trigger == AdjudicationTrigger.NONE


@pytest.mark.asyncio
async def test_demo_14_ambiguous_nli_inconclusive_adjudication_escalates(async_session: AsyncSession):
    """Demo 14: Ambiguous NLI -> Adjudicator Inconclusive -> final_label NULL -> ESCALATE."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Tell me if Plan B provides international roaming across designated regions.",
        scenario="AMBIGUOUS_NLI",
        judge_scenario="INCONCLUSIVE",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ESCALATE
    assert resp.adjudication_invocations == 1
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE
    assert resp.claims[0].final_label is None  # Must remain NULL
    assert resp.claims[0].uncertainty_reason == UncertaintyReason.JUDGE_LOW_CONFIDENCE
