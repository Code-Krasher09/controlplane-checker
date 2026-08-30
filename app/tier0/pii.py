"""Deterministic Tier 0 PII and Secrets detector."""

import re
from typing import List
from app.domain.models import ActionType, PolicyEventItem, SeverityLevel

# Regular expressions for common identifiers and secrets
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SECRET_PATTERN = re.compile(
    r"(?i)\b(?:sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|bearer\s+[a-zA-Z0-9_\-\.]{20,}|api[_-]?key[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?)\b"
)


class PIIDetector:
    """Detects sensitive personal data and secrets in text."""

    def scan(self, text: str) -> List[PolicyEventItem]:
        """Scan text for PII and secrets, returning policy events."""
        events: List[PolicyEventItem] = []
        if not text:
            return events

        # 1. SSN Check (CRITICAL)
        for match in SSN_PATTERN.finditer(text):
            events.append(
                PolicyEventItem(
                    event_type="PII",
                    detector="Tier0_PII_SSN",
                    severity=SeverityLevel.CRITICAL,
                    confidence=0.99,
                    matched_text=match.group(0),
                    metadata={"pii_type": "SSN"},
                    action_taken=ActionType.BLOCK,
                )
            )

        # 2. Secret Key Check (CRITICAL)
        for match in SECRET_PATTERN.finditer(text):
            events.append(
                PolicyEventItem(
                    event_type="SECRET",
                    detector="Tier0_Secret_Detector",
                    severity=SeverityLevel.CRITICAL,
                    confidence=0.98,
                    matched_text=match.group(0),
                    metadata={"secret_type": "API_KEY"},
                    action_taken=ActionType.BLOCK,
                )
            )

        # 3. Email Check (HIGH)
        for match in EMAIL_PATTERN.finditer(text):
            events.append(
                PolicyEventItem(
                    event_type="PII",
                    detector="Tier0_PII_Email",
                    severity=SeverityLevel.HIGH,
                    confidence=0.95,
                    matched_text=match.group(0),
                    metadata={"pii_type": "EMAIL"},
                    action_taken=ActionType.BLOCK,
                )
            )

        # 4. Phone Check (MEDIUM)
        for match in PHONE_PATTERN.finditer(text):
            events.append(
                PolicyEventItem(
                    event_type="PII",
                    detector="Tier0_PII_Phone",
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.90,
                    matched_text=match.group(0),
                    metadata={"pii_type": "PHONE"},
                    action_taken=ActionType.BLOCK,
                )
            )

        return events
