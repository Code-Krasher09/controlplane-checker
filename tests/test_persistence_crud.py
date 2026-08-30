"""Persistence CRUD and relationship integration tests."""

from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.persistence import (
    AIModel,
    Application,
    AuditEvent,
    Claim,
    ClaimEvidence,
    Evidence,
    Intervention,
    PolicyConfig,
    PolicyVersion,
    RepairAttempt,
    Request,
    Response,
    seed_database_async,
)


@pytest.mark.asyncio
async def test_application_and_policy_creation(async_session: AsyncSession):
    """Test creating an application with policy configs and versions."""
    app = Application(
        application_id=uuid4(),
        name="Test Support App",
        application_type="CUSTOMER_SUPPORT",
        mode="REALTIME",
    )
    policy = PolicyConfig(
        policy_id=uuid4(),
        application=app,
        policy_name="Standard Support Policy",
        risk_appetite="MEDIUM",
        require_grounding=False,
        max_repair_attempts=2,
    )
    version = PolicyVersion(
        policy_version_id=uuid4(),
        policy=policy,
        version_number=1,
        thresholds={"nli_confidence_threshold": 0.75},
        action_rules={"contradiction_action": "REPAIR"},
    )
    async_session.add(app)
    await async_session.commit()

    # Query back with explicit async eager loading
    stmt = (
        select(Application)
        .where(Application.name == "Test Support App")
        .options(selectinload(Application.policies).selectinload(PolicyConfig.versions))
    )
    result = await async_session.execute(stmt)
    fetched_app = result.scalar_one()

    assert fetched_app is not None
    assert fetched_app.name == "Test Support App"
    assert len(fetched_app.policies) == 1
    assert fetched_app.policies[0].policy_name == "Standard Support Policy"
    assert len(fetched_app.policies[0].versions) == 1
    assert fetched_app.policies[0].versions[0].version_number == 1


@pytest.mark.asyncio
async def test_request_response_lifecycle(async_session: AsyncSession):
    """Test request and response creation with attempt numbering."""
    app = Application(
        application_id=uuid4(),
        name="Test App",
        application_type="DECISION_SUPPORT",
    )
    model = AIModel(
        model_id=uuid4(),
        provider="mock",
        model_name="mock-model",
    )
    async_session.add_all([app, model])
    await async_session.flush()

    req = Request(
        request_id=uuid4(),
        application_id=app.application_id,
        model_id=model.model_id,
        prompt="Is the policy active?",
        mode="REALTIME",
        status="PROCESSING",
    )
    resp = Response(
        response_id=uuid4(),
        request=req,
        attempt_number=0,
        content="The policy is active until December.",
        output_tokens=12,
        latency_ms=85,
    )
    async_session.add_all([req, resp])
    await async_session.commit()

    stmt = (
        select(Request)
        .where(Request.request_id == req.request_id)
        .options(selectinload(Request.responses))
    )
    fetched_req = (await async_session.execute(stmt)).scalar_one()
    assert len(fetched_req.responses) == 1
    assert fetched_req.responses[0].content == "The policy is active until December."


@pytest.mark.asyncio
async def test_claims_evidence_many_to_many(async_session: AsyncSession):
    """Test many-to-many relationship between claims and retrieved evidence."""
    app = Application(application_id=uuid4(), name="App", application_type="SUPPORT")
    req = Request(request_id=uuid4(), application_id=app.application_id, prompt="Test")
    resp = Response(response_id=uuid4(), request=req, content="Claim text")
    async_session.add_all([app, req, resp])
    await async_session.flush()

    claim = Claim(
        claim_id=uuid4(),
        response_id=resp.response_id,
        claim_index=0,
        claim_text="Return window is 30 days.",
    )
    ev1 = Evidence(
        evidence_id=uuid4(),
        source_type="KB",
        source_id="doc-returns-01",
        content_snippet="Standard return period is 30 days from purchase.",
        quality_score=0.95,
    )
    ev2 = Evidence(
        evidence_id=uuid4(),
        source_type="KB",
        source_id="doc-faq-02",
        content_snippet="Items can be returned within 30 days.",
        quality_score=0.88,
    )
    async_session.add_all([claim, ev1, ev2])
    await async_session.flush()

    link1 = ClaimEvidence(claim_id=claim.claim_id, evidence_id=ev1.evidence_id, relevance_score=0.96, rank=1)
    link2 = ClaimEvidence(claim_id=claim.claim_id, evidence_id=ev2.evidence_id, relevance_score=0.89, rank=2)
    async_session.add_all([link1, link2])
    await async_session.commit()

    stmt = (
        select(Claim)
        .where(Claim.claim_id == claim.claim_id)
        .options(selectinload(Claim.claim_evidence_links))
    )
    fetched_claim = (await async_session.execute(stmt)).scalar_one()
    assert len(fetched_claim.claim_evidence_links) == 2


@pytest.mark.asyncio
async def test_interventions_and_repair_attempts(async_session: AsyncSession):
    """Test intervention and repair attempt persistence."""
    app = Application(application_id=uuid4(), name="App", application_type="SUPPORT")
    req = Request(request_id=uuid4(), application_id=app.application_id, prompt="Test")
    resp = Response(response_id=uuid4(), request=req, content="Incorrect answer")
    async_session.add_all([app, req, resp])
    await async_session.flush()

    claim = Claim(claim_id=uuid4(), response_id=resp.response_id, claim_index=0, claim_text="Incorrect fact")
    intervention = Intervention(
        intervention_id=uuid4(),
        request_id=req.request_id,
        response_id=resp.response_id,
        action="REPAIR",
        trigger_type="CONTRADICTED_CLAIM",
        trigger_reason="Claim contradicts evidence snippet",
    )
    repair = RepairAttempt(
        repair_id=uuid4(),
        request_id=req.request_id,
        source_response_id=resp.response_id,
        attempt_number=1,
        failed_claim_id=claim.claim_id,
        repair_prompt="Please regenerate correcting the return window.",
        outcome="SUCCESS",
    )
    audit = AuditEvent(
        event_id=uuid4(),
        request_id=req.request_id,
        response_id=resp.response_id,
        event_type="INTERVENTION_TRIGGERED",
        component="ActionEngine",
        event_data={"action": "REPAIR", "failed_claims": 1},
    )
    async_session.add_all([claim, intervention, repair, audit])
    await async_session.commit()

    # Query back
    stmt = select(Intervention).where(Intervention.request_id == req.request_id)
    fetched_interv = (await async_session.execute(stmt)).scalar_one()
    assert fetched_interv.action == "REPAIR"

    stmt_audit = select(AuditEvent).where(AuditEvent.request_id == req.request_id)
    fetched_audit = (await async_session.execute(stmt_audit)).scalar_one()
    assert fetched_audit.event_type == "INTERVENTION_TRIGGERED"


@pytest.mark.asyncio
async def test_seed_database_execution(async_session: AsyncSession):
    """Verify standard seed data loads applications and policy versions."""
    await seed_database_async(async_session)

    stmt = select(Application)
    apps = (await async_session.execute(stmt)).scalars().all()
    assert len(apps) == 3

    app_types = {a.application_type for a in apps}
    assert app_types == {"CUSTOMER_SUPPORT", "INTERNAL_KNOWLEDGE", "DECISION_SUPPORT"}
