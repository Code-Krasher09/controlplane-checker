"""Repair Planner and bounded regeneration service."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.domain.models import ClaimVerificationItem, EvidenceSnippet
from app.persistence.models import PolicyConfig


class RepairPlan(BaseModel):
    """Structured plan for targeted response regeneration."""
    attempt_number: int
    max_attempts: int
    repair_prompt: str
    failed_claims: List[ClaimVerificationItem] = Field(default_factory=list)
    evidence: List[EvidenceSnippet] = Field(default_factory=list)


class RepairPlanner:
    """Generates structured evidence-constrained instructions for model repair."""

    def plan_repair(
        self,
        failed_claims: List[ClaimVerificationItem],
        evidence: List[EvidenceSnippet],
        previous_response: str,
        attempt_number: int,
        policy_config: PolicyConfig,
    ) -> RepairPlan:
        """Create a targeted repair plan."""
        max_attempts = int(policy_config.max_repair_attempts or 2)

        # Collect failed claim statements
        failed_texts = [f"- {c.claim_text}" for c in failed_claims]
        evidence_texts = [f"- [{e.source_id or 'DOC'}] {e.content_snippet}" for e in evidence]

        repair_prompt = (
            f"The previous response contained factual errors contradicted by authoritative enterprise documents:\n\n"
            f"Contradicted claim(s):\n" + "\n".join(failed_texts) + "\n\n"
            f"Authoritative evidence:\n" + "\n".join(evidence_texts) + "\n\n"
            f"Please regenerate the response strictly adhering to the authoritative evidence. "
            f"Do not include the contradicted claims."
        )

        return RepairPlan(
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            repair_prompt=repair_prompt,
            failed_claims=failed_claims,
            evidence=evidence,
        )


class RepairService:
    """Evaluates repair eligibility and tracks bounded attempts."""

    def __init__(self, planner: Optional[RepairPlanner] = None):
        self.planner = planner or RepairPlanner()

    def can_repair(self, policy_config: PolicyConfig, attempt_number: int) -> bool:
        """Check if policy permits further repair attempts."""
        max_attempts = int(policy_config.max_repair_attempts or 2)
        return attempt_number < max_attempts
