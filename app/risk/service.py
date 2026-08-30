"""Risk and Severity Engine service with Multi-label support and Session Risk awareness."""

from typing import Any, Dict, List, Optional
from app.domain.models import (
    PolicyEventItem,
    RiskAssessmentResult,
    RiskLevel,
    SeverityLevel,
)
from app.persistence.models import PolicyConfig, PolicyVersion


class RiskEngine:
    """Evaluates task, response, policy, session, and Tier 0 signals to determine verification requirements."""

    SEVERITY_HIERARCHY = {
        SeverityLevel.LOW: 1,
        SeverityLevel.MEDIUM: 2,
        SeverityLevel.HIGH: 3,
        SeverityLevel.CRITICAL: 4,
    }

    def assess(
        self,
        prompt: str,
        response: str,
        policy_config: PolicyConfig,
        policy_version: Optional[PolicyVersion] = None,
        policy_events: Optional[List[PolicyEventItem]] = None,
        semantic_consistency_score: float = 0.85,
        task_signals: Optional[Dict[str, Any]] = None,
        response_signals: Optional[Dict[str, Any]] = None,
        evidence_availability: Optional[Dict[str, Any]] = None,
        session_state: Optional[Dict[str, Any]] = None,
        cost_state: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessmentResult:
        """Compute multidimensional multi-label risk score and Tier 1 routing decision."""
        events = policy_events or []
        task_sig = task_signals or {}
        session_data = session_state or {}
        reasons: List[str] = []

        # Identify all detected Tier 0 risk types
        risk_types = sorted(list({ev.event_type for ev in events}))

        # 1. Tier 0 Critical Violations
        critical_events = [e for e in events if e.severity == SeverityLevel.CRITICAL]
        high_events = [e for e in events if e.severity == SeverityLevel.HIGH]

        if critical_events:
            for ev in critical_events:
                reasons.append(f"TIER0_{ev.event_type}_CRITICAL")
            return RiskAssessmentResult(
                task_risk_score=0.9,
                response_risk_score=1.0,
                evidence_availability_score=1.0,
                sensitivity_score=1.0,
                severity_score=1.0,
                session_risk_score=float(session_data.get("score", 0.0)),
                final_risk_score=1.0,
                risk_level=RiskLevel.CRITICAL,
                severity=SeverityLevel.CRITICAL,
                highest_severity=SeverityLevel.CRITICAL,
                verification_required=False,  # Hard block does not need Tier 1
                risk_types=risk_types,
                reasons=reasons,
            )

        # 2. Session Risk Incorporation
        session_score = float(session_data.get("score", 0.0))
        session_level = session_data.get("level", "NORMAL")

        task_risk = 0.2
        if session_level == "STRICT":
            task_risk += 0.45
            reasons.append("SESSION_RISK_STRICT_MANDATORY_GROUNDING")
        elif session_level == "ELEVATED":
            task_risk += 0.25
            reasons.append("SESSION_RISK_ELEVATED")

        # 3. Task Risk Scoring
        domain = str(task_sig.get("domain", "")).upper()
        prompt_upper = prompt.upper()

        if policy_config.risk_appetite == "LOW" or policy_config.require_grounding:
            task_risk += 0.4
            reasons.append("POLICY_STRICT_GROUNDING_REQUIRED")

        if any(kw in prompt_upper or kw in domain for kw in ["FINANCIAL", "REFUND", "WAIVER", "LEGAL", "COMPLIANCE", "BENEFIT", "LIABILITY", "WARRANTY"]):
            task_risk += 0.35
            reasons.append("HIGH_CONSEQUENCE_DOMAIN")

        task_risk = min(1.0, task_risk)

        # 4. Response Risk Scoring
        # Claim density + low semantic consistency signal
        response_risk = 0.2
        if high_events:
            response_risk += 0.35
            for ev in high_events:
                reasons.append(f"TIER0_{ev.event_type}_EVENT")

        if semantic_consistency_score < 0.60:
            response_risk += 0.3
            reasons.append("LOW_SEMANTIC_CONSISTENCY_SIGNAL")
        elif semantic_consistency_score > 0.85:
            response_risk -= 0.1

        if any(kw in response.upper() for kw in ["ALLOW", "ENTITLED", "GUARANTEE", "WAIVER", "COVERED", "RETURN", "POLICY"]):
            response_risk += 0.25

        response_risk = max(0.0, min(1.0, response_risk))

        # 5. Severity Scoring (Consequence of Error)
        severity_score = 0.3
        if policy_config.risk_appetite == "LOW":
            severity_score += 0.4
        if "HIGH_CONSEQUENCE_DOMAIN" in reasons or "POLICY_STRICT_GROUNDING_REQUIRED" in reasons:
            severity_score += 0.3
        if session_level == "STRICT":
            severity_score += 0.3

        severity_score = min(1.0, severity_score)
        if severity_score >= 0.75:
            severity = SeverityLevel.HIGH
        elif severity_score >= 0.45:
            severity = SeverityLevel.MEDIUM
        else:
            severity = SeverityLevel.LOW

        highest_sev = severity
        for ev in events:
            if ev.severity and self.SEVERITY_HIERARCHY.get(ev.severity, 0) > self.SEVERITY_HIERARCHY.get(highest_sev, 0):
                highest_sev = ev.severity

        # 6. Final Risk Calculation
        final_risk = (0.45 * task_risk) + (0.25 * response_risk) + (0.25 * severity_score) + (0.05 * min(1.0, session_score / 10.0))

        if final_risk >= 0.70:
            risk_level = RiskLevel.HIGH
        elif final_risk >= 0.40:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # 7. Verification Routing Decision
        if policy_config.require_grounding or session_level == "STRICT":
            verification_required = True
            if "POLICY_STRICT_GROUNDING_REQUIRED" not in reasons and "SESSION_RISK_STRICT_MANDATORY_GROUNDING" not in reasons:
                reasons.append("GROUNDING_MANDATORY")
        elif risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) or (
            risk_level == RiskLevel.MEDIUM and ("HIGH_CONSEQUENCE_DOMAIN" in reasons or session_level == "ELEVATED")
        ):
            verification_required = True
            reasons.append("HIGH_RISK_VERIFICATION_TRIGGERED")
        else:
            verification_required = False
            reasons.append("SAFE_FAST_PATH_ALLOWED")

        return RiskAssessmentResult(
            task_risk_score=round(task_risk, 4),
            response_risk_score=round(response_risk, 4),
            evidence_availability_score=1.0,
            sensitivity_score=round(severity_score, 4),
            severity_score=round(severity_score, 4),
            session_risk_score=round(session_score, 4),
            final_risk_score=round(final_risk, 4),
            risk_level=risk_level,
            severity=severity,
            highest_severity=highest_sev,
            verification_required=verification_required,
            risk_types=risk_types,
            reasons=reasons,
        )
