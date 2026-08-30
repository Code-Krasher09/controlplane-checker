"""Phase 12A.5: High-Severity Safety Failure Closure & Action Engine Regression Tests."""

from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.actions.service import ActionEngine
from app.domain.models import (
    ActionType,
    AdjudicationTrigger,
    ClaimEvidenceQuality,
    ClaimVerificationItem,
    GatewayInspectRequest,
    RiskAssessmentResult,
    RiskLevel,
    SeverityLevel,
    UncertaintyReason,
    VerificationStatus,
)
from app.gateway.service import GatewayService
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    PolicyConfig,
    PolicyVersion,
    seed_database_async,
)


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    await seed_database_async(async_session)


@pytest.mark.asyncio
async def test_1_high_severity_contradiction_successful_repair_yields_allow(async_session: AsyncSession):
    """1. High-severity contradiction with successful repair returns ALLOW."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Can I get an immediate $1,000 courtesy waiver?",
        scenario="CONTRADICTED",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert resp.cost_telemetry.repair_attempts == 1
    assert "$200" in (resp.final_content or "")


@pytest.mark.asyncio
async def test_2_high_severity_contradiction_failed_repair_yields_escalate():
    """2. High-severity contradiction where repair fails yields ESCALATE."""
    engine = ActionEngine()
    risk = RiskAssessmentResult(
        risk_level=RiskLevel.HIGH,
        severity=SeverityLevel.HIGH,
        verification_required=True,
    )
    policy_config = PolicyConfig(
        max_repair_attempts=2,
        risk_appetite="LOW",
    )
    claim = ClaimVerificationItem(
        claim_id=uuid4(),
        claim_index=0,
        claim_text="Unapproved $1,000 cash waiver granted.",
        severity=SeverityLevel.HIGH,
        verification_status=VerificationStatus.DIRECT_NLI,
        final_label="CONTRADICTED",
    )

    # Attempt 2 (exhausted retries)
    action = engine.resolve(
        risk_assessment=risk,
        policy_config=policy_config,
        claims=[claim],
        current_repair_attempt=2,
    )
    assert action == ActionType.ESCALATE


@pytest.mark.asyncio
async def test_3_high_severity_insufficient_evidence_yields_escalate():
    """3. High-severity claim with INSUFFICIENT_EVIDENCE strictly yields ESCALATE."""
    engine = ActionEngine()
    risk = RiskAssessmentResult(
        risk_level=RiskLevel.HIGH,
        severity=SeverityLevel.HIGH,
        verification_required=True,
    )
    policy_config = PolicyConfig(
        risk_appetite="LOW",
        allow_warn_abstain=True,
    )
    claim = ClaimVerificationItem(
        claim_id=uuid4(),
        claim_index=0,
        claim_text="Interdimensional parcel shipping warranty.",
        severity=SeverityLevel.HIGH,
        verification_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
        final_label="INSUFFICIENT_EVIDENCE",
    )

    action = engine.resolve(
        risk_assessment=risk,
        policy_config=policy_config,
        claims=[claim],
    )
    assert action == ActionType.ESCALATE


@pytest.mark.asyncio
async def test_4_high_severity_adjudication_inconclusive_yields_escalate():
    """4. High-severity claim with ADJUDICATION_INCONCLUSIVE strictly yields ESCALATE."""
    engine = ActionEngine()
    risk = RiskAssessmentResult(
        risk_level=RiskLevel.HIGH,
        severity=SeverityLevel.HIGH,
        verification_required=True,
    )
    policy_config = PolicyConfig(
        risk_appetite="MEDIUM",
    )
    claim = ClaimVerificationItem(
        claim_id=uuid4(),
        claim_index=0,
        claim_text="Ambiguous roaming policy coverage.",
        severity=SeverityLevel.HIGH,
        verification_status=VerificationStatus.ADJUDICATION_INCONCLUSIVE,
        final_label=None,
    )

    action = engine.resolve(
        risk_assessment=risk,
        policy_config=policy_config,
        claims=[claim],
    )
    assert action == ActionType.ESCALATE


@pytest.mark.asyncio
async def test_5_no_verified_supported_state_cannot_allow_on_high_severity():
    """5. An unverified/unresolved semantic state on high severity cannot ALLOW."""
    engine = ActionEngine()
    risk = RiskAssessmentResult(
        risk_level=RiskLevel.HIGH,
        severity=SeverityLevel.HIGH,
        verification_required=True,
    )
    policy_config = PolicyConfig(
        risk_appetite="LOW",
    )
    claim = ClaimVerificationItem(
        claim_id=uuid4(),
        claim_index=0,
        claim_text="Uncertain enterprise claim.",
        severity=SeverityLevel.HIGH,
        verification_status=VerificationStatus.DIRECT_NLI,
        final_label="UNKNOWN_OR_UNVERIFIED",
    )

    action = engine.resolve(
        risk_assessment=risk,
        policy_config=policy_config,
        claims=[claim],
    )
    assert action == ActionType.ESCALATE


@pytest.mark.asyncio
async def test_6_tier0_ssn_prompt_blocks_immediately(async_session: AsyncSession):
    """6. Tier 0 detects SSN in prompt and enforces hard BLOCK immediately."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Customer SSN is 111-22-3301. Please look up.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.BLOCK
    assert resp.claims == []
