"""Provider-neutral Selective Adjudicator interface and implementations."""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.domain.models import (
    AdjudicationResponse,
    ClaimVerificationItem,
    EvidenceSnippet,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)


class Adjudicator(ABC):
    """Abstract interface for secondary LLM adjudication judges."""

    @abstractmethod
    async def adjudicate(
        self,
        claim: ClaimVerificationItem,
        evidence: List[EvidenceSnippet],
        nli_result: VerifierResponse,
        policy_thresholds: Optional[Dict[str, Any]] = None,
        scenario: Optional[str] = None,
    ) -> AdjudicationResponse:
        """Adjudicate ambiguous NLI claim against the same evidence context."""
        pass


class MockAdjudicator(Adjudicator):
    """Deterministic Mock Adjudicator for local testing and benchmark execution."""

    DEFAULT_ADJUDICATOR_CONFIDENCE_THRESHOLD: float = 0.80

    def __init__(self, model_name: str = "mock-judge-v1"):
        self.model_name = model_name

    async def adjudicate(
        self,
        claim: ClaimVerificationItem,
        evidence: List[EvidenceSnippet],
        nli_result: VerifierResponse,
        policy_thresholds: Optional[Dict[str, Any]] = None,
        scenario: Optional[str] = None,
    ) -> AdjudicationResponse:
        """Execute deterministic adjudication evaluation."""
        thresholds = policy_thresholds or {}
        min_judge_conf = float(thresholds.get("judge_confidence_threshold", self.DEFAULT_ADJUDICATOR_CONFIDENCE_THRESHOLD))

        selected_scenario = (scenario or "").upper()
        claim_upper = claim.claim_text.upper()

        # Check explicit scenario or keyword heuristics
        if selected_scenario == "INCONCLUSIVE" or "INCONCLUSIVE" in claim_upper or "EXCEPTION" in claim_upper:
            # Judge cannot reach high confidence
            return AdjudicationResponse(
                verification_status=VerificationStatus.ADJUDICATION_INCONCLUSIVE,
                final_label=None,  # Invariant: final_label MUST be None when inconclusive
                adjudicator_model=self.model_name,
                adjudicator_confidence=0.48,
                uncertainty_reason=UncertaintyReason.JUDGE_LOW_CONFIDENCE,
                adjudication_invoked=True,
                estimated_cost_usd=0.005,
            )

        if selected_scenario == "CONFIDENT_CONTRADICTED" or "CONTRADICT" in claim_upper or "UNAUTHORIZED" in claim_upper:
            return AdjudicationResponse(
                verification_status=VerificationStatus.ADJUDICATED,
                final_label="CONTRADICTED",
                adjudicator_model=self.model_name,
                adjudicator_confidence=0.95,
                uncertainty_reason=UncertaintyReason.NONE,
                adjudication_invoked=True,
                estimated_cost_usd=0.005,
            )

        # Default confident resolution to SUPPORTED
        return AdjudicationResponse(
            verification_status=VerificationStatus.ADJUDICATED,
            final_label="SUPPORTED",
            adjudicator_model=self.model_name,
            adjudicator_confidence=0.92,
            uncertainty_reason=UncertaintyReason.NONE,
            adjudication_invoked=True,
            estimated_cost_usd=0.005,
        )


class RealLLMAdjudicator(Adjudicator):
    """Real LLM Adjudicator adapter for live cloud model execution."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("ADJUDICATOR_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self._gemini_verifier = None
        if self.api_key:
            try:
                from app.tier1.semantic_verifier import GeminiSemanticVerifier
                self._gemini_verifier = GeminiSemanticVerifier(api_key=self.api_key, model_name=self.model_name)
            except Exception as e:
                logger.warning(f"Failed to initialize GeminiSemanticVerifier in RealLLMAdjudicator: {e}")

    async def adjudicate(
        self,
        claim: ClaimVerificationItem,
        evidence: List[EvidenceSnippet],
        nli_result: VerifierResponse,
        policy_thresholds: Optional[Dict[str, Any]] = None,
        scenario: Optional[str] = None,
    ) -> AdjudicationResponse:
        """Call external LLM API if credentials configured, otherwise fallback to mock."""
        if not self._gemini_verifier:
            # Graceful fallback to mock adjudicator
            mock = MockAdjudicator(model_name=self.model_name)
            return await mock.adjudicate(claim, evidence, nli_result, policy_thresholds, scenario)

        evidence_snippets = [e.content_snippet for e in evidence]
        res = await self._gemini_verifier.verify_async(claim.claim_text, evidence_snippets)

        if res.label == "INSUFFICIENT_EVIDENCE" or res.confidence < 0.70:
            return AdjudicationResponse(
                verification_status=VerificationStatus.ADJUDICATION_INCONCLUSIVE,
                final_label=None,  # Invariant: final_label MUST be None when inconclusive
                adjudicator_model=res.model,
                adjudicator_confidence=res.confidence,
                uncertainty_reason=UncertaintyReason.JUDGE_LOW_CONFIDENCE,
                adjudication_invoked=True,
                estimated_cost_usd=0.0001,
            )

        return AdjudicationResponse(
            verification_status=VerificationStatus.ADJUDICATED,
            final_label=res.label,
            adjudicator_model=res.model,
            adjudicator_confidence=res.confidence,
            uncertainty_reason=UncertaintyReason.NONE,
            adjudication_invoked=True,
            estimated_cost_usd=0.0001,
        )
