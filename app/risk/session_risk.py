"""Session Risk Accumulator and Dynamic Policy Tuning."""

from typing import Any, Dict, List, Optional, Tuple
from app.domain.models import (
    ActionType,
    ClaimVerificationItem,
    PolicyEventItem,
    SessionRiskTelemetry,
    SeverityLevel,
    VerificationStatus,
)
from app.persistence.redis import RuntimeStateStore


class SessionRiskTracker:
    """Tracks multi-turn risk scores in Redis and computes dynamic session risk levels."""

    DEFAULT_ELEVATED_THRESHOLD: float = 3.0
    DEFAULT_STRICT_THRESHOLD: float = 7.0

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "SAFE": 0.0,
        "WARNING": 1.0,
        "UNCERTAINTY": 1.0,
        "REPAIR": 2.0,
        "CONTRADICTION": 3.0,
        "POLICY_VIOLATION": 5.0,
        "CRITICAL_PII": 5.0,
    }

    def __init__(self, state_store: Optional[RuntimeStateStore] = None):
        self.state_store = state_store or RuntimeStateStore()

    def determine_level(self, score: float, policy_thresholds: Optional[Dict[str, Any]] = None) -> str:
        """Map cumulative session score to risk level."""
        thresholds = policy_thresholds or {}
        elevated_thresh = float(thresholds.get("session_risk_elevated_threshold", self.DEFAULT_ELEVATED_THRESHOLD))
        strict_thresh = float(thresholds.get("session_risk_strict_threshold", self.DEFAULT_STRICT_THRESHOLD))

        if score >= strict_thresh:
            return "STRICT"
        if score >= elevated_thresh:
            return "ELEVATED"
        return "NORMAL"

    async def get_session_telemetry(
        self,
        session_id: str,
        policy_thresholds: Optional[Dict[str, Any]] = None,
    ) -> SessionRiskTelemetry:
        """Fetch current session risk telemetry from Redis."""
        raw = await self.state_store.get_session_risk_state(session_id)
        score = float(raw.get("score", 0.0))
        level = self.determine_level(score, policy_thresholds)

        return SessionRiskTelemetry(
            session_id=session_id,
            prior_score=score,
            current_score=score,
            level=level,
            turn_count=int(raw.get("turn_count", 0)),
            violations_count=int(raw.get("violations_count", 0)),
            contradictions_count=int(raw.get("contradictions_count", 0)),
            repairs_count=int(raw.get("repairs_count", 0)),
            uncertainties_count=int(raw.get("uncertainties_count", 0)),
        )

    def compute_turn_delta(
        self,
        policy_events: List[PolicyEventItem],
        claims: List[ClaimVerificationItem],
        action: ActionType,
        policy_thresholds: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, Optional[str]]:
        """Calculate score delta and primary event category for the current turn."""
        thresholds = policy_thresholds or {}
        weights = thresholds.get("session_risk_weights", self.DEFAULT_WEIGHTS)

        # 1. Critical PII or Hard Violations
        if any(ev.severity == SeverityLevel.CRITICAL for ev in policy_events):
            return float(weights.get("CRITICAL_PII", 5.0)), "VIOLATION"

        if any(ev.event_type in ("PII", "SECRET", "POLICY_VIOLATION", "TOXICITY") for ev in policy_events):
            return float(weights.get("POLICY_VIOLATION", 5.0)), "VIOLATION"

        # 2. Contradicted Claims
        if any(c.final_label == "CONTRADICTED" for c in claims):
            if action == ActionType.REPAIR:
                return float(weights.get("REPAIR", 2.0)), "REPAIR"
            return float(weights.get("CONTRADICTION", 3.0)), "CONTRADICTION"

        # 3. Inconclusive Adjudication or Uncertainty
        if any(c.verification_status == VerificationStatus.ADJUDICATION_INCONCLUSIVE for c in claims):
            return float(weights.get("UNCERTAINTY", 1.0)), "UNCERTAINTY"

        # 4. Warnings / Abstentions
        if action in (ActionType.WARN, ActionType.ABSTAIN):
            return float(weights.get("WARNING", 1.0)), "WARNING"

        return float(weights.get("SAFE", 0.0)), None

    async def record_turn_outcome(
        self,
        session_id: str,
        prior_score: float,
        policy_events: List[PolicyEventItem],
        claims: List[ClaimVerificationItem],
        action: ActionType,
        policy_thresholds: Optional[Dict[str, Any]] = None,
    ) -> SessionRiskTelemetry:
        """Update Redis session accumulator with turn outcome and return updated telemetry."""
        delta, event_type = self.compute_turn_delta(policy_events, claims, action, policy_thresholds)
        raw = await self.state_store.update_session_risk_state(session_id, delta, event_type)
        new_score = float(raw.get("score", 0.0))
        level = self.determine_level(new_score, policy_thresholds)

        return SessionRiskTelemetry(
            session_id=session_id,
            prior_score=prior_score,
            current_score=new_score,
            level=level,
            turn_count=int(raw.get("turn_count", 1)),
            violations_count=int(raw.get("violations_count", 0)),
            contradictions_count=int(raw.get("contradictions_count", 0)),
            repairs_count=int(raw.get("repairs_count", 0)),
            uncertainties_count=int(raw.get("uncertainties_count", 0)),
        )
