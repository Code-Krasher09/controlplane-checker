"""Phase 3E, 3F, 3G & V1.2 Regressions — Policy Profiles, Immutability, and Validation Tests."""

from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import (
    ActionType,
    AdjudicationTrigger,
    GatewayInspectRequest,
    RiskLevel,
    UncertaintyReason,
    VerificationStatus,
)
from app.gateway.service import GatewayService
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    Application,
    PolicyConfig,
    PolicyVersion,
    RuntimeStateStore,
    seed_database_async,
)
from app.preflight.policy_validator import PolicyValidator


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    await seed_database_async(async_session)


# =====================================================================
# POLICY PROFILE RESOLUTION & THRESHOLD DYNAMICS
# =====================================================================

@pytest.mark.asyncio
async def test_20_three_profiles_resolve_correctly(async_session: AsyncSession):
    """Test 20: Customer Support, Internal Knowledge, and Decision Support load from DB."""
    for app_id in (CUSTOMER_SUPPORT_APP_ID, INTERNAL_KB_APP_ID, DECISION_SUPPORT_APP_ID):
        stmt = select(Application).where(Application.application_id == app_id)
        res = await async_session.execute(stmt)
        app = res.scalar_one_or_none()
        assert app is not None
        assert len(app.policies) > 0
        assert len(app.policies[0].versions) > 0


@pytest.mark.asyncio
async def test_21_profile_thresholds_from_persisted_policy(async_session: AsyncSession):
    """Test 21: Thresholds are read dynamically from PolicyVersion.thresholds."""
    stmt = select(PolicyVersion).join(PolicyConfig).where(PolicyConfig.application_id == DECISION_SUPPORT_APP_ID)
    res = await async_session.execute(stmt)
    version_ds = res.scalar_one()

    assert version_ds.thresholds["nli_confidence_threshold"] == 0.85
    assert version_ds.thresholds["adjudication_budget_usd"] == 0.05
    assert version_ds.thresholds["min_evidence_quality"] == 0.65


@pytest.mark.asyncio
async def test_22_same_prompt_produces_policy_dependent_decisions(async_session: AsyncSession):
    """Test 22: Identical prompt behaves differently under Customer Support vs Decision Support."""
    gateway = GatewayService()
    prompt = "Can I return a delivered item?"

    # 1. Customer Support profile: Recommended grounding, low risk -> Fast path ALLOW without Tier 1
    req_cs = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt=prompt,
        scenario="SAFE",
    )
    resp_cs = await gateway.inspect(req_cs, async_session)
    assert resp_cs.action == ActionType.ALLOW
    assert resp_cs.risk_assessment.verification_required is False

    # 2. Decision Support profile: Mandatory grounding -> Tier 1 Verification executed
    req_ds = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt=prompt,
        scenario="SAFE",
    )
    resp_ds = await gateway.inspect(req_ds, async_session)
    assert resp_ds.action == ActionType.ALLOW
    assert resp_ds.risk_assessment.verification_required is True
    assert len(resp_ds.claims) > 0


@pytest.mark.asyncio
async def test_23_policy_version_immutability(async_session: AsyncSession):
    """Test 23: Verified traces preserve the exact policy snapshot."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Hello, what time do your stores open on weekends?",
        scenario="SAFE",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.applied_policy is not None
    assert resp.applied_policy["application_name"] == "Customer Support Assistant"
    assert resp.applied_policy["risk_appetite"] == "MEDIUM"


# =====================================================================
# POLICY VALIDATOR CONSTRAINTS
# =====================================================================

def test_24_invalid_policies_rejected_by_validator():
    """Test 24: Validator rejects out-of-bounds thresholds, negative budgets, and invalid taxonomies."""
    validator = PolicyValidator()

    # Case 1: Invalid risk appetite
    is_valid, errors = validator.validate_policy(risk_appetite="EXTREME", max_repair_attempts=2)
    assert is_valid is False
    assert any("risk appetite" in e.lower() for e in errors)

    # Case 2: Negative budget
    is_valid, errors = validator.validate_policy(risk_appetite="LOW", max_repair_attempts=2, max_request_cost=-0.05)
    assert is_valid is False
    assert any("negative" in e.lower() for e in errors)

    # Case 3: Out-of-bounds threshold (> 1.0)
    is_valid, errors = validator.validate_policy(
        risk_appetite="LOW",
        max_repair_attempts=2,
        thresholds={"nli_confidence_threshold": 1.5},
    )
    assert is_valid is False
    assert any("between 0.0 and 1.0" in e for e in errors)

    # Case 4: Invalid action name
    is_valid, errors = validator.validate_policy(
        risk_appetite="LOW",
        max_repair_attempts=2,
        action_precedence=["INVALID_ACTION_NAME"],
    )
    assert is_valid is False
    assert any("invalid action" in e.lower() for e in errors)


# =====================================================================
# V1.2 CRITICAL SEMANTIC INVARIANT REGRESSIONS
# =====================================================================

@pytest.mark.asyncio
async def test_25_evidence_insufficiency_never_invokes_adjudicator(async_session: AsyncSession):
    """Test 25: Evidence Insufficiency NEVER invokes secondary adjudication."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Explain quantum teleportation shipping under domestic warranty.",
        scenario="INSUFFICIENT",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ESCALATE
    assert resp.adjudication_invocations == 0
    assert resp.claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.asyncio
async def test_26_ambiguous_nli_invokes_adjudicator(async_session: AsyncSession):
    """Test 26: Ambiguous NLI against adequate evidence invokes adjudicator."""
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
    assert resp.claims[0].verification_status == VerificationStatus.ADJUDICATED
    assert resp.claims[0].final_label == "SUPPORTED"


@pytest.mark.asyncio
async def test_27_inconclusive_adjudicator_produces_null_final_label(async_session: AsyncSession):
    """Test 27: Inconclusive judge produces ADJUDICATION_INCONCLUSIVE with final_label = NULL."""
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
    assert resp.claims[0].verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE
    assert resp.claims[0].final_label is None


@pytest.mark.asyncio
async def test_28_budget_exhaustion_preserves_trigger(async_session: AsyncSession):
    """Test 28: Exhausted adjudication budget skips judge, preserves trigger and marks uncertainty."""
    store = RuntimeStateStore()
    session_id = f"test-exhaust-{uuid4()}"
    await store.consume_adjudication_budget(session_id, 0.05)

    gateway = GatewayService(state_store=store)
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Tell me if Plan B provides international roaming across designated regions.",
        scenario="AMBIGUOUS_NLI",
        session_id=session_id,
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.adjudication_invocations == 0
    assert resp.claims[0].verification_status == VerificationStatus.DIRECT_NLI
    assert resp.claims[0].adjudication_trigger != AdjudicationTrigger.NONE
    assert resp.claims[0].uncertainty_reason == UncertaintyReason.ADJUDICATION_BUDGET_EXHAUSTED


@pytest.mark.asyncio
async def test_29_repair_reenters_full_pipeline(async_session: AsyncSession):
    """Test 29: Repaired candidate responses re-enter the full pipeline (Tier 0 -> Risk -> Tier 1)."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Can I get an immediate $1,000 cash waiver without any approval?",
        scenario="CONTRADICTED",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert resp.cost_telemetry.repair_attempts == 1
    assert "$200" in (resp.final_content or "")
