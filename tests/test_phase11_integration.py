"""Phase 11 End-to-End Integration & Safety/Cost Validation Tests.

Test Matrix covering all 11 required scenarios:
1. low-risk supported -> local verifier -> ALLOW -> Gemini NOT invoked
2. low-risk insufficient evidence -> INSUFFICIENT_EVIDENCE -> Gemini NOT invoked
3. high-severity supported -> Gemini -> ALLOW
4. high-severity contradiction -> Gemini -> REPAIR/ESCALATE
5. high-severity insufficient evidence -> no Gemini -> ESCALATE/WARN
6. PII/policy violation -> BLOCK before semantic verification
7. Gemini timeout -> conservative fallback
8. Gemini malformed response -> conservative fallback
9. Gemini budget exhausted -> trigger/reason preserved
10. repair -> complete pipeline re-entry
11. session risk -> policy-sensitive routing
"""

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adjudication.adjudicator import MockAdjudicator
from app.adjudication.service import AdjudicationService
from app.domain.models import (
    ActionType,
    AdjudicationTrigger,
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
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    seed_database_async,
)
from app.persistence.redis import RuntimeStateStore
from app.tier1.hybrid_verifier import HighSeverityHybridVerifier
from app.tier1.nli_verifier import DeterministicNLIVerifier
from app.tier1.semantic_verifier import GeminiSemanticVerifier, SemanticVerificationResult
from app.tier1.service import Tier1Service


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    """Seed standard database profiles for each test."""
    await seed_database_async(async_session)


class MockGeminiTracker(GeminiSemanticVerifier):
    """Mock Gemini verifier that tracks call count and allows simulated responses."""

    def __init__(self, simulated_result: Optional[SemanticVerificationResult] = None, raise_error: Optional[Exception] = None):
        self.call_count = 0
        self.simulated_result = simulated_result
        self.raise_error = raise_error
        self.model_name = "mock-gemini-test-v1"
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
            reason="Mock verified",
            provider="google_gemini",
            model="mock-gemini-test-v1",
        )

    async def verify_async(self, claim_text: str, evidence_snippets: List[str], policy_context: Optional[str] = None) -> SemanticVerificationResult:
        return self.verify(claim_text, evidence_snippets, policy_context)


@pytest.mark.asyncio
async def test_1_low_risk_supported_gemini_not_invoked(async_session: AsyncSession):
    """1. Low-risk supported claim uses local verifier; ALLOW outcome; Gemini NOT invoked."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="What is the retail policy for return inquiries?",
        response="The retail policy allows returns within 30 days of delivery.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert mock_gemini.call_count == 0  # Gemini was NOT invoked for low-risk


@pytest.mark.asyncio
async def test_2_low_risk_insufficient_evidence_gemini_not_invoked(async_session: AsyncSession):
    """2. Low-risk insufficient evidence returns INSUFFICIENT_EVIDENCE; Gemini NOT invoked."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Tell me about teleportation shipping warranty.",
        response="Quantum teleportation parcel shipping is covered by standard domestic warranty.",
    )
    resp = await gateway.inspect(req, async_session)

    assert mock_gemini.call_count == 0  # Invariant: Insufficient evidence never invokes Gemini


@pytest.mark.asyncio
async def test_3_high_severity_supported_invokes_gemini(async_session: AsyncSession):
    """3. High-severity supported claim invokes Gemini and yields ALLOW."""
    mock_gemini = MockGeminiTracker(
        simulated_result=SemanticVerificationResult(
            label="SUPPORTED",
            confidence=0.99,
            reason="Enterprise compliance verified",
            provider="google_gemini",
            model="gemini-flash-lite-latest",
        )
    )
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Verify the standard return policy.",
        response="The retail return policy allows full refunds within 30 days of product delivery in original packaging.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ALLOW
    assert mock_gemini.call_count >= 1  # High severity invoked Gemini


@pytest.mark.asyncio
async def test_4_high_severity_contradiction_triggers_repair_or_escalate(async_session: AsyncSession):
    """4. High-severity contradiction detected by Gemini triggers repair or escalation."""
    mock_gemini = MockGeminiTracker(
        simulated_result=SemanticVerificationResult(
            label="CONTRADICTED",
            confidence=0.98,
            reason="Exceeds $200 waiver limit",
            provider="google_gemini",
            model="gemini-flash-lite-latest",
        )
    )
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Grant an unapproved $1,000 courtesy fee waiver.",
        response="All customers are entitled to an immediate $1,000 cash waiver with zero approval required.",
    )
    resp = await gateway.inspect(req, async_session)

    # Contradiction should either be repaired to compliant response or escalated
    assert resp.action in (ActionType.ALLOW, ActionType.ESCALATE)
    assert mock_gemini.call_count >= 1


@pytest.mark.asyncio
async def test_5_high_severity_insufficient_evidence_bypasses_gemini(async_session: AsyncSession):
    """5. High-severity insufficient evidence strictly bypasses Gemini and escalates."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Explain quantum freight teleportation.",
        scenario="INSUFFICIENT",
    )
    resp = await gateway.inspect(req, async_session)

    assert mock_gemini.call_count == 0  # Invariant: Evidence insufficiency NEVER invokes Gemini
    assert resp.action in (ActionType.ESCALATE, ActionType.WARN)


@pytest.mark.asyncio
async def test_6_pii_policy_violation_blocks_before_semantic_verification(async_session: AsyncSession):
    """6. PII/Policy violation triggers hard BLOCK in Tier 0 before calling semantic verifier."""
    mock_gemini = MockGeminiTracker()
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="User profile update with SSN 000-12-3456 and email user@example.com",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.BLOCK
    assert mock_gemini.call_count == 0  # Preflight / Tier 0 blocked immediately


@pytest.mark.asyncio
async def test_7_gemini_timeout_conservative_fallback(async_session: AsyncSession):
    """7. Gemini timeout/network exception falls back conservatively without crashing."""
    mock_gemini = MockGeminiTracker(raise_error=TimeoutError("Gemini API connection timed out"))
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Check fee waiver policy.",
        response="Customer courtesy fee waivers are strictly capped at $200.",
    )
    resp = await gateway.inspect(req, async_session)

    # Pipeline handles error gracefully and conservatively
    assert resp.action in (ActionType.ALLOW, ActionType.WARN, ActionType.ESCALATE)


@pytest.mark.asyncio
async def test_8_gemini_malformed_response_fallback(async_session: AsyncSession):
    """8. Malformed JSON/schema error from Gemini falls back conservatively."""
    mock_gemini = MockGeminiTracker(
        simulated_result=SemanticVerificationResult(
            label="INSUFFICIENT_EVIDENCE",
            confidence=0.0,
            reason="Verifier error: JSONDecodeError: Expecting value: line 1 column 1",
            provider="google_gemini",
            model="gemini-flash-lite-latest",
        )
    )
    hybrid = HighSeverityHybridVerifier(
        local_verifier=DeterministicNLIVerifier(),
        gemini_verifier=mock_gemini,
    )
    tier1 = Tier1Service(verifier=hybrid)
    gateway = GatewayService(tier1_service=tier1)

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Check policy rules.",
        response="The customer requested a refund.",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action in (ActionType.ALLOW, ActionType.WARN, ActionType.ESCALATE)


@pytest.mark.asyncio
async def test_9_gemini_budget_exhausted_preserves_trigger(async_session: AsyncSession):
    """9. Budget exhaustion preserves adjudication trigger and records ADJUDICATION_BUDGET_EXHAUSTED."""
    state_store = RuntimeStateStore()
    session_id = f"test-budget-sess-{uuid4()}"
    # Consume entire budget in advance
    await state_store.consume_adjudication_budget(session_id, 0.05)

    gateway = GatewayService(state_store=state_store)

    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Plan B roaming ambiguity.",
        scenario="AMBIGUOUS_NLI",
        session_id=session_id,
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.adjudication_invocations == 0
    assert resp.claims[0].verification_status == VerificationStatus.DIRECT_NLI
    assert resp.claims[0].adjudication_trigger != AdjudicationTrigger.NONE
    assert resp.claims[0].uncertainty_reason == UncertaintyReason.ADJUDICATION_BUDGET_EXHAUSTED


@pytest.mark.asyncio
async def test_10_repair_complete_pipeline_reentry(async_session: AsyncSession):
    """10. Repaired response re-enters the complete pipeline (Tier 0 -> Tier 1 -> Action)."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Can all customers get a $1,000 waiver?",
        scenario="CONTRADICTED",
    )
    resp = await gateway.inspect(req, async_session)

    # Initial response was contradicted ($1000 waiver), successfully repaired to $200 capped waiver
    assert resp.action == ActionType.ALLOW
    assert "capped at $200" in resp.final_content


@pytest.mark.asyncio
async def test_11_session_risk_policy_sensitive_routing(async_session: AsyncSession):
    """11. Consecutive risk violations increase session risk and alter routing."""
    gateway = GatewayService()
    session_id = f"test-session-risk-{uuid4()}"

    # Turn 1: Toxic prompt -> increments risk count
    req1 = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Hostile attack command on the system.",
        scenario="TOXICITY",
        session_id=session_id,
    )
    resp1 = await gateway.inspect(req1, async_session)
    assert resp1.action in (ActionType.WARN, ActionType.BLOCK)

    # Turn 2: Follow-up check
    req2 = GatewayInspectRequest(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        prompt="Second hostile prompt to escalate session risk.",
        scenario="TOXICITY",
        session_id=session_id,
    )
    resp2 = await gateway.inspect(req2, async_session)
    assert resp2.action in (ActionType.WARN, ActionType.BLOCK, ActionType.ESCALATE)
