"""Comprehensive unit and integration tests for the Bounded Repair Loop and Full Pipeline Re-entry."""

from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import (
    ActionType,
    ClaimVerificationItem,
    EvidenceSnippet,
    GatewayInspectRequest,
    SeverityLevel,
    VerificationStatus,
)
from app.gateway.service import GatewayService
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    PolicyConfig,
    seed_database_async,
)
from app.repair.service import RepairPlanner, RepairService


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    """Seed standard database profiles."""
    await seed_database_async(async_session)


# =====================================================================
# REPAIR PLANNER UNIT TESTS
# =====================================================================

def test_repair_planner_instruction_generation():
    """Verify RepairPlanner creates targeted evidence-constrained prompts."""
    planner = RepairPlanner()
    failed_claim = ClaimVerificationItem(
        claim_text="All customers get unlimited $1,000 cash waivers.",
        severity=SeverityLevel.HIGH,
    )
    evidence = EvidenceSnippet(
        content_snippet="Customer courtesy fee waivers are strictly capped at $200 per account.",
        source_id="doc-waivers-2026",
    )
    policy = PolicyConfig(max_repair_attempts=2)

    plan = planner.plan_repair(
        failed_claims=[failed_claim],
        evidence=[evidence],
        previous_response="You get an unlimited $1,000 waiver.",
        attempt_number=1,
        policy_config=policy,
    )

    assert plan.attempt_number == 1
    assert plan.max_attempts == 2
    assert "Contradicted claim(s):" in plan.repair_prompt
    assert "All customers get unlimited $1,000 cash waivers." in plan.repair_prompt
    assert "Customer courtesy fee waivers are strictly capped at $200" in plan.repair_prompt


def test_repair_service_bounds():
    """Verify RepairService enforces max repair limits."""
    service = RepairService()
    policy = PolicyConfig(max_repair_attempts=2)

    assert service.can_repair(policy, attempt_number=0) is True
    assert service.can_repair(policy, attempt_number=1) is True
    assert service.can_repair(policy, attempt_number=2) is False


# =====================================================================
# END-TO-END REPAIR LOOP INTEGRATION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_repair_flow_success_with_reentry(async_session: AsyncSession):
    """Contradicted response triggers REPAIR -> regenerates -> re-enters full pipeline -> ALLOW."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Can I get an immediate $1,000 cash waiver without any approval?",
        scenario="CONTRADICTED",
    )
    resp = await gateway.inspect(req, async_session)

    # Verifies repair occurred and successfully corrected the error
    assert resp.action == ActionType.ALLOW
    assert resp.cost_telemetry.repair_attempts == 1
    assert len(resp.repair_history) == 1
    assert resp.final_content is not None
    assert "$200" in resp.final_content
    assert resp.timing_telemetry.repair_ms > 0.0


@pytest.mark.asyncio
async def test_repair_repeated_failure_exhausts_and_escalates(async_session: AsyncSession):
    """Repeatedly failing repair exceeds max attempts without looping infinitely -> ESCALATES."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Can I get an immediate $1,000 cash waiver without any approval?",
        scenario="REPAIR_FAIL",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ESCALATE
    assert resp.cost_telemetry.repair_attempts == 2  # Bounded to max 2 attempts!
    assert len(resp.repair_history) == 2


@pytest.mark.asyncio
async def test_semantic_separation_insufficient_vs_inconclusive(async_session: AsyncSession):
    """Verify semantic separation between Evidence Insufficiency and Inconclusive Adjudication."""
    gateway = GatewayService()

    # Flow A: Evidence Insufficiency
    req_a = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Explain quantum teleportation parcel shipping under domestic warranty.",
        scenario="INSUFFICIENT",
    )
    resp_a = await gateway.inspect(req_a, async_session)

    # Flow B: Judge Inconclusive
    req_b = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Tell me if Plan B provides international roaming across designated regions.",
        scenario="AMBIGUOUS_NLI",
        judge_scenario="INCONCLUSIVE",
    )
    resp_b = await gateway.inspect(req_b, async_session)

    # Both produce ESCALATE for high-severity decisions, but with distinct audit states:
    assert resp_a.action == ActionType.ESCALATE
    assert resp_b.action == ActionType.ESCALATE

    # Case A: Never called judge, state is INSUFFICIENT_EVIDENCE
    assert resp_a.adjudication_invocations == 0
    assert resp_a.claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE

    # Case B: Called judge, state is ADJUDICATION_INCONCLUSIVE with NULL final_label
    assert resp_b.adjudication_invocations == 1
    assert resp_b.claims[0].verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE
    assert resp_b.claims[0].final_label is None
