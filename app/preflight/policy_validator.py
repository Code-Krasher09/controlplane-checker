"""Policy Configuration and Threshold Validation."""

from typing import Any, Dict, List, Tuple
from app.domain.models import ActionType, RiskLevel


class PolicyValidator:
    """Validates policy thresholds, budgets, and action taxonomies before activation."""

    VALID_RISK_APPETITES = {"LOW", "MEDIUM", "HIGH"}
    VALID_ACTIONS = {a.value for a in ActionType}

    def validate_policy(
        self,
        risk_appetite: str,
        max_repair_attempts: int,
        max_request_cost: Optional[float] = None,
        thresholds: Optional[Dict[str, Any]] = None,
        action_rules: Optional[Dict[str, Any]] = None,
        action_precedence: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """Validate policy parameters, returning (is_valid, errors)."""
        errors: List[str] = []

        # 1. Risk Appetite Validation
        if risk_appetite.upper() not in self.VALID_RISK_APPETITES:
            errors.append(f"Invalid risk appetite '{risk_appetite}'. Must be one of {self.VALID_RISK_APPETITES}")

        # 2. Repair Attempts Validation
        if max_repair_attempts < 0:
            errors.append(f"max_repair_attempts cannot be negative: {max_repair_attempts}")

        # 3. Cost Budget Validation
        if max_request_cost is not None and max_request_cost < 0:
            errors.append(f"max_request_cost cannot be negative: {max_request_cost}")

        # 4. Thresholds Validation
        thresh = thresholds or {}
        for key in ["nli_confidence_threshold", "adjudication_confidence_threshold", "min_evidence_quality"]:
            if key in thresh:
                val = float(thresh[key])
                if not (0.0 <= val <= 1.0):
                    errors.append(f"Threshold '{key}' must be between 0.0 and 1.0 (got {val})")

        if "adjudication_budget_usd" in thresh:
            val = float(thresh["adjudication_budget_usd"])
            if val < 0:
                errors.append(f"adjudication_budget_usd cannot be negative: {val}")

        # 5. Action Precedence Validation
        if action_precedence:
            for act in action_precedence:
                if act.upper() not in self.VALID_ACTIONS:
                    errors.append(f"Invalid action in action_precedence: '{act}'. Valid actions: {self.VALID_ACTIONS}")

        # 6. Action Rules Validation
        if action_rules:
            for rule_name, act in action_rules.items():
                if isinstance(act, str) and act.upper() not in self.VALID_ACTIONS:
                    errors.append(f"Invalid action in rule '{rule_name}': '{act}'. Valid actions: {self.VALID_ACTIONS}")

        return (len(errors) == 0, errors)
