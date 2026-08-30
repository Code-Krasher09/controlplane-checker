"""Initial P0 MVP database schema.

Revision ID: 0001_initial_p0_schema
Revises: 
Create Date: 2026-08-30

This migration creates the minimal P0 database schema for the ControlPlane
Round 2 prototype:
- applications
- ai_models
- policy_configs
- policy_versions
- requests
- responses
- policy_events
- risk_assessments
- claims
- evidence
- claim_evidence
- nli_results (with V1.2 check constraints)
- interventions
- repair_attempts
- audit_events

Deferred target tables:
- human_feedback
- session_risk
- evaluation_cases
- evaluation_runs
- evaluation_case_results
- agent_action_gates
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "0001_initial_p0_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Applications
    op.create_table(
        "applications",
        sa.Column("application_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("application_type", sa.String(60), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False, server_default="REALTIME"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. AI Models
    op.create_table(
        "ai_models",
        sa.Column("model_id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(150), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("deployment_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. Policy Configs
    op.create_table(
        "policy_configs",
        sa.Column("policy_id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.application_id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_name", sa.String(150), nullable=False),
        sa.Column("risk_appetite", sa.String(30), nullable=False),
        sa.Column("require_grounding", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("block_on_pii", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("block_on_policy_violation", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_repair_attempts", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("max_request_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("max_latency_ms", sa.Integer(), nullable=True),
        sa.Column("allow_warn_abstain", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("action_precedence", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 4. Policy Versions
    op.create_table(
        "policy_versions",
        sa.Column("policy_version_id", sa.String(36), primary_key=True),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policy_configs.policy_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("geography", sa.String(80), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("thresholds", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("action_rules", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("policy_id", "version_number", name="uq_policy_version"),
    )

    # 5. Requests
    op.create_table(
        "requests",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.application_id"), nullable=False),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("ai_models.model_id"), nullable=True),
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("policy_versions.policy_version_id"), nullable=True),
        sa.Column("session_id", sa.String(150), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("request_type", sa.String(100), nullable=True),
        sa.Column("domain", sa.String(100), nullable=True),
        sa.Column("mode", sa.String(30), nullable=False, server_default="REALTIME"),
        sa.Column("status", sa.String(30), nullable=False, server_default="PROCESSING"),
        sa.Column("preflight_action", sa.String(30), nullable=True),
        sa.Column("preflight_model_budget", sa.Numeric(12, 6), nullable=True),
        sa.Column("preflight_output_token_budget", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_requests_session", "requests", ["session_id"])
    op.create_index("idx_requests_status", "requests", ["status"])

    # 6. Responses
    op.create_table(
        "responses",
        sa.Column("response_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("generated_by_model", sa.String(36), sa.ForeignKey("ai_models.model_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_responses_request", "responses", ["request_id"])

    # 7. Policy Events
    op.create_table(
        "policy_events",
        sa.Column("policy_event_id", sa.String(36), primary_key=True),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("responses.response_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("detector", sa.String(100), nullable=True),
        sa.Column("severity", sa.String(30), nullable=True),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("action_taken", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 8. Risk Assessments
    op.create_table(
        "risk_assessments",
        sa.Column("risk_assessment_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("responses.response_id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_risk_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("response_risk_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("evidence_availability_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("sensitivity_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("severity_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("session_risk_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("cost_state_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("final_risk_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("risk_level", sa.String(30), nullable=False),
        sa.Column("verification_required", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 9. Claims
    op.create_table(
        "claims",
        sa.Column("claim_id", sa.String(36), primary_key=True),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("responses.response_id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_index", sa.Integer(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(30), nullable=True),
        sa.Column("business_impact", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_claims_response", "claims", ["response_id"])

    # 10. Evidence
    op.create_table(
        "evidence",
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=True),
        sa.Column("document_version", sa.String(100), nullable=True),
        sa.Column("chunk_id", sa.String(200), nullable=True),
        sa.Column("source_authority", sa.String(50), nullable=True),
        sa.Column("freshness_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relevance_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("completeness_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("quality_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("content_snippet", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 11. Claim Evidence Association
    op.create_table(
        "claim_evidence",
        sa.Column("claim_id", sa.String(36), sa.ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidence.evidence_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relevance_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
    )

    # 12. NLI Results (with V1.2 check constraints)
    op.create_table(
        "nli_results",
        sa.Column("nli_result_id", sa.String(36), primary_key=True),
        sa.Column("claim_id", sa.String(36), sa.ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidence.evidence_id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_name", sa.String(150), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("entailment_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("contradiction_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("neutral_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("inference_latency_ms", sa.Integer(), nullable=True),
        sa.Column("nli_confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("verification_status", sa.String(40), nullable=False, server_default="DIRECT_NLI"),
        sa.Column("adjudication_trigger", sa.String(60), nullable=False, server_default="NONE"),
        sa.Column("uncertainty_reason", sa.String(60), nullable=False, server_default="NONE"),
        sa.Column("adjudicator_model", sa.String(150), nullable=True),
        sa.Column("adjudicator_confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("final_label", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "verification_status IN ('DIRECT_NLI','ADJUDICATED','ADJUDICATION_INCONCLUSIVE')",
            name="chk_nli_verification_status",
        ),
        sa.CheckConstraint(
            "adjudication_trigger IN ('NONE','NLI_LOW_CONFIDENCE','NLI_CLOSE_TOP2','NLI_EVIDENCE_LABEL_CONFLICT','HIGH_SEVERITY_MARGINAL_NLI')",
            name="chk_nli_adjudication_trigger",
        ),
        sa.CheckConstraint(
            "uncertainty_reason IN ('NONE','NLI_LOW_CONFIDENCE','NLI_CLOSE_TOP2','NLI_EVIDENCE_LABEL_CONFLICT','HIGH_SEVERITY_MARGINAL_NLI','JUDGE_LOW_CONFIDENCE','ADJUDICATION_BUDGET_EXHAUSTED')",
            name="chk_nli_uncertainty_reason",
        ),
        sa.CheckConstraint(
            "verification_status <> 'ADJUDICATION_INCONCLUSIVE' OR final_label IS NULL",
            name="chk_nli_inconclusive_requires_null_label",
        ),
        sa.CheckConstraint(
            "verification_status <> 'DIRECT_NLI' OR final_label IS NOT NULL OR uncertainty_reason = 'ADJUDICATION_BUDGET_EXHAUSTED'",
            name="chk_nli_direct_requires_final_label",
        ),
        sa.CheckConstraint(
            "("
            "(adjudication_trigger = 'NONE' AND verification_status = 'DIRECT_NLI' AND uncertainty_reason = 'NONE') OR "
            "(adjudication_trigger <> 'NONE' AND verification_status IN ('ADJUDICATED','ADJUDICATION_INCONCLUSIVE')) OR "
            "(adjudication_trigger <> 'NONE' AND verification_status = 'DIRECT_NLI' AND uncertainty_reason = 'ADJUDICATION_BUDGET_EXHAUSTED')"
            ")",
            name="chk_nli_trigger_status_consistency",
        ),
    )
    op.create_index("idx_nli_claim", "nli_results", ["claim_id"])
    op.create_index("idx_nli_verification_status", "nli_results", ["verification_status"])
    op.create_index("idx_nli_adjudication_trigger", "nli_results", ["adjudication_trigger"])

    # 13. Interventions
    op.create_table(
        "interventions",
        sa.Column("intervention_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("responses.response_id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("trigger_type", sa.String(60), nullable=True),
        sa.Column("trigger_reason", sa.Text(), nullable=True),
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("policy_versions.policy_version_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_interventions_request", "interventions", ["request_id"])

    # 14. Repair Attempts
    op.create_table(
        "repair_attempts",
        sa.Column("repair_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_response_id", sa.String(36), sa.ForeignKey("responses.response_id", ondelete="SET NULL"), nullable=True),
        sa.Column("repaired_response_id", sa.String(36), sa.ForeignKey("responses.response_id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("failed_claim_id", sa.String(36), sa.ForeignKey("claims.claim_id", ondelete="SET NULL"), nullable=True),
        sa.Column("repair_prompt", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 15. Audit Events
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=True),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("responses.response_id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("component", sa.String(100), nullable=True),
        sa.Column("event_data", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_audit_request", "audit_events", ["request_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("repair_attempts")
    op.drop_table("interventions")
    op.drop_table("nli_results")
    op.drop_table("claim_evidence")
    op.drop_table("evidence")
    op.drop_table("claims")
    op.drop_table("risk_assessments")
    op.drop_table("policy_events")
    op.drop_table("responses")
    op.drop_table("requests")
    op.drop_table("policy_versions")
    op.drop_table("policy_configs")
    op.drop_table("ai_models")
    op.drop_table("applications")
