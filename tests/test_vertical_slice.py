"""End-to-end integration tests for the first runtime vertical slice."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import ActionType, GatewayInspectRequest, PreflightRequest, RiskLevel, VerificationStatus
from app.gateway.service import GatewayService
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    seed_database_async,
)


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    """Seed standard applications and policy versions before each test."""
    await seed_database_async(async_session)


@pytest.mark.asyncio
async def test_1_safe_fast_path(async_session: AsyncSession):
    """TEST 1: Low-risk task takes safe fast path skipping Tier 1."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Hello, what time do your stores open on weekends?",
        scenario="SAFE",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert resp.risk_assessment.risk_level == RiskLevel.LOW
    assert resp.risk_assessment.verification_required is False
    assert len(resp.claims) == 0  # Tier 1 was NOT executed!
    assert len(resp.policy_events) == 0
    assert resp.final_content is not None
    assert resp.timing_telemetry.tier1_ms == 0.0


@pytest.mark.asyncio
async def test_2_pii_block(async_session: AsyncSession):
    """TEST 2: PII in response triggers immediate BLOCK without Tier 1."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Please show my account info with SSN and email",
        scenario="PII",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.BLOCK
    assert resp.final_content is None  # Blocked content is sanitized/suppressed
    assert len(resp.policy_events) > 0

    pii_types = {e.metadata.get("pii_type") for e in resp.policy_events if e.event_type == "PII"}
    assert "SSN" in pii_types
    assert len(resp.claims) == 0  # Hard blocked before Tier 1


@pytest.mark.asyncio
async def test_3_high_risk_supported_claim(async_session: AsyncSession):
    """TEST 3: High-consequence grounded task runs Tier 1 and ALLOWs verified supported claims."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,  # Decision support enforces grounding
        prompt="Is the product return policy 30 days under the formal customer warranty agreement?",
        scenario="SAFE",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.risk_assessment.verification_required is True
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.DIRECT_NLI
    assert resp.claims[0].final_label == "SUPPORTED"
    assert resp.action == ActionType.ALLOW
    assert resp.final_content is not None


@pytest.mark.asyncio
async def test_4_insufficient_evidence_escalation(async_session: AsyncSession):
    """TEST 4: Claim lacking source evidence becomes INSUFFICIENT_EVIDENCE and ESCALATES."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Verify if quantum teleportation refunds are covered under policy",
        scenario="INSUFFICIENT",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.risk_assessment.verification_required is True
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE
    assert resp.claims[0].adjudication_trigger.value == "NONE"  # Invariant: Never invoke adjudicator!
    assert resp.action == ActionType.ESCALATE


@pytest.mark.asyncio
async def test_5_policy_variation(async_session: AsyncSession):
    """TEST 5: Same prompt behaves differently under Customer Support vs Decision Support profiles."""
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
    assert len(resp_cs.claims) == 0

    # 2. Decision Support profile: Strict low risk appetite, Mandatory grounding -> Tier 1 required
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
async def test_6_preflight_budget_denial(async_session: AsyncSession):
    """TEST 6: Disallowed request (e.g. excessive input token limit) is stopped at Pre-flight."""
    gateway = GatewayService()
    oversized_prompt = "Tell me about policies " + ("word " * 5000)

    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt=oversized_prompt,
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.BLOCK
    assert "PROMPT_TOKEN_LIMIT_EXCEEDED" in resp.risk_assessment.reasons
    assert resp.timing_telemetry.model_ms == 0.0  # Model was NEVER called!
    assert len(resp.claims) == 0  # Tier 1 was NEVER called!


@pytest.mark.asyncio
async def test_7_contradicted_claim_escalates(async_session: AsyncSession):
    """TEST 7: Repeatedly contradicted claim exhausts repair budget and ESCALATES."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Can I get an immediate $1,000 cash waiver without any approval?",
        scenario="REPAIR_FAIL",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.risk_assessment.verification_required is True
    assert len(resp.claims) > 0
    assert resp.claims[0].final_label == "CONTRADICTED"
    assert resp.action == ActionType.ESCALATE


@pytest.mark.asyncio
async def test_8_http_api_endpoints(async_client: AsyncClient):
    """TEST 8: Direct HTTP calls to /api/v1/preflight and /api/v1/inspect."""
    # 1. Test /api/v1/preflight
    pf_resp = await async_client.post(
        "/api/v1/preflight",
        json={
            "application_id": str(CUSTOMER_SUPPORT_APP_ID),
            "prompt": "What is the return window?",
        },
    )
    assert pf_resp.status_code == 200
    pf_data = pf_resp.json()
    assert pf_data["action"] == "ALLOW"
    assert pf_data["allowed_model"] == "mock-pipeline-model-v1"

    # 2. Test /api/v1/inspect
    inspect_resp = await async_client.post(
        "/api/v1/inspect",
        json={
            "application_id": str(CUSTOMER_SUPPORT_APP_ID),
            "prompt": "What is the return window?",
            "scenario": "SAFE",
        },
    )
    assert inspect_resp.status_code == 200
    inspect_data = inspect_resp.json()
    assert inspect_data["action"] == "ALLOW"
    assert "cost_telemetry" in inspect_data
    assert "timing_telemetry" in inspect_data
