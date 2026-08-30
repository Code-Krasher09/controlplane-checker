"""Seed data for standard application profiles, AI models, and policy versions."""

from typing import List
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from .models import (
    AIModel,
    Application,
    PolicyConfig,
    PolicyVersion,
)

# Deterministic Seed UUIDs for tests/traceability
CUSTOMER_SUPPORT_APP_ID = UUID("11111111-1111-1111-1111-111111111111")
INTERNAL_KB_APP_ID = UUID("22222222-2222-2222-2222-222222222222")
DECISION_SUPPORT_APP_ID = UUID("33333333-3333-3333-3333-333333333333")

MOCK_MODEL_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
GPT4O_MINI_MODEL_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def get_seed_models() -> List[AIModel]:
    """Generate default AI Model metadata."""
    return [
        AIModel(
            model_id=MOCK_MODEL_ID,
            provider="mock",
            model_name="mock-pipeline-model-v1",
            model_version="1.0",
            deployment_type="local",
        ),
        AIModel(
            model_id=GPT4O_MINI_MODEL_ID,
            provider="openai",
            model_name="gpt-4o-mini",
            model_version="2024-07-18",
            deployment_type="api",
        ),
    ]


def get_seed_applications() -> List[Application]:
    """Generate the 3 canonical application profiles and policy configurations."""
    # 1. Customer Support
    app_cs = Application(
        application_id=CUSTOMER_SUPPORT_APP_ID,
        name="Customer Support Assistant",
        description="E-commerce and support response assistant with balanced latency and safety.",
        application_type="CUSTOMER_SUPPORT",
        mode="REALTIME",
    )
    policy_cs = PolicyConfig(
        policy_id=uuid4(),
        application_id=CUSTOMER_SUPPORT_APP_ID,
        policy_name="Customer Support Default Policy",
        risk_appetite="MEDIUM",
        require_grounding=False,
        block_on_pii=True,
        block_on_policy_violation=True,
        max_repair_attempts=2,
        max_request_cost=0.05,
        max_latency_ms=200,
        allow_warn_abstain=True,
        action_precedence=["BLOCK", "ESCALATE", "REPAIR", "WARN", "ALLOW"],
    )
    version_cs = PolicyVersion(
        policy_version_id=UUID("11111111-0000-0000-0000-000000000001"),
        policy=policy_cs,
        version_number=1,
        geography="GLOBAL",
        industry="RETAIL",
        thresholds={
            "nli_confidence_threshold": 0.75,
            "adjudication_confidence_threshold": 0.80,
            "adjudication_budget_usd": 0.02,
            "adjudication_top2_margin": 0.15,
            "high_severity_nli_threshold": 0.85,
            "min_evidence_quality": 0.55,
            "session_risk_elevated_threshold": 3.0,
            "session_risk_strict_threshold": 7.0,
            "max_consecutive_uncertainties": 3,
        },
        action_rules={
            "bias_action": "WARN",
            "contradiction_action": "REPAIR",
            "insufficient_evidence_action": "WARN",
            "inconclusive_adjudication_action": "WARN",
        },
    )
    policy_cs.versions.append(version_cs)
    app_cs.policies.append(policy_cs)

    # 2. Internal Knowledge
    app_kb = Application(
        application_id=INTERNAL_KB_APP_ID,
        name="Internal Knowledge Engine",
        description="Enterprise HR, IT, and operational document retrieval assistant.",
        application_type="INTERNAL_KNOWLEDGE",
        mode="REALTIME",
    )
    policy_kb = PolicyConfig(
        policy_id=uuid4(),
        application_id=INTERNAL_KB_APP_ID,
        policy_name="Internal Knowledge Policy",
        risk_appetite="MEDIUM",
        require_grounding=True,
        block_on_pii=True,
        block_on_policy_violation=True,
        max_repair_attempts=2,
        max_request_cost=0.05,
        max_latency_ms=300,
        allow_warn_abstain=True,
        action_precedence=["BLOCK", "ESCALATE", "REPAIR", "WARN", "ALLOW"],
    )
    version_kb = PolicyVersion(
        policy_version_id=UUID("22222222-0000-0000-0000-000000000001"),
        policy=policy_kb,
        version_number=1,
        geography="GLOBAL",
        industry="ENTERPRISE",
        thresholds={
            "nli_confidence_threshold": 0.80,
            "adjudication_confidence_threshold": 0.85,
            "adjudication_budget_usd": 0.03,
            "adjudication_top2_margin": 0.15,
            "high_severity_nli_threshold": 0.85,
            "min_evidence_quality": 0.60,
            "session_risk_elevated_threshold": 3.0,
            "session_risk_strict_threshold": 6.0,
            "max_consecutive_uncertainties": 2,
        },
        action_rules={
            "bias_action": "ESCALATE",
            "contradiction_action": "REPAIR",
            "insufficient_evidence_action": "WARN",
            "inconclusive_adjudication_action": "WARN",
        },
    )
    policy_kb.versions.append(version_kb)
    app_kb.policies.append(policy_kb)

    # 3. Decision Support
    app_ds = Application(
        application_id=DECISION_SUPPORT_APP_ID,
        name="Decision Support System",
        description="High-consequence financial, underwriting, and compliance decisioning.",
        application_type="DECISION_SUPPORT",
        mode="REALTIME",
    )
    policy_ds = PolicyConfig(
        policy_id=uuid4(),
        application_id=DECISION_SUPPORT_APP_ID,
        policy_name="Decision Support Strict Policy",
        risk_appetite="LOW",
        require_grounding=True,
        block_on_pii=True,
        block_on_policy_violation=True,
        max_repair_attempts=1,
        max_request_cost=0.10,
        max_latency_ms=500,
        allow_warn_abstain=False,
        action_precedence=["BLOCK", "ESCALATE", "REPAIR", "WARN", "ALLOW"],
    )
    version_ds = PolicyVersion(
        policy_version_id=UUID("33333333-0000-0000-0000-000000000001"),
        policy=policy_ds,
        version_number=1,
        geography="GLOBAL",
        industry="FINANCIAL",
        thresholds={
            "nli_confidence_threshold": 0.85,
            "adjudication_confidence_threshold": 0.90,
            "adjudication_budget_usd": 0.05,
            "adjudication_top2_margin": 0.15,
            "high_severity_nli_threshold": 0.88,
            "min_evidence_quality": 0.65,
            "session_risk_elevated_threshold": 2.0,
            "session_risk_strict_threshold": 5.0,
            "max_consecutive_uncertainties": 1,
        },
        action_rules={
            "bias_action": "ESCALATE",
            "contradiction_action": "REPAIR",
            "insufficient_evidence_action": "ESCALATE",
            "inconclusive_adjudication_action": "ESCALATE",
        },
    )
    policy_ds.versions.append(version_ds)
    app_ds.policies.append(policy_ds)

    return [app_cs, app_kb, app_ds]


async def seed_database_async(session: AsyncSession) -> None:
    """Async seed loader checking idempotency."""
    # Check if models already exist
    stmt_model = select(AIModel).where(AIModel.model_id == MOCK_MODEL_ID)
    res_model = await session.execute(stmt_model)
    if res_model.scalar_one_or_none() is None:
        for model in get_seed_models():
            session.add(model)

    # Check if applications already exist
    stmt_app = select(Application).where(Application.application_id == CUSTOMER_SUPPORT_APP_ID)
    res_app = await session.execute(stmt_app)
    if res_app.scalar_one_or_none() is None:
        for app in get_seed_applications():
            session.add(app)

    await session.commit()


def seed_database_sync(session: Session) -> None:
    """Synchronous seed loader for CLI/migrations."""
    stmt_model = select(AIModel).where(AIModel.model_id == MOCK_MODEL_ID)
    if session.execute(stmt_model).scalar_one_or_none() is None:
        for model in get_seed_models():
            session.add(model)

    stmt_app = select(Application).where(Application.application_id == CUSTOMER_SUPPORT_APP_ID)
    if session.execute(stmt_app).scalar_one_or_none() is None:
        for app in get_seed_applications():
            session.add(app)

    session.commit()
