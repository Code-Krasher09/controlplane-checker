"""Phase 3D — Session Risk Accumulation, Dynamic Policy Tuning, and Multi-Turn Tests."""

from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import (
    ActionType,
    ClaimVerificationItem,
    GatewayInspectRequest,
    PolicyEventItem,
    SeverityLevel,
    VerificationStatus,
)
from app.gateway.service import GatewayService
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    RuntimeStateStore,
    seed_database_async,
)
from app.risk.session_risk import SessionRiskTracker


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    await seed_database_async(async_session)


@pytest.mark.asyncio
async def test_13_initial_session_risk_is_normal():
    """Test 13: Initial session has score 0.0 and NORMAL level."""
    store = RuntimeStateStore()
    tracker = SessionRiskTracker(store)
    session_id = f"sess-init-{uuid4()}"

    telemetry = await tracker.get_session_telemetry(session_id)
    assert telemetry.current_score == 0.0
    assert telemetry.level == "NORMAL"
    assert telemetry.turn_count == 0


@pytest.mark.asyncio
async def test_14_uncertainty_increases_session_risk():
    """Test 14: Inconclusive adjudication or warnings increase session score (+1.0)."""
    store = RuntimeStateStore()
    tracker = SessionRiskTracker(store)
    session_id = f"sess-unc-{uuid4()}"

    inconclusive_claim = ClaimVerificationItem(
        claim_text="Plan B roaming is active.",
        verification_status=VerificationStatus.ADJUDICATION_INCONCLUSIVE,
    )
    res = await tracker.record_turn_outcome(
        session_id=session_id,
        prior_score=0.0,
        policy_events=[],
        claims=[inconclusive_claim],
        action=ActionType.WARN,
    )

    assert res.current_score == 1.0
    assert res.turn_count == 1
    assert res.uncertainties_count == 1


@pytest.mark.asyncio
async def test_15_contradiction_increases_session_risk():
    """Test 15: Contradicted claim increases session score (+3.0)."""
    store = RuntimeStateStore()
    tracker = SessionRiskTracker(store)
    session_id = f"sess-contra-{uuid4()}"

    contra_claim = ClaimVerificationItem(
        claim_text="Waiver is $1,000.",
        final_label="CONTRADICTED",
    )
    res = await tracker.record_turn_outcome(
        session_id=session_id,
        prior_score=0.0,
        policy_events=[],
        claims=[contra_claim],
        action=ActionType.ESCALATE,
    )

    assert res.current_score == 3.0
    assert res.contradictions_count == 1
    assert res.level in ("ELEVATED", "NORMAL")


@pytest.mark.asyncio
async def test_16_repeated_failures_transition_to_strict():
    """Test 16: Accumulating score transitions from NORMAL -> ELEVATED -> STRICT."""
    store = RuntimeStateStore()
    tracker = SessionRiskTracker(store)
    session_id = f"sess-rep-{uuid4()}"

    # Turn 1: Contradiction (+3.0 -> 3.0 ELEVATED)
    contra_claim = ClaimVerificationItem(claim_text="c1", final_label="CONTRADICTED")
    t1 = await tracker.record_turn_outcome(session_id, 0.0, [], [contra_claim], ActionType.ESCALATE)
    assert t1.current_score == 3.0
    assert t1.level == "ELEVATED"

    # Turn 2: Policy violation (+5.0 -> 8.0 STRICT)
    pii_event = PolicyEventItem(event_type="PII", detector="PII", severity=SeverityLevel.CRITICAL)
    t2 = await tracker.record_turn_outcome(session_id, 3.0, [pii_event], [], ActionType.BLOCK)
    assert t2.current_score == 8.0
    assert t2.level == "STRICT"


@pytest.mark.asyncio
async def test_17_session_risk_affects_pipeline_routing(async_session: AsyncSession):
    """Test 17: When session risk becomes STRICT, mandatory grounding is triggered."""
    store = RuntimeStateStore()
    session_id = f"sess-strict-route-{uuid4()}"

    # Manually elevate session to STRICT (score 8.0)
    await store.update_session_risk_state(session_id, 8.0, "VIOLATION")

    gateway = GatewayService(state_store=store)
    # Customer support normally permits fast-path ALLOW for simple safe queries,
    # but with STRICT session risk, verification becomes mandatory!
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Hello, what time do your stores open on weekends?",
        scenario="SAFE",
        session_id=session_id,
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.session_risk.level == "STRICT"
    assert "SESSION_RISK_STRICT_MANDATORY_GROUNDING" in resp.risk_assessment.reasons
    assert resp.risk_assessment.verification_required is True


@pytest.mark.asyncio
async def test_18_multi_turn_session_integration(async_session: AsyncSession):
    """Test 18: Multi-turn deterministic integration: Turn 1 Safe -> Turn 2 Uncertainty -> Turn 3 Contradiction."""
    gateway = GatewayService()
    session_id = f"sess-multi-{uuid4()}"

    # Turn 1: Safe request
    req1 = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Hello, what time do your stores open on weekends?",
        scenario="SAFE",
        session_id=session_id,
    )
    resp1 = await gateway.inspect(req1, async_session)
    assert resp1.action == ActionType.ALLOW
    assert resp1.session_risk.current_score == 0.0
    assert resp1.session_risk.turn_count == 1

    # Turn 2: Ambiguous / Inconclusive request (+1.0 uncertainty)
    req2 = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Can I get a fee waiver for Plan B roaming exclusions?",
        scenario="AMBIGUOUS_NLI",
        judge_scenario="INCONCLUSIVE",
        session_id=session_id,
    )
    resp2 = await gateway.inspect(req2, async_session)
    assert resp2.session_risk.prior_score == 0.0
    assert resp2.session_risk.current_score >= 1.0
    assert resp2.session_risk.turn_count == 2

    # Turn 3: Contradicted request (+2.0 or +3.0)
    req3 = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Can I get an immediate $1,000 cash waiver without any approval?",
        scenario="REPAIR_FAIL",
        session_id=session_id,
    )
    resp3 = await gateway.inspect(req3, async_session)
    assert resp3.session_risk.prior_score >= 1.0
    assert resp3.session_risk.current_score >= 4.0
    assert resp3.session_risk.turn_count == 3


@pytest.mark.asyncio
async def test_19_sessions_are_isolated():
    """Test 19: Risk accumulation in session A does not affect session B."""
    store = RuntimeStateStore()
    tracker = SessionRiskTracker(store)
    sess_a = f"sess-iso-a-{uuid4()}"
    sess_b = f"sess-iso-b-{uuid4()}"

    # Elevate session A
    await store.update_session_risk_state(sess_a, 5.0, "VIOLATION")

    res_a = await tracker.get_session_telemetry(sess_a)
    res_b = await tracker.get_session_telemetry(sess_b)

    assert res_a.current_score == 5.0
    assert res_a.level == "ELEVATED"

    assert res_b.current_score == 0.0
    assert res_b.level == "NORMAL"
