"""Deterministic Tier 0 Policy Violation and Toxicity screen."""

import re
from typing import List
from app.domain.models import ActionType, PolicyEventItem, SeverityLevel

TOXICITY_PATTERNS = [
    (re.compile(r"(?i)\b(?:hate|foolish|incompetent|stupid|idiot|garbage|worthless)\b"), SeverityLevel.MEDIUM, 0.85, "HARSH_LANGUAGE"),
    (re.compile(r"(?i)\b(?:kill|attack|destroy|harm|bomb|threaten)\b"), SeverityLevel.CRITICAL, 0.95, "THREAT_VIOLENCE"),
]

POLICY_PATTERNS = [
    (re.compile(r"(?i)\b(?:ignore all previous instructions|system prompt leak|jailbreak|disregard safety)\b"), SeverityLevel.HIGH, 0.90, "PROMPT_INJECTION"),
    (re.compile(r"(?i)\b(?:illegal|counterfeit|launder|unauthorized bypass)\b"), SeverityLevel.HIGH, 0.88, "COMPLIANCE_VIOLATION"),
]


class PolicyToxicityDetector:
    """Screen for explicit policy violations and hostile language."""

    def scan(self, text: str) -> List[PolicyEventItem]:
        """Scan text for toxic or policy-violating language."""
        events: List[PolicyEventItem] = []
        if not text:
            return events

        # Toxicity Checks
        for pattern, severity, confidence, category in TOXICITY_PATTERNS:
            match = pattern.search(text)
            if match:
                events.append(
                    PolicyEventItem(
                        event_type="TOXICITY",
                        detector="Tier0_Toxicity_Screen",
                        severity=severity,
                        confidence=confidence,
                        matched_text=match.group(0),
                        metadata={"category": category},
                        action_taken=ActionType.BLOCK if severity == SeverityLevel.CRITICAL else ActionType.WARN,
                    )
                )

        # Policy Compliance Checks
        for pattern, severity, confidence, category in POLICY_PATTERNS:
            match = pattern.search(text)
            if match:
                events.append(
                    PolicyEventItem(
                        event_type="POLICY_VIOLATION",
                        detector="Tier0_Policy_Rule_Screen",
                        severity=severity,
                        confidence=confidence,
                        matched_text=match.group(0),
                        metadata={"category": category},
                        action_taken=ActionType.BLOCK if severity == SeverityLevel.CRITICAL else ActionType.ESCALATE,
                    )
                )

        return events
