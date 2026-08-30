"""Heuristic Tier 0 Bias screen for protected-attribute and stereotype terms."""

import re
from typing import List
from app.domain.models import ActionType, PolicyEventItem, SeverityLevel

BIAS_STEREOTYPE_PATTERNS = [
    (
        re.compile(r"(?i)\b(?:older workers|elderly candidates|senior employees)\s+are\s+(?:generally\s+)?(?:unsuitable|slow|incompetent|incapable)\b"),
        "AGE_BIAS",
        SeverityLevel.MEDIUM,
        0.85,
    ),
    (
        re.compile(r"(?i)\b(?:women|females)\s+are\s+(?:less\s+qualified|incapable|unsuited)\s+for\s+(?:leadership|technical|executive)\b"),
        "GENDER_BIAS",
        SeverityLevel.HIGH,
        0.88,
    ),
    (
        re.compile(r"(?i)\b(?:certain races|foreigners|immigrants)\s+(?:always|never|cannot)\s+be\s+trusted\b"),
        "ETHNICITY_BIAS",
        SeverityLevel.HIGH,
        0.90,
    ),
]


class HeuristicBiasDetector:
    """Heuristic bias indicator matching demographic terms with negative stereotypical generalizations.

    NOTE: This is a risk routing signal for the prototype, NOT a certified fairness model.
    It does not directly auto-block low-confidence findings.
    """

    def scan(self, text: str) -> List[PolicyEventItem]:
        """Scan text for stereotypical associations against protected attributes."""
        events: List[PolicyEventItem] = []
        if not text:
            return events

        for pattern, category, severity, confidence in BIAS_STEREOTYPE_PATTERNS:
            match = pattern.search(text)
            if match:
                events.append(
                    PolicyEventItem(
                        event_type="BIAS",
                        detector="Tier0_Heuristic_Bias_Screen",
                        severity=severity,
                        confidence=confidence,
                        matched_text=match.group(0),
                        metadata={"bias_category": category, "is_heuristic": True},
                        action_taken=ActionType.WARN,  # Does not auto-block; routes to policy resolution
                    )
                )

        return events
