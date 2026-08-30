"""Phase 3A & 3B — Evidence Quality Unit and Integration Tests."""

from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import (
    ActionType,
    AdjudicationTrigger,
    ClaimEvidenceQuality,
    ClaimVerificationItem,
    EvidenceSnippet,
    GatewayInspectRequest,
    SeverityLevel,
    VerificationStatus,
)
from app.gateway.service import GatewayService
from app.persistence import DECISION_SUPPORT_APP_ID, seed_database_async
from app.tier1.evidence_quality import EvidenceQualityEvaluator


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    await seed_database_async(async_session)


def test_1_high_authority_fresh_relevant_evidence():
    """Test 1: Official enterprise document with fresh version and strong lexical overlap."""
    evaluator = EvidenceQualityEvaluator()
    claim = "Standard retail return policy permits full refunds within 30 days."
    snippet = EvidenceSnippet(
        source_type="POLICY_DOC",
        source_id="doc-returns-2026",
        content_snippet="Standard retail return policy permits full refunds within 30 days of product delivery in original packaging.",
        quality=ClaimEvidenceQuality(authority="HIGH", freshness=1.0),
    )
    quality = evaluator.evaluate_snippet(claim, snippet)

    assert quality.authority == "HIGH"
    assert quality.freshness == 1.0
    assert quality.relevance >= 0.85
    assert quality.completeness >= 0.85
    assert quality.quality_score >= 0.85


def test_2_low_authority_evidence_penalized():
    """Test 2: Low-authority unverified source receives lower composite score."""
    evaluator = EvidenceQualityEvaluator()
    claim = "Standard retail return policy permits full refunds within 30 days."
    snippet = EvidenceSnippet(
        source_type="UNVERIFIED",
        source_id="untrusted-user-post-123",
        content_snippet="Standard retail return policy permits full refunds within 30 days.",
        metadata={"authority": "LOW"},
    )
    quality = evaluator.evaluate_snippet(claim, snippet)

    assert quality.authority == "LOW"
    assert quality.quality_score < 0.85


def test_3_stale_evidence_penalized():
    """Test 3: Deprecated / stale document receives lower freshness score."""
    evaluator = EvidenceQualityEvaluator()
    claim = "Standard retail return policy permits full refunds within 30 days."
    snippet = EvidenceSnippet(
        source_type="POLICY_DOC",
        source_id="doc-returns-2020-deprecated",
        content_snippet="Standard retail return policy permits full refunds within 30 days.",
        metadata={"is_stale": True, "freshness_status": "STALE"},
    )
    quality = evaluator.evaluate_snippet(claim, snippet)

    assert quality.freshness_status == "STALE"
    assert quality.freshness == 0.40
    assert quality.quality_score < 0.90


def test_4_incomplete_fragmented_evidence_penalized():
    """Test 4: Fragmented or short snippets receive completeness length penalty."""
    evaluator = EvidenceQualityEvaluator()
    claim = "Financial contract liability clause is active under European jurisdiction across international accounts."
    snippet = EvidenceSnippet(
        source_type="POLICY_DOC",
        source_id="doc-snippet-short",
        content_snippet="clause is active.",  # Very short snippet (<40 chars)
    )
    quality = evaluator.evaluate_snippet(claim, snippet)

    assert quality.completeness < 0.40
    assert quality.quality_score < 0.65


def test_5_quality_score_calculation_formula():
    """Test 5: Explicit formula verification (0.35*rel + 0.25*auth + 0.20*fresh + 0.20*comp)."""
    evaluator = EvidenceQualityEvaluator()
    claim = "Customers get courtesy fee waivers."
    snippet = EvidenceSnippet(
        source_type="POLICY_DOC",
        source_id="doc-waivers",
        content_snippet="Customer courtesy fee waivers are permitted.",
    )
    quality = evaluator.evaluate_snippet(claim, snippet)

    expected = (
        (0.35 * quality.relevance)
        + (0.25 * evaluator.AUTHORITY_WEIGHTS.get(quality.authority, 0.70))
        + (0.20 * quality.freshness)
        + (0.20 * quality.completeness)
    )
    assert abs(quality.quality_score - expected) < 0.001


def test_6_weak_evidence_yields_insufficient_evidence():
    """Test 6: When evidence quality is below threshold, is_adequate returns False."""
    evaluator = EvidenceQualityEvaluator()
    claim = "Advanced quantum teleportation applies to parcel delivery."
    # High authority but zero relevance / completeness to teleportation claim
    snippet = EvidenceSnippet(
        source_type="POLICY_DOC",
        source_id="doc-returns-2026",
        content_snippet="Standard retail return policy permits full refunds within 30 days.",
    )
    evaluated = evaluator.evaluate_evidence_set(claim, [snippet])
    assert evaluator.is_adequate(evaluated, {"min_evidence_quality": 0.60}) is False


@pytest.mark.asyncio
async def test_7_weak_evidence_never_triggers_adjudication(async_session: AsyncSession):
    """Test 7: Invariant check - Weak/insufficient evidence MUST NEVER trigger Selective Adjudication."""
    gateway = GatewayService()
    req = GatewayInspectRequest(
        application_id=DECISION_SUPPORT_APP_ID,
        prompt="Explain quantum teleportation parcel shipping under domestic warranty.",
        scenario="INSUFFICIENT",
    )
    resp = await gateway.inspect(req, async_session)

    assert resp.action == ActionType.ESCALATE
    assert resp.adjudication_invocations == 0
    assert len(resp.claims) > 0
    assert resp.claims[0].verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE
    assert resp.claims[0].adjudication_trigger == AdjudicationTrigger.NONE
