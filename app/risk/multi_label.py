"""Multi-Label Risk Aggregator and Overlapping Action Resolver."""

from typing import List, Optional, Tuple
from app.domain.models import (
    ActionType,
    ClaimVerificationItem,
    PolicyEventItem,
    RiskAssessmentResult,
    RiskLevel,
    SeverityLevel,
    VerificationStatus,
)
from app.persistence.models import PolicyConfig, PolicyVersion


class MultiLabelRiskAggregator:
    """Aggregates multiple simultaneous risk categories and resolves overlapping actions."""

    SEVERITY_HIERARCHY = {
        SeverityLevel.LOW: 1,
        SeverityLevel.MEDIUM: 2,
        SeverityLevel.HIGH: 3,
        SeverityLevel.CRITICAL: 4,
    }

    PRECEDENCE_ORDER = [
        ActionType.BLOCK,
        ActionType.ESCALATE,
        ActionType.REPAIR,
        ActionType.WARN,
        ActionType.ABSTAIN,
        ActionType.ALLOW,
    ]

    def aggregate_risks(
        self,
        policy_events: List[PolicyEventItem],
        claims: List[ClaimVerificationItem],
        base_risk_result: RiskAssessmentResult,
        policy_config: PolicyConfig,
        policy_version: Optional[PolicyVersion] = None,
        current_repair_attempt: int = 0,
    ) -> Tuple[List[str], SeverityLevel, List[ActionType], ActionType, str]:
        """Extract all co-occurring risk types, highest severity, candidate actions, and resolved action.

        Returns:
            Tuple of (risk_types, highest_severity, candidate_actions, resolved_action, precedence_reason)
        """
        detected_risk_types: set[str] = set()
        candidate_actions: List[ActionType] = []
        highest_sev = base_risk_result.severity

        # 1. Inspect Tier 0 Policy Events
        for ev in policy_events:
            detected_risk_types.add(ev.event_type)

            # Update highest severity
            if ev.severity and self.SEVERITY_HIERARCHY.get(ev.severity, 0) > self.SEVERITY_HIERARCHY.get(highest_sev, 0):
                highest_sev = ev.severity

            # Propose candidate action per event
            if ev.severity == SeverityLevel.CRITICAL:
                candidate_actions.append(ActionType.BLOCK)
            elif ev.event_type in ("PII", "SECRET") and policy_config.block_on_pii:
                candidate_actions.append(ActionType.BLOCK)
            elif ev.event_type == "POLICY_VIOLATION" and policy_config.block_on_policy_violation:
                candidate_actions.append(ActionType.BLOCK if ev.severity == SeverityLevel.HIGH else ActionType.ESCALATE)
            elif ev.event_type == "BIAS":
                bias_action = "WARN"
                if policy_version and policy_version.action_rules:
                    bias_action = policy_version.action_rules.get("bias_action", "WARN")
                candidate_actions.append(ActionType(bias_action.upper()))
            elif ev.action_taken:
                candidate_actions.append(ev.action_taken)

        # 2. Inspect Tier 1 Claims
        max_repairs = int(policy_config.max_repair_attempts or 2)
        can_repair = current_repair_attempt < max_repairs

        for claim in claims:
            if claim.severity and self.SEVERITY_HIERARCHY.get(claim.severity, 0) > self.SEVERITY_HIERARCHY.get(highest_sev, 0):
                highest_sev = claim.severity

            if claim.final_label == "CONTRADICTED":
                detected_risk_types.add("HALLUCINATION")
                if can_repair:
                    candidate_actions.append(ActionType.REPAIR)
                else:
                    candidate_actions.append(ActionType.ESCALATE)

            elif claim.verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE:
                detected_risk_types.add("UNGROUNDED")
                if highest_sev in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) or policy_config.risk_appetite == "LOW":
                    candidate_actions.append(ActionType.ESCALATE)
                else:
                    candidate_actions.append(ActionType.WARN if policy_config.allow_warn_abstain else ActionType.ESCALATE)

            elif claim.verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE:
                detected_risk_types.add("UNCERTAINTY")
                if highest_sev in (SeverityLevel.HIGH, SeverityLevel.CRITICAL) or policy_config.risk_appetite == "LOW":
                    candidate_actions.append(ActionType.ESCALATE)
                else:
                    candidate_actions.append(ActionType.WARN)

            elif claim.final_label == "SUPPORTED":
                candidate_actions.append(ActionType.ALLOW)

        if not candidate_actions:
            candidate_actions.append(ActionType.ALLOW)

        # 3. Resolve using Precedence
        resolved_action = ActionType.ALLOW
        precedence_reason = "DEFAULT_ALLOW"

        for action in self.PRECEDENCE_ORDER:
            if action in candidate_actions:
                resolved_action = action
                precedence_reason = f"Precedence resolved {action.value} over {[a.value for a in candidate_actions if a != action]}"
                break

        return sorted(list(detected_risk_types)), highest_sev, candidate_actions, resolved_action, precedence_reason
