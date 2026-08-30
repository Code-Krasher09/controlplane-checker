"""Real P0 prompt-response semantic consistency signal scorer using SentenceTransformers."""

import logging
from typing import Optional
from app.tier0.semantic_consistency import SemanticConsistencyScorer

logger = logging.getLogger(__name__)


class RealSemanticConsistencyScorer(SemanticConsistencyScorer):
    """Calculates semantic alignment between prompt and generated response using embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer, util
            self.model = SentenceTransformer(model_name)
            self.util = util
        except ImportError:
            raise ImportError("sentence-transformers and torch are required. Run: pip install sentence-transformers torch")
        except Exception as e:
            raise RuntimeError(f"Failed to load sentence transformer model {model_name}: {e}")

    def calculate_score(self, prompt: str, response: str) -> float:
        """Calculate embedding cosine similarity between prompt and response in range [0.0, 1.0]."""
        if not prompt or not response:
            return 0.5
            
        try:
            # Compute embeddings
            embeddings1 = self.model.encode(prompt, convert_to_tensor=True)
            embeddings2 = self.model.encode(response, convert_to_tensor=True)

            # Compute cosine similarities
            cosine_scores = self.util.cos_sim(embeddings1, embeddings2)
            
            # Extract raw score
            score = float(cosine_scores[0][0])
            
            # Clamp between 0.0 and 1.0 (cosine sim can technically be [-1, 1])
            score = max(0.0, min(1.0, score))
            return round(score, 4)
        except Exception as e:
            logger.error(f"Embedding inference failed: {e}")
            return 0.5
