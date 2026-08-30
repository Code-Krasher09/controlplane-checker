"""Tier 1 Verification Orchestrator Service with Evidence Quality Assessment."""

from typing import Any, Dict, List, Optional, Tuple
from app.domain.models import (
    AdjudicationTrigger,
    ClaimVerificationItem,
    EvidenceSnippet,
    UncertaintyReason,
    VerificationStatus,
)
from .claim_extractor import ClaimExtractor
from .evidence_quality import EvidenceQualityEvaluator
from .evidence_store import EvidenceRepository
from .nli_verifier import DeterministicNLIVerifier, NLIVerifier


class Tier1Service:
    """Orchestrates claim extraction, evidence retrieval, evidence quality evaluation, and NLI verification."""

    def __init__(
        self,
        verifier: Optional[NLIVerifier] = None,
        evidence_repo: Optional[EvidenceRepository] = None,
        quality_evaluator: Optional[EvidenceQualityEvaluator] = None,
    ):
        self.claim_extractor = ClaimExtractor()
        self.evidence_repo = evidence_repo or EvidenceRepository()
        self.verifier = verifier or DeterministicNLIVerifier()
        self.quality_evaluator = quality_evaluator or EvidenceQualityEvaluator()

    def verify_response(
        self,
        response_text: str,
        policy_thresholds: Optional[Dict[str, Any]] = None,
        application_profile: Optional[str] = None,
        policy_scope: Optional[str] = None,
    ) -> Tuple[List[ClaimVerificationItem], List[Tuple[ClaimVerificationItem, List[EvidenceSnippet]]]]:
        """Extract claims, retrieve evidence, assess evidence quality, and run NLI verification.

        Returns:
            Tuple of (verified_claims_list, claim_with_evidence_pairs)
        """
        claims = self.claim_extractor.extract_claims(response_text)
        verified_claims: List[ClaimVerificationItem] = []
        claim_evidence_pairs: List[Tuple[ClaimVerificationItem, List[EvidenceSnippet]]] = []

        for claim in claims:
            # 1. Evidence lookup with metadata context
            raw_evidence = self.evidence_repo.find_relevant_evidence(
                claim.claim_text,
                application_profile=application_profile,
                policy=policy_scope,
            )

            # 2. Post-retrieval Evidence Quality Evaluation
            evaluated_evidence = self.quality_evaluator.evaluate_evidence_set(
                claim.claim_text, raw_evidence, policy_thresholds
            )

            # 3. Check Evidence Adequacy
            if not self.quality_evaluator.is_adequate(evaluated_evidence, policy_thresholds):
                # Critical Invariant: Inadequate/weak evidence yields INSUFFICIENT_EVIDENCE
                # and MUST NEVER trigger Selective Adjudication
                best_quality = evaluated_evidence[0].quality if evaluated_evidence else None

                claim.verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
                claim.final_label = "INSUFFICIENT_EVIDENCE"
                claim.nli_confidence = 0.0
                claim.top2_scores = None
                claim.adjudication_trigger = AdjudicationTrigger.NONE
                claim.uncertainty_reason = UncertaintyReason.NONE
                claim.evidence_quality = best_quality

                verified_claims.append(claim)
                claim_evidence_pairs.append((claim, evaluated_evidence))
                continue

            # 4. Run verification (supports hybrid routing)
            try:
                nli_res = self.verifier.verify(
                    claim,
                    evaluated_evidence,
                    application_profile=application_profile,
                    policy_scope=policy_scope,
                )
            except TypeError:
                nli_res = self.verifier.verify(claim, evaluated_evidence)

            # 4b. Confidence & Gate checks
            if nli_res.label != "INSUFFICIENT_EVIDENCE":
                if nli_res.nli_confidence is not None and nli_res.nli_confidence < 0.75:
                    nli_res.verification_status = VerificationStatus.DIRECT_NLI
                    nli_res.adjudication_trigger = AdjudicationTrigger.NLI_LOW_CONFIDENCE
                    nli_res.uncertainty_reason = UncertaintyReason.NONE
                elif nli_res.top2_scores and len(nli_res.top2_scores) >= 2:
                    sorted_scores = sorted(nli_res.top2_scores.values(), reverse=True)
                    if (sorted_scores[0] - sorted_scores[1]) < 0.15:
                        nli_res.verification_status = VerificationStatus.DIRECT_NLI
                        nli_res.adjudication_trigger = AdjudicationTrigger.NLI_CLOSE_TOP2
                        nli_res.uncertainty_reason = UncertaintyReason.NONE

            # 5. Populate claim verification fields
            best_quality = evaluated_evidence[0].quality if evaluated_evidence else None

            claim.verification_status = nli_res.verification_status
            claim.nli_confidence = nli_res.nli_confidence
            claim.top2_scores = nli_res.top2_scores
            claim.adjudication_trigger = nli_res.adjudication_trigger
            claim.uncertainty_reason = nli_res.uncertainty_reason
            claim.final_label = nli_res.label if nli_res.verification_status != VerificationStatus.ADJUDICATION_INCONCLUSIVE else None
            claim.evidence_quality = best_quality
            if hasattr(nli_res, "adjudicator_model") and nli_res.adjudicator_model:
                claim.adjudicator_model = nli_res.adjudicator_model
                claim.adjudicator_confidence = getattr(nli_res, "adjudicator_confidence", nli_res.nli_confidence)

            verified_claims.append(claim)
            claim_evidence_pairs.append((claim, evaluated_evidence))

        return verified_claims, claim_evidence_pairs
