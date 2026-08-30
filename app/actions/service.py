"""Action Engine service for resolving interventions and enforcing policy precedence."""

from typing import List, Optional
from app.domain.models import (
    ActionType,
    ClaimVerificationItem,
    PolicyEventItem,
    RiskAssessmentResult,
    SeverityLevel,
    UncertaintyReason,
    VerificationStatus,
)
from app.persistence.models import PolicyConfig, PolicyVersion


class ActionEngine:
    """Resolves the final safety intervention across Tier 0 events, risk, claims, and policy."""

    PRECEDENCE_ORDER = [
        ActionType.BLOCK,
        ActionType.ESCALATE,
        ActionType.REPAIR,
        ActionType.WARN,
        ActionType.ABSTAIN,
        ActionType.ALLOW,
    ]

    def resolve(
        self,
        risk_assessment: RiskAssessmentResult,
        policy_config: PolicyConfig,
        policy_version: Optional[PolicyVersion] = None,
        policy_events: Optional[List[PolicyEventItem]] = None,
        claims: Optional[List[ClaimVerificationItem]] = None,
        current_repair_attempt: int = 0,
    ) -> ActionType:
        """Resolve final action applying strict precedence and repair bounds."""
        candidate_actions: List[ActionType] = []
        events = policy_events or []
        claim_items = claims or []

        # -------------------------------------------------------------
        # 1. Evaluate Tier 0 Policy Events
        # -------------------------------------------------------------
        for ev in events:
            if ev.severity == SeverityLevel.CRITICAL:
                return ActionType.BLOCK  # Immediate hard block on critical PII/secrets/threats

            if ev.event_type in ("PII", "SECRET") and policy_config.block_on_pii:
                candidate_actions.append(ActionType.BLOCK)
            elif ev.event_type == "POLICY_VIOLATION" and policy_config.block_on_policy_violation:
                candidate_actions.append(ActionType.BLOCK if ev.severity == SeverityLevel.HIGH else ActionType.ESCALATE)
            elif ev.event_type == "BIAS":
                bias_action_str = "WARN"
                if policy_version and policy_version.action_rules:
                    bias_action_str = policy_version.action_rules.get("bias_action", "WARN")
                candidate_actions.append(ActionType(bias_action_str.upper()))
            elif ev.action_taken:
                candidate_actions.append(ev.action_taken)

        # -------------------------------------------------------------
        # 2. Evaluate Tier 1 Claims & Adjudication States
        # -------------------------------------------------------------
        max_repairs = int(policy_config.max_repair_attempts or 2)
        can_repair = current_repair_attempt < max_repairs

        for claim in claim_items:
            # CASE A: Evidence Insufficiency
            if claim.verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE or claim.final_label == "INSUFFICIENT_EVIDENCE":
                if risk_assessment.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) or policy_config.risk_appetite == "LOW":
                    candidate_actions.append(ActionType.ESCALATE)
                else:
                    if policy_config.allow_warn_abstain:
                        candidate_actions.append(ActionType.WARN)
                    else:
                        candidate_actions.append(ActionType.ESCALATE)

            # CASE B: Contradicted Claim (Eligible for Repair or Escalation)
            elif claim.final_label == "CONTRADICTED":
                if can_repair:
                    candidate_actions.append(ActionType.REPAIR)
                else:
                    candidate_actions.append(ActionType.ESCALATE)

            # CASE C: Adjudication Inconclusive (Judge Ambiguity)
            elif claim.verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE:
                if risk_assessment.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) or policy_config.risk_appetite == "LOW":
                    candidate_actions.append(ActionType.ESCALATE)
                else:
                    candidate_actions.append(ActionType.WARN)

            # CASE D: Adjudication Budget Exhausted on Ambiguous Claim
            elif claim.uncertainty_reason == UncertaintyReason.ADJUDICATION_BUDGET_EXHAUSTED:
                if risk_assessment.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) or policy_config.risk_appetite == "LOW":
                    candidate_actions.append(ActionType.ESCALATE)
                else:
                    candidate_actions.append(ActionType.WARN)

            # CASE E: Verified Supported Claim
            elif claim.final_label == "SUPPORTED":
                candidate_actions.append(ActionType.ALLOW)

            # CASE F: Any Unverified / Unresolved Semantic State
            else:
                if risk_assessment.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) or policy_config.risk_appetite == "LOW":
                    candidate_actions.append(ActionType.ESCALATE)
                else:
                    candidate_actions.append(ActionType.WARN)

        # -------------------------------------------------------------
        # 3. Default fallback if no claims or events
        # -------------------------------------------------------------
        if not candidate_actions:
            if (risk_assessment.verification_required and not claim_items) or risk_assessment.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL):
                candidate_actions.append(ActionType.ESCALATE)
            else:
                candidate_actions.append(ActionType.ALLOW)

        # -------------------------------------------------------------
        # 4. Resolve using Strict Precedence Ordering
        # BLOCK > ESCALATE > REPAIR > WARN > ABSTAIN > ALLOW
        # -------------------------------------------------------------
        for action in self.PRECEDENCE_ORDER:
            if action in candidate_actions:
                return action

        return ActionType.ALLOW
