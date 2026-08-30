"""Selective Adjudication Service coordinating the Confidence Gate, Adjudicator, and Budget State."""

from typing import List, Optional, Tuple
from uuid import UUID
from app.domain.models import (
    AdjudicationTrigger,
    ClaimVerificationItem,
    EvidenceSnippet,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)
from app.persistence.models import PolicyConfig, PolicyVersion
from app.persistence.redis import RuntimeStateStore
from .adjudicator import Adjudicator, MockAdjudicator
from .gate import ConfidenceGate


class AdjudicationService:
    """Evaluates NLI ambiguity and selectively invokes secondary LLM adjudication within budget."""

    def __init__(
        self,
        gate: Optional[ConfidenceGate] = None,
        adjudicator: Optional[Adjudicator] = None,
        state_store: Optional[RuntimeStateStore] = None,
    ):
        self.gate = gate or ConfidenceGate()
        self.adjudicator = adjudicator or MockAdjudicator()
        self.state_store = state_store or RuntimeStateStore()

    async def evaluate_and_adjudicate(
        self,
        claim: ClaimVerificationItem,
        evidence: List[EvidenceSnippet],
        nli_result: VerifierResponse,
        policy_config: PolicyConfig,
        policy_version: Optional[PolicyVersion] = None,
        session_id: Optional[str] = None,
        request_id: Optional[UUID] = None,
        scenario: Optional[str] = None,
        force_adjudicate: bool = False,
        skip_adjudicate: bool = False,
    ) -> Tuple[ClaimVerificationItem, bool, float]:
        """Execute Confidence Gate and optional selective adjudication.

        Returns:
            Tuple of (updated_claim, was_adjudicator_invoked, estimated_cost_usd)
        """
        thresholds = policy_version.thresholds if policy_version and policy_version.thresholds else {}

        # 1. Run Confidence Gate
        gate_res = self.gate.evaluate(claim, evidence, thresholds)
        
        if skip_adjudicate:
            claim.adjudication_trigger = gate_res.trigger
            claim.uncertainty_reason = UncertaintyReason.NONE
            return claim, False, 0.0

        if not gate_res.adjudication_required and not force_adjudicate:
            # Clean direct NLI verification
            claim.adjudication_trigger = gate_res.trigger
            claim.uncertainty_reason = UncertaintyReason.NONE
            return claim, False, 0.0

        # Ambiguity detected -> record trigger
        claim.adjudication_trigger = gate_res.trigger if gate_res.trigger != AdjudicationTrigger.NONE else AdjudicationTrigger.NLI_LOW_CONFIDENCE

        # 2. Check Adjudication Budget
        key = session_id or str(request_id or "default")
        max_adj_cost = float(thresholds.get("adjudication_budget_usd", 0.02))
        current_consumed = await self.state_store.get_adjudication_budget(key)

        estimated_adj_cost = 0.005
        if (current_consumed + estimated_adj_cost) > (max_adj_cost + 1e-6):
            # ---------------------------------------------------------
            # INVARIANT I: Budget Exhaustion Exception
            # Preserve trigger, set DIRECT_NLI, and record ADJUDICATION_BUDGET_EXHAUSTED
            # ---------------------------------------------------------
            claim.verification_status = VerificationStatus.DIRECT_NLI
            claim.uncertainty_reason = UncertaintyReason.ADJUDICATION_BUDGET_EXHAUSTED
            claim.final_label = nli_result.label
            claim.adjudication_invoked = False
            return claim, False, 0.0

        # 3. Invoke Adjudicator
        adj_res = await self.adjudicator.adjudicate(
            claim=claim,
            evidence=evidence,
            nli_result=nli_result,
            policy_thresholds=thresholds,
            scenario=scenario,
        )

        # 4. Consume Budget
        await self.state_store.consume_adjudication_budget(key, adj_res.estimated_cost_usd)

        # 5. Populate Claim Outcome
        claim.verification_status = adj_res.verification_status
        claim.final_label = adj_res.final_label  # Must be None if ADJUDICATION_INCONCLUSIVE
        claim.adjudicator_model = adj_res.adjudicator_model
        claim.adjudicator_confidence = adj_res.adjudicator_confidence
        claim.uncertainty_reason = adj_res.uncertainty_reason
        claim.adjudication_invoked = True

        return claim, True, adj_res.estimated_cost_usd
