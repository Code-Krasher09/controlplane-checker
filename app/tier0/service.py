"""Unified Tier 0 Execution Service."""

from typing import List, Tuple
from app.domain.models import PolicyEventItem
from .bias import HeuristicBiasDetector
from .cost import CostEstimator
from .pii import PIIDetector
from .policy_toxicity import PolicyToxicityDetector
from .semantic_consistency import SemanticConsistencyScorer


class Tier0Service:
    """Orchestrates always-on Tier 0 detectors and signals."""

    def __init__(self):
        self.pii_detector = PIIDetector()
        self.policy_detector = PolicyToxicityDetector()
        self.bias_detector = HeuristicBiasDetector()
        self.semantic_scorer = SemanticConsistencyScorer()
        self.cost_estimator = CostEstimator()

    def run_checks(
        self, prompt: str, response: str, semantic_consistency_enabled: bool = False
    ) -> Tuple[List[PolicyEventItem], float]:
        """Execute all Tier 0 detectors on response text.

        Returns:
            Tuple of (policy_events, semantic_consistency_score)
        """
        events: List[PolicyEventItem] = []

        # 1. PII and Secrets detection (scans prompt and response)
        events.extend(self.pii_detector.scan(prompt))
        events.extend(self.pii_detector.scan(response))

        # 2. Policy violations and toxicity screening
        events.extend(self.policy_detector.scan(prompt))
        events.extend(self.policy_detector.scan(response))

        # 3. Heuristic bias screening
        events.extend(self.bias_detector.scan(prompt))
        events.extend(self.bias_detector.scan(response))

        # 4. Prompt-response semantic consistency signal (routing only)
        consistency_score = 1.0  # Default safe/high score if disabled
        if semantic_consistency_enabled:
            consistency_score = self.semantic_scorer.calculate_score(prompt, response)

        return events, consistency_score
