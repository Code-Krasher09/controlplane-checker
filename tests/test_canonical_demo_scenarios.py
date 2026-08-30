"""Dedicated regression test suite for the six canonical ControlPlane demo scenarios and core safety invariants."""

import pytest
from typing import List, Optional
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.adjudication.adjudicator import MockAdjudicator
from app.adjudication.service import AdjudicationService
from app.domain.models import (
    ActionType,
    AdjudicationTrigger,
    ClaimVerificationItem,
    GatewayInspectRequest,
    RiskLevel,
    SeverityLevel,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)
from app.gateway.service import GatewayService
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    seed_database_async,
)
from app.tier1.hybrid_verifier import HighSeverityHybridVerifier
from app.tier1.nli_verifier import DeterministicNLIVerifier
from app.tier1.semantic_verifier import GeminiSemanticVerifier, SemanticVerificationResult
from app.tier1.service import Tier1Service


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    """Seed standard database profiles for each test."""
    await seed_database_async(async_session)


class MockGeminiTracker(GeminiSemanticVerifier):
    """Mock Gemini verifier that tracks calls without external API requests."""

    def __init__(self, simulated_result: Optional[SemanticVerificationResult] = None, raise_error: Optional[Exception] = None):
        self.call_count = 0
        self.simulated_result = simulated_result
        self.raise_error = raise_error
        self.model_name = "gemini-flash-lite-latest"
        self.provider = "google_gemini"

    def verify(self, claim_text: str, evidence_snippets: List[str], policy_context: Optional[str] = None) -> SemanticVerificationResult:
        self.call_count += 1
        if self.raise_error:
            raise self.raise_error
        if self.simulated_result:
            return self.simulated_result
        return SemanticVerificationResult(
            label="SUPPORTED",
            confidence=0.98,
            reason="Mock verified logical deduction",
            provider="google_gemini",
            model="gemini-flash-lite-latest",
        )

    async def verify_async(self, claim_text: str, evidence_snippets: List[str], policy_context: Optional[str] = None) -> SemanticVerificationResult:
        return self.verify(claim_text, evidence_snippets, policy_context)


# ==============================================================================
# CANONICAL DEMO SCENARIO TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_1_safe_fast_path(async_session: AsyncSession):
    """Scenario 1: Routine customer support return inquiry uses fast local NLI, avoids cloud calls, ALLOWs."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(local_verifier=DeterministicNLIVerifier(), gemini_verifier=mock_gemini)
    gateway = GatewayService(tier1_service=Tier1Service(verifier=hybrid))

    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="What is the standard retail return policy for order inquiries?",
        response="The retail policy for order inquiries dictates a 30-day return window with full refund.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert resp.risk_assessment.risk_level == RiskLevel.LOW
    assert resp.adjudication_invocations == 0
    assert resp.cost_telemetry.adjudication_calls == 0
    assert mock_gemini.call_count == 0
    assert len(resp.repair_history) == 0
    assert resp.final_content is not None


@pytest.mark.asyncio
async def test_scenario_2_pii_threat_hard_block(async_session: AsyncSession):
    """Scenario 2: Sensitive SSN detected deterministically at Tier 0, downstream bypassed, BLOCKs."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(local_verifier=DeterministicNLIVerifier(), gemini_verifier=mock_gemini)
    gateway = GatewayService(tier1_service=Tier1Service(verifier=hybrid))

    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Customer SSN is 111-22-3301. Please pull all financial records immediately.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.BLOCK
    assert resp.risk_assessment.risk_level == RiskLevel.CRITICAL
    assert any(e.detector == "Tier0_PII_SSN" for e in resp.policy_events)
    assert len(resp.claims) == 0
    assert resp.adjudication_invocations == 0
    assert mock_gemini.call_count == 0
    assert resp.final_content is None


@pytest.mark.asyncio
async def test_scenario_3_high_severity_gemini_judge(async_session: AsyncSession):
    """Scenario 3: Decision Support financial query routes to Gemini, verifies SUPPORTED, ALLOWs."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(local_verifier=DeterministicNLIVerifier(), gemini_verifier=mock_gemini)
    gateway = GatewayService(tier1_service=Tier1Service(verifier=hybrid))

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Verify customer fee waiver policy limits and approval hierarchy.",
        response="Customer courtesy fee waivers are strictly capped at $200 and require explicit manager sign-off.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert resp.risk_assessment.risk_level == RiskLevel.HIGH
    assert mock_gemini.call_count == 1
    assert resp.adjudication_invocations == 1
    assert len(resp.claims) > 0
    assert resp.claims[0].final_label == "SUPPORTED"
    assert resp.claims[0].adjudicator_model == "gemini-flash-lite-latest"
    assert resp.final_content is not None


@pytest.mark.asyncio
async def test_scenario_4_contradiction_self_healing_repair(async_session: AsyncSession):
    """Scenario 4: $1,000 waiver contradiction is detected, repaired to $200 cap, re-verified, ALLOWs."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(local_verifier=DeterministicNLIVerifier(), gemini_verifier=mock_gemini)
    gateway = GatewayService(tier1_service=Tier1Service(verifier=hybrid))

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Are all customers granted unconditional $1,000 fee waivers immediately?",
        response="Yes, all customers are granted unconditional $1,000 fee waivers immediately upon request without any managerial approval.",
        scenario="CONTRADICTED",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert len(resp.repair_history) == 1
    assert resp.cost_telemetry.repair_attempts == 1
    assert resp.repair_history[0]["previous_content"] != resp.repair_history[0]["repaired_content"]
    assert "200" in resp.repair_history[0]["repaired_content"]
    assert resp.final_content is not None
    assert "200" in resp.final_content
    # Telemetry cloud-call count exactly matches actual invocation count
    assert resp.adjudication_invocations == resp.cost_telemetry.adjudication_calls


@pytest.mark.asyncio
async def test_scenario_5_insufficient_evidence_gate(async_session: AsyncSession):
    """Scenario 5: Fictional teleportation inquiry has no grounding, gate blocks hallucination, ESCALATEs."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(local_verifier=DeterministicNLIVerifier(), gemini_verifier=mock_gemini)
    gateway = GatewayService(tier1_service=Tier1Service(verifier=hybrid))

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Provide complete warranty coverage details for interdimensional freight teleportation.",
        response="Quantum teleportation parcel shipping is covered by standard domestic warranty.",
        scenario="INSUFFICIENT",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ESCALATE
    assert mock_gemini.call_count == 0
    assert resp.adjudication_invocations == 0
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE
    assert resp.final_content is None


@pytest.mark.asyncio
async def test_scenario_6_borderline_semantic_ambiguity(async_session: AsyncSession):
    """Scenario 6: Close top-2 score margin routes to secondary judge, inconclusive verdict ESCALATEs."""
    gateway = GatewayService()

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Does Plan B provide complimentary international roaming across all designated tier-2 regions?",
        response="Plan B provides complimentary international roaming across 45 designated countries subject to exclusions.",
        scenario="AMBIGUOUS_NLI",
        judge_scenario="INCONCLUSIVE",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ESCALATE
    assert resp.adjudication_invocations == 1
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE
    assert resp.claims[0].adjudication_trigger == AdjudicationTrigger.NLI_CLOSE_TOP2
    assert resp.claims[0].final_label is None
    assert resp.final_content is None


# ==============================================================================
# CORE DECISION INVARIANT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_invariant_1_no_cloud_calls_no_gemini_claims(async_session: AsyncSession):
    """Invariant 1: If adjudication_invocations == 0, response must not claim cloud adjudication was invoked."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="What is the return window for retail products?",
        response="Products can be returned within 30 days.",
    )
    resp = await gateway.inspect(req, async_session)

    if resp.adjudication_invocations == 0:
        assert resp.cost_telemetry.adjudication_calls == 0
        for claim in resp.claims:
            if claim.verification_status == VerificationStatus.DIRECT_NLI:
                assert claim.adjudication_trigger == AdjudicationTrigger.NONE


@pytest.mark.asyncio
async def test_invariant_2_hard_block_skips_downstream(async_session: AsyncSession):
    """Invariant 2: When blocked at Tier 0, downstream semantic verifiers are skipped with zero cost."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Customer SSN 000-11-2222 leaked in prompt.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.BLOCK
    assert len(resp.claims) == 0
    assert resp.cost_telemetry.adjudication_calls == 0
    assert resp.adjudication_invocations == 0


@pytest.mark.asyncio
async def test_invariant_3_repair_requires_reverification_to_allow(async_session: AsyncSession):
    """Invariant 3: A contradicted response cannot be ALLOWed unless the repaired text passes verification."""
    gateway = GatewayService()
    # Scenario REPAIR_FAIL forces repair attempt to remain contradicted
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Are all customers granted unconditional $1,000 fee waivers immediately?",
        response="All customers are entitled to an immediate $1,000 cash waiver with zero approval required.",
        scenario="REPAIR_FAIL",
    )
    resp = await gateway.inspect(req, async_session)

    # When repair fails to produce compliant text, ActionEngine strictly ESCALATEs
    assert resp.action == ActionType.ESCALATE
    assert resp.final_content is None


@pytest.mark.asyncio
async def test_invariant_4_insufficient_evidence_never_allows(async_session: AsyncSession):
    """Invariant 4: INSUFFICIENT_EVIDENCE can never resolve to ALLOW action."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Describe warp drive maintenance protocols for stellar logistics.",
        response="Warp drive core coolant must be replaced every 5 light years.",
        scenario="INSUFFICIENT",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action in (ActionType.ESCALATE, ActionType.WARN, ActionType.ABSTAIN)
    assert resp.action != ActionType.ALLOW


@pytest.mark.asyncio
async def test_invariant_5_inconclusive_adjudication_never_allows(async_session: AsyncSession):
    """Invariant 5: ADJUDICATION_INCONCLUSIVE can never resolve to ALLOW action."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Is clause 4B applicable to foreign entities?",
        response="Plan B roaming is active across foreign territories subject to ambiguous provisions.",
        judge_scenario="INCONCLUSIVE",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action in (ActionType.ESCALATE, ActionType.WARN)
    assert resp.action != ActionType.ALLOW


@pytest.mark.asyncio
async def test_invariant_6_final_action_matches_action_engine(async_session: AsyncSession):
    """Invariant 6: The serialized final action must match terminal candidate action precedence."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="What is the return policy?",
        response="The return policy permits full refunds within 30 days.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action in resp.risk_assessment.candidate_actions or resp.action == ActionType.ALLOW


@pytest.mark.asyncio
async def test_invariant_7_telemetry_internal_consistency(async_session: AsyncSession):
    """Invariant 7: Timing and cost telemetry must be non-negative and mutually consistent."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Return policy inquiry.",
        response="30 days return window.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.timing_telemetry.total_controlplane_ms >= 0.0
    assert resp.timing_telemetry.preflight_ms >= 0.0
    assert resp.cost_telemetry.total_tokens >= resp.cost_telemetry.input_tokens
    assert resp.cost_telemetry.total_cost_usd >= 0.0
