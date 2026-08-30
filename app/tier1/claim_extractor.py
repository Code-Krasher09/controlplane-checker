"""Tier 1 Atomic Claim Extractor."""

import re
from typing import List
from uuid import uuid4
from app.domain.models import ClaimVerificationItem, SeverityLevel


class ClaimExtractor:
    """Extracts atomic factual claims from response text."""

    def extract_claims(self, text: str, default_severity: SeverityLevel = SeverityLevel.MEDIUM) -> List[ClaimVerificationItem]:
        """Split response into distinct atomic claims."""
        if not text:
            return []

        # Split sentences by period, exclamation, question mark, or newline
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        claims: List[ClaimVerificationItem] = []

        index = 0
        for s in raw_sentences:
            cleaned = s.strip()
            if len(cleaned) > 10:  # ignore trivial fragments
                claims.append(
                    ClaimVerificationItem(
                        claim_id=uuid4(),
                        claim_index=index,
                        claim_text=cleaned,
                        severity=default_severity,
                    )
                )
                index += 1

        if not claims and text.strip():
            claims.append(
                ClaimVerificationItem(
                    claim_id=uuid4(),
                    claim_index=0,
                    claim_text=text.strip(),
                    severity=default_severity,
                )
            )

        return claims
