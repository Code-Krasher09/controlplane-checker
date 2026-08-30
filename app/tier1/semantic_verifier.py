"""Provider-neutral Semantic Verifier interface and Gemini implementation."""

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.domain.models import ClaimVerificationItem, EvidenceSnippet

logger = logging.getLogger(__name__)


class SemanticVerificationResult(BaseModel):
    """Standardized result from a Semantic Verifier execution."""

    label: str  # "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE"
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class SemanticVerifier(ABC):
    """Abstract interface for Tier-1 semantic verification."""

    @abstractmethod
    async def verify_async(
        self,
        claim_text: str,
        evidence_snippets: List[str],
        policy_context: Optional[str] = None,
    ) -> SemanticVerificationResult:
        """Verify claim against provided evidence context asynchronously."""
        pass

    def verify(
        self,
        claim_text: str,
        evidence_snippets: List[str],
        policy_context: Optional[str] = None,
    ) -> SemanticVerificationResult:
        """Synchronous wrapper for verifier using a worker thread."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run,
                self.verify_async(claim_text, evidence_snippets, policy_context),
            )
            return future.result()


class GeminiSemanticVerifier(SemanticVerifier):
    """Production Gemini-powered LLM-as-a-Judge semantic verifier."""

    SYSTEM_INSTRUCTION: str = """You are a strict, objective semantic verification judge for an enterprise policy governance system.
Your job is to determine whether a CLAIM is supported, contradicted, or has insufficient evidence based ONLY on the provided EVIDENCE.

You must output valid JSON strictly conforming to this schema:
{
  "label": "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE",
  "confidence": float between 0.0 and 1.0,
  "reason": "short explanation of the verification decision"
}

Definitions:
- SUPPORTED: The provided evidence directly or logically supports the claim.
- CONTRADICTED: The provided evidence directly or logically conflicts with or refutes the claim.
- INSUFFICIENT_EVIDENCE: The provided evidence does not contain enough information to confirm or refute the claim.

Rules:
1. Rely ONLY on the given evidence. Do NOT use outside world knowledge to assume unstated facts.
2. Do not mark SUPPORTED merely because a claim seems plausible.
3. If evidence is empty, ambiguous, or lacks specific details, return INSUFFICIENT_EVIDENCE.
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.provider = "google_gemini"

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiSemanticVerifier.")

    async def verify_async(
        self,
        claim_text: str,
        evidence_snippets: List[str],
        policy_context: Optional[str] = None,
    ) -> SemanticVerificationResult:
        """Verify claim against evidence snippets using Gemini API."""
        if not evidence_snippets:
            return SemanticVerificationResult(
                label="INSUFFICIENT_EVIDENCE",
                confidence=1.0,
                reason="No evidence provided to evaluate claim.",
                provider=self.provider,
                model=self.model_name,
                latency_ms=0.0,
            )

        combined_evidence = "\n---\n".join(evidence_snippets)
        user_prompt = f"EVIDENCE:\n{combined_evidence}\n\nCLAIM:\n{claim_text}\n"
        if policy_context:
            user_prompt += f"\nPOLICY CONTEXT:\n{policy_context}\n"
        user_prompt += "\nVerify the claim against the evidence and output strictly valid JSON."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "system_instruction": {"parts": [{"text": self.SYSTEM_INSTRUCTION}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "maxOutputTokens": 1024,
            },
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                latency_ms = (time.perf_counter() - t0) * 1000.0

                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError(f"No candidates returned: {data}")

                text = candidates[0]["content"]["parts"][0]["text"]
                usage = data.get("usageMetadata", {})
                input_tokens = usage.get("promptTokenCount", 0)
                output_tokens = usage.get("candidatesTokenCount", 0)

                parsed = json.loads(text)
                label = parsed.get("label", "").upper()
                if label not in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]:
                    raise ValueError(f"Invalid label returned: '{label}'")

                confidence = float(parsed.get("confidence", 1.0))
                confidence = max(0.0, min(1.0, confidence))
                reason = str(parsed.get("reason", "")).strip()
                if not reason:
                    reason = f"Model classified as {label} with confidence {confidence}"

                return SemanticVerificationResult(
                    label=label,
                    confidence=confidence,
                    reason=reason,
                    provider=self.provider,
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    raw_response=parsed,
                )

            except Exception as e:
                last_error = e
                logger.warning(f"Gemini verification attempt {attempt+1} failed: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2.0 * (attempt + 1))

        # If all retries failed, fall back to safe error result
        logger.error(f"Gemini verification permanently failed: {last_error}")
        return SemanticVerificationResult(
            label="INSUFFICIENT_EVIDENCE",
            confidence=0.0,
            reason=f"Verifier error: {str(last_error)}",
            provider=self.provider,
            model=self.model_name,
            latency_ms=0.0,
            raw_response={"error": str(last_error)},
        )
