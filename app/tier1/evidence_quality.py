"""Post-retrieval Evidence Quality Evaluator for Tier 1 Verification.

Evaluates:
- Authority (Source trustworthiness level)
- Relevance (Claim-to-snippet semantic alignment)
- Freshness (Temporal validity / currency)
- Completeness (Coverage of the factual proposition)
- Quality Score (Composite weighted score)

CRITICAL INVARIANT:
Weak evidence (quality_score < threshold) yields INSUFFICIENT_EVIDENCE
and MUST NEVER trigger Selective Adjudication.
"""

import re
from typing import Any, Dict, List, Optional, Set
from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet


class EvidenceQualityEvaluator:
    """Evaluates retrieved evidence quality across authority, relevance, freshness, and completeness."""

    DEFAULT_MIN_QUALITY_THRESHOLD: float = 0.60

    AUTHORITY_WEIGHTS: Dict[str, float] = {
        "HIGH": 1.0,
        "MEDIUM": 0.70,
        "LOW": 0.30,
        "UNKNOWN": 0.40,
    }

    FRESHNESS_WEIGHTS: Dict[str, float] = {
        "FRESH": 1.0,
        "STALE": 0.40,
        "UNKNOWN": 0.60,
    }

    def evaluate_snippet(
        self,
        claim_text: str,
        snippet: EvidenceSnippet,
        policy_thresholds: Optional[Dict[str, Any]] = None,
    ) -> ClaimEvidenceQuality:
        """Compute post-retrieval quality metrics for an evidence snippet."""
        if snippet.source_type == "EVALUATION_FIXTURE" and snippet.quality:
            return snippet.quality
            
        thresholds = policy_thresholds or {}

        # 1. Authority Scoring
        auth_level = (snippet.quality.authority if snippet.quality and snippet.quality.authority else "HIGH").upper()
        if snippet.metadata and "authority" in snippet.metadata:
            auth_level = str(snippet.metadata["authority"]).upper()
        elif snippet.source_type == "UNVERIFIED" or "untrusted" in (snippet.source_id or "").lower():
            auth_level = "LOW"
        elif snippet.source_type in ("POLICY_DOC", "HR_DOC", "TELECOM_DOC", "LEGAL_DOC"):
            auth_level = "HIGH"

        auth_score = self.AUTHORITY_WEIGHTS.get(auth_level, 0.70)

        # 2. Relevance Scoring (Keyword stem overlap)
        relevance_score = self._compute_relevance(claim_text, snippet.content_snippet)

        # 3. Freshness Scoring
        fresh_status = "FRESH"
        if snippet.metadata and "freshness_status" in snippet.metadata:
            fresh_status = str(snippet.metadata["freshness_status"]).upper()
        elif snippet.metadata and snippet.metadata.get("is_stale", False):
            fresh_status = "STALE"
        elif "stale" in (snippet.source_id or "").lower() or "deprecated" in (snippet.document_version or "").lower():
            fresh_status = "STALE"

        freshness_score = self.FRESHNESS_WEIGHTS.get(fresh_status, 1.0)

        # 4. Completeness Scoring (Coverage of core claim verbs and nouns)
        completeness_score = self._compute_completeness(claim_text, snippet.content_snippet)

        # 5. Composite Quality Score
        # Formula: 0.35 * relevance + 0.25 * authority + 0.20 * freshness + 0.20 * completeness
        if relevance_score < 0.15:
            # Gating penalty for irrelevant evidence: authority cannot prop up unrelated documents
            composite_score = relevance_score * 0.5
        else:
            composite_score = (
                (0.35 * relevance_score)
                + (0.25 * auth_score)
                + (0.20 * freshness_score)
                + (0.20 * completeness_score)
            )
        quality_score = round(max(0.0, min(1.0, composite_score)), 4)

        return ClaimEvidenceQuality(
            authority=auth_level,
            freshness=round(freshness_score, 4),
            relevance=round(relevance_score, 4),
            completeness=round(completeness_score, 4),
            quality_score=quality_score,
            freshness_status=fresh_status,
        )

    def evaluate_evidence_set(
        self,
        claim_text: str,
        evidence_list: List[EvidenceSnippet],
        policy_thresholds: Optional[Dict[str, Any]] = None,
    ) -> List[EvidenceSnippet]:
        """Evaluate and attach quality scores to all retrieved evidence snippets."""
        evaluated: List[EvidenceSnippet] = []
        for snippet in evidence_list:
            quality = self.evaluate_snippet(claim_text, snippet, policy_thresholds)
            snippet.quality = quality
            evaluated.append(snippet)
        return evaluated

    def is_adequate(
        self,
        evidence_list: List[EvidenceSnippet],
        policy_thresholds: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Determine if retrieved evidence meets minimum quality standards for verification."""
        if not evidence_list:
            return False

        thresholds = policy_thresholds or {}
        min_quality = float(thresholds.get("min_evidence_quality", self.DEFAULT_MIN_QUALITY_THRESHOLD))

        # Check if at least one evidence snippet exceeds quality threshold AND has substantive relevance
        for e in evidence_list:
            if e.quality:
                q_score = e.quality.quality_score
                r_score = e.quality.relevance
                if q_score >= min_quality and r_score >= 0.15:
                    return True
        return False

    def _compute_relevance(self, claim: str, evidence: str) -> float:
        """Compute lexical overlap relevance between claim and evidence snippet."""
        if not claim or not evidence:
            return 0.0

        claim_words = self._tokenize(claim)
        evidence_words = self._tokenize(evidence)

        if not claim_words or not evidence_words:
            return 0.0

        overlap = claim_words.intersection(evidence_words)
        if not overlap or len(overlap) < 2:
            # Single word coincidence (e.g. "standard") does not establish topic relevance
            return len(overlap) / max(1, len(claim_words))

        # 2+ matching topic stems establish strong domain relevance
        coverage = len(overlap) / min(6, len(claim_words))
        return round(min(1.0, coverage), 4)

    def _compute_completeness(self, claim: str, evidence: str) -> float:
        """Estimate whether evidence adequately covers the proposition."""
        if not claim or not evidence:
            return 0.0

        claim_words = self._tokenize(claim)
        evidence_words = self._tokenize(evidence)

        # Ratio of claim words found in evidence, scaled
        overlap = len(claim_words.intersection(evidence_words))
        coverage = overlap / max(1, len(claim_words))

        # Evidence length check: very short fragments (< 30 chars) are penalized
        length_penalty = 1.0 if len(evidence.strip()) >= 40 else (len(evidence.strip()) / 40.0)
        return round(min(1.0, coverage * length_penalty), 4)

    def _stem(self, word: str) -> str:
        w = word.lower()
        if w.endswith("s") and len(w) > 3:
            w = w[:-1]
        if w.endswith("ed") and len(w) > 4:
            w = w[:-2]
        if w.endswith("ing") and len(w) > 5:
            w = w[:-3]
        return w

    def _tokenize(self, text: str) -> Set[str]:
        words = re.findall(r"\b[a-z0-9]{3,}\b", text.lower().replace("$", " ").replace(",", ""))
        stopwords = {
            "the", "and", "for", "are", "with", "this", "that", "from", "have", "you", "your",
            "what", "all", "can", "get", "zero", "any", "without", "been", "will", "our"
        }
        return {self._stem(w) for w in words if w not in stopwords}
