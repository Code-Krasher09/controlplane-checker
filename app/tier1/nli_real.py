"""Real Tier 1 Natural Language Inference (NLI) Verifier using local transformers."""

import logging
from typing import Dict, List
from app.domain.models import (
    AdjudicationTrigger,
    ClaimVerificationItem,
    EvidenceSnippet,
    UncertaintyReason,
    VerificationStatus,
    VerifierResponse,
)
from app.tier1.nli_verifier import NLIVerifier

logger = logging.getLogger(__name__)

class RealNLIVerifier(NLIVerifier):
    """Local inference NLI verifier using HuggingFace cross-encoders."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-small", truncation_strategy="only_first"):
        self.truncation_strategy = truncation_strategy
        try:
            from transformers import pipeline
            # Use text-classification for cross-encoders
            self.classifier = pipeline("text-classification", model=model_name, top_k=None, truncation=self.truncation_strategy, max_length=512)
            self.model_name = model_name
        except ImportError:
            raise ImportError("transformers and torch are required for RealNLIVerifier. Run: pip install transformers torch")
        except Exception as e:
            raise RuntimeError(f"Failed to load NLI model {model_name}: {e}")

    def verify(self, claim: ClaimVerificationItem, evidence: List[EvidenceSnippet]) -> VerifierResponse:
        """Evaluate claim against evidence using local transformer."""
        if not evidence:
            return VerifierResponse(
                label="INSUFFICIENT_EVIDENCE",
                nli_confidence=0.0,
                top2_scores=None,
                evidence_ids=[],
                verification_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                adjudication_trigger=AdjudicationTrigger.NONE,
                uncertainty_reason=UncertaintyReason.NONE,
            )

        evidence_ids = [e.evidence_id for e in evidence]
        combined_evidence = " ".join([e.content_snippet for e in evidence])

        inputs = {"text": combined_evidence, "text_pair": claim.claim_text}
        
        try:
            scores = self.classifier(inputs)
            if isinstance(scores, list) and isinstance(scores[0], list):
                scores = scores[0]
            
            mapped_scores = {}
            for score_dict in scores:
                raw_label = score_dict["label"].lower()
                val = score_dict["score"]
                
                if "entail" in raw_label:
                    mapped_scores["SUPPORTED"] = mapped_scores.get("SUPPORTED", 0) + val
                elif "contradict" in raw_label:
                    mapped_scores["CONTRADICTED"] = mapped_scores.get("CONTRADICTED", 0) + val
                elif "neutral" in raw_label:
                    mapped_scores["INSUFFICIENT_EVIDENCE"] = mapped_scores.get("INSUFFICIENT_EVIDENCE", 0) + val
                else:
                    mapped_scores[raw_label.upper()] = val
            
            sorted_scores = sorted(mapped_scores.items(), key=lambda x: x[1], reverse=True)
            top1_label, top1_score = sorted_scores[0]
            
            top2_dict = {}
            if len(sorted_scores) > 0:
                top2_dict[sorted_scores[0][0]] = sorted_scores[0][1]
            if len(sorted_scores) > 1:
                top2_dict[sorted_scores[1][0]] = sorted_scores[1][1]

            return VerifierResponse(
                label=top1_label,
                nli_confidence=top1_score,
                top2_scores=top2_dict,
                evidence_ids=evidence_ids,
                verification_status=VerificationStatus.DIRECT_NLI,
                adjudication_trigger=AdjudicationTrigger.NONE,
                uncertainty_reason=UncertaintyReason.NONE,
            )
        except Exception as e:
            logger.error(f"NLI model inference failed: {e}")
            return VerifierResponse(
                label="INSUFFICIENT_EVIDENCE",
                nli_confidence=0.0,
                top2_scores=None,
                evidence_ids=evidence_ids,
                verification_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                adjudication_trigger=AdjudicationTrigger.NONE,
                uncertainty_reason=UncertaintyReason.NONE,
            )
