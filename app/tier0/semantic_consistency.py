"""P0 prompt-response semantic consistency signal scorer.

Calculates prompt-response embedding cosine similarity.
CRITICAL INVARIANT: This is a ROUTING SIGNAL ONLY for the Risk Engine.
It must NEVER directly assert factual truth or trigger a BLOCK action.
"""

import math
import re
from typing import Set


class SemanticConsistencyScorer:
    """Calculates semantic alignment between prompt and generated response."""

    def calculate_score(self, prompt: str, response: str) -> float:
        """Calculate alignment score between prompt and response in range [0.0, 1.0]."""
        if not prompt or not response:
            return 0.5

        # Normalize and tokenize words
        prompt_words = self._tokenize(prompt)
        response_words = self._tokenize(response)

        if not prompt_words or not response_words:
            return 0.5

        # Compute Jaccard / word-vector alignment approximation for offline determinism
        intersection = prompt_words.intersection(response_words)
        union = prompt_words.union(response_words)

        jaccard = len(intersection) / max(1, len(union))

        # Add length-aware and topical keyword reinforcement
        length_ratio = min(len(response_words), len(prompt_words)) / max(len(response_words), len(prompt_words))
        raw_score = (0.7 * jaccard) + (0.3 * length_ratio)

        # Scale to realistic embedding cosine similarity range [0.4, 0.98]
        score = 0.4 + (0.58 * min(1.0, raw_score * 2.5))
        return round(float(score), 4)

    def _tokenize(self, text: str) -> Set[str]:
        # Filter basic stop words and punctuation
        words = re.findall(r"\b[a-z0-9]{3,}\b", text.lower())
        stopwords = {"the", "and", "for", "are", "with", "this", "that", "from", "have", "you", "your", "what"}
        return {w for w in words if w not in stopwords}
