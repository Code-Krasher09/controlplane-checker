"""Human Feedback Capture and Offline Policy Calibration Foundation."""

from typing import Any, Dict, List, Tuple
from app.persistence.models import PolicyVersion
from .models import CalibrationRecommendation, HumanFeedbackItem


class CalibrationAnalyzer:
    """Analyzes human reviewer overrides and generates calibration recommendations."""

    def analyze_feedback(
        self,
        feedback_items: List[HumanFeedbackItem],
        current_policy: Optional[PolicyVersion] = None,
    ) -> Tuple[Dict[str, Any], List[CalibrationRecommendation]]:
        """Analyze reviewer overrides and generate calibration recommendations."""
        total = len(feedback_items)
        if total == 0:
            return {"total_feedback": 0, "override_rate": 0.0}, []

        overrides = [f for f in feedback_items if f.is_override]
        override_rate = round(len(overrides) / total, 4)

        # False Positives: System intervened (BLOCK/ESCALATE/WARN), but human corrected to ALLOW
        false_positives = [
            f for f in overrides
            if f.system_action in ("BLOCK", "ESCALATE", "WARN") and f.correct_action == "ALLOW"
        ]

        # False Negatives: System allowed, but human corrected to BLOCK/ESCALATE/WARN
        false_negatives = [
            f for f in overrides
            if f.system_action == "ALLOW" and f.correct_action in ("BLOCK", "ESCALATE", "WARN")
        ]

        summary = {
            "total_feedback": total,
            "overrides_count": len(overrides),
            "override_rate": override_rate,
            "false_positives_count": len(false_positives),
            "false_negatives_count": len(false_negatives),
            "action_confusion": self._compute_action_confusion(feedback_items),
        }

        # Generate non-autonomous policy threshold recommendations
        recommendations: List[CalibrationRecommendation] = []
        thresholds = current_policy.thresholds if current_policy and current_policy.thresholds else {}

        # 1. Check if False Positives on Ambiguous Cases Warrant Lowering Adjudication Threshold
        if len(false_positives) > (total * 0.10):
            current_margin = thresholds.get("adjudication_top2_margin", 0.15)
            recommendations.append(CalibrationRecommendation(
                parameter="adjudication_top2_margin",
                current_value=current_margin,
                recommended_value=round(current_margin + 0.05, 2),
                rationale=f"Reviewer override rate ({override_rate*100:.1f}%) indicates excessive conservative escalations on borderline cases.",
                expected_impact="Expands selective adjudication window to resolve ambiguity without unnecessary escalation.",
            ))

        # 2. Check if False Negatives Warrant Stricter Verification
        if len(false_negatives) > 0:
            current_nli = thresholds.get("nli_confidence_threshold", 0.75)
            recommendations.append(CalibrationRecommendation(
                parameter="nli_confidence_threshold",
                current_value=current_nli,
                recommended_value=min(0.95, round(current_nli + 0.05, 2)),
                rationale=f"Detected {len(false_negatives)} unsafe passes where human reviewer required intervention.",
                expected_impact="Tightens verification confidence requirement, routing borderline claims to adjudication or escalation.",
            ))

        return summary, recommendations

    def _compute_action_confusion(self, feedback: List[HumanFeedbackItem]) -> Dict[str, Dict[str, int]]:
        """Matrix mapping system_action -> reviewer_action."""
        matrix: Dict[str, Dict[str, int]] = {}
        for item in feedback:
            matrix.setdefault(item.system_action, {})
            matrix[item.system_action][item.reviewer_action] = (
                matrix[item.system_action].get(item.reviewer_action, 0) + 1
            )
        return matrix
