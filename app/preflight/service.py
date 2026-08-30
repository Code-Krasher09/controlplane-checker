"""Pre-flight Gate service for request eligibility and budget checks."""

from typing import List, Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.domain.models import ActionType, PreflightRequest, PreflightResponse
from app.persistence.models import Application, PolicyConfig, PolicyVersion


class PreflightService:
    """Evaluates request eligibility and budget constraints before model execution."""

    async def evaluate(
        self,
        request: PreflightRequest,
        db_session: AsyncSession,
    ) -> Tuple[PreflightResponse, Optional[Application], Optional[PolicyVersion]]:
        """Run pre-flight validation against application profile and policy version."""
        reasons: List[str] = []

        # 1. Resolve Application and Policy
        stmt = (
            select(Application)
            .where(Application.application_id == request.application_id)
            .options(selectinload(Application.policies).selectinload(PolicyConfig.versions))
        )
        res = await db_session.execute(stmt)
        app = res.scalar_one_or_none()

        if app is None:
            return (
                PreflightResponse(
                    request_id=uuid4(),
                    action=ActionType.BLOCK,
                    application_id=request.application_id,
                    mode=request.mode,
                    reasons=["APPLICATION_NOT_FOUND"],
                ),
                None,
                None,
            )

        # 2. Resolve Policy Config and Version
        if not app.policies:
            return (
                PreflightResponse(
                    request_id=uuid4(),
                    action=ActionType.BLOCK,
                    application_id=app.application_id,
                    mode=app.mode,
                    reasons=["NO_POLICY_CONFIGURED"],
                ),
                app,
                None,
            )

        policy = app.policies[0]
        policy_version: Optional[PolicyVersion] = None

        if request.policy_version_id:
            for v in policy.versions:
                if v.policy_version_id == request.policy_version_id:
                    policy_version = v
                    break
        if policy_version is None and policy.versions:
            policy_version = policy.versions[-1]  # active latest version

        # 3. Budget & Eligibility Checks
        # Estimated input tokens check
        input_tokens = request.estimated_input_tokens or (len(request.prompt) // 4)
        if input_tokens > 4000:
            reasons.append("PROMPT_TOKEN_LIMIT_EXCEEDED")
            return (
                PreflightResponse(
                    request_id=uuid4(),
                    action=ActionType.BLOCK,
                    application_id=app.application_id,
                    policy_version_id=policy_version.policy_version_id if policy_version else None,
                    mode=app.mode,
                    reasons=reasons,
                ),
                app,
                policy_version,
            )

        # Check request budget limits if configured
        if policy.max_request_cost is not None and policy.max_request_cost <= 0.0:
            reasons.append("POLICY_REQUEST_BUDGET_EXHAUSTED")
            return (
                PreflightResponse(
                    request_id=uuid4(),
                    action=ActionType.BLOCK,
                    application_id=app.application_id,
                    policy_version_id=policy_version.policy_version_id if policy_version else None,
                    mode=app.mode,
                    reasons=reasons,
                ),
                app,
                policy_version,
            )

        reasons.append("PREFLIGHT_PASSED")
        return (
            PreflightResponse(
                request_id=uuid4(),
                action=ActionType.ALLOW,
                application_id=app.application_id,
                policy_version_id=policy_version.policy_version_id if policy_version else None,
                mode=app.mode,
                allowed_model="mock-pipeline-model-v1",
                output_token_budget=500,
                cost_budget_usd=float(policy.max_request_cost) if policy.max_request_cost else 0.05,
                reasons=reasons,
            ),
            app,
            policy_version,
        )
