"""Provider-neutral AI model interface and deterministic MockModel implementation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from app.domain.models import ClaimVerificationItem, EvidenceSnippet
from app.persistence.seed import MOCK_MODEL_ID


class ModelResponse(BaseModel):
    """Standardized response from an AI model invocation."""
    content: str
    output_tokens: int
    latency_ms: int
    model_name: str
    model_id: UUID
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelProvider(ABC):
    """Abstract interface for AI foundation model providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        scenario: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate response text from prompt."""
        pass

    @abstractmethod
    async def generate_repair(
        self,
        original_prompt: str,
        previous_response: str,
        failed_claims: List[ClaimVerificationItem],
        evidence: List[EvidenceSnippet],
        repair_prompt: str,
        scenario: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate repaired response text addressing contradicted claims."""
        pass


class MockModelProvider(ModelProvider):
    """Deterministic Mock AI Model for scenario-driven testing and local execution."""

    SCENARIOS: Dict[str, str] = {
        "SAFE": "The standard return policy allows customers to return items within 30 days of delivery.",
        "PII": "Customer profile updated: Contact john.smith@example.com at 555-019-4821. SSN: 000-55-9876.",
        "CONTRADICTED": "All customers are entitled to an immediate $1,000 cash waiver with zero approval required.",
        "REPAIR_FAIL": "All customers are entitled to an immediate $1,000 cash waiver with zero approval required.",
        "INSUFFICIENT": "Quantum teleportation parcel shipping is covered by standard domestic warranty.",
        "AMBIGUOUS_NLI": "Plan B provides complimentary international roaming across 45 designated countries subject to exclusions.",
        "BIAS": "Older workers are generally unsuitable for high-speed technology teams.",
        "TOXICITY": "Your request is utterly foolish and I refuse to help such an incompetent user.",
    }

    REPAIRED_RESPONSES: Dict[str, str] = {
        "DEFAULT": "Customer courtesy fee waivers are strictly capped at $200 per account and require formal supervisor signoff.",
        "RETURN": "The retail return policy allows full refunds within 30 days of product delivery in original packaging.",
    }

    def __init__(self, model_id: UUID = MOCK_MODEL_ID, model_name: str = "mock-pipeline-model-v1"):
        self.model_id = model_id
        self.model_name = model_name

    async def generate(
        self,
        prompt: str,
        scenario: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate deterministic scenario-based response."""
        selected_scenario = (scenario or "").upper()

        if not selected_scenario:
            prompt_upper = prompt.upper()
            if "PII" in prompt_upper or "EMAIL" in prompt_upper or "SSN" in prompt_upper:
                selected_scenario = "PII"
            elif "CONTRADICT" in prompt_upper or "WAIVER" in prompt_upper or "$1,000" in prompt_upper or "$1000" in prompt_upper:
                selected_scenario = "CONTRADICTED"
            elif (
                "UNKNOWN" in prompt_upper
                or "QUANTUM" in prompt_upper
                or "NO EVIDENCE" in prompt_upper
                or "TELEPORT" in prompt_upper
                or "INTERDIMENSIONAL" in prompt_upper
                or "WARP" in prompt_upper
            ):
                selected_scenario = "INSUFFICIENT"
            elif "AMBIGUOUS" in prompt_upper or "PLAN B" in prompt_upper or "ROAMING" in prompt_upper:
                selected_scenario = "AMBIGUOUS_NLI"
            elif "BIAS" in prompt_upper or "OLDER" in prompt_upper:
                selected_scenario = "BIAS"
            elif "TOXIC" in prompt_upper or "HATE" in prompt_upper:
                selected_scenario = "TOXICITY"
            else:
                selected_scenario = "SAFE"

        content = self.SCENARIOS.get(selected_scenario, self.SCENARIOS["SAFE"])

        output_tokens = max(1, len(content) // 4)
        if max_tokens and output_tokens > max_tokens:
            content = content[: max_tokens * 4]
            output_tokens = max_tokens

        return ModelResponse(
            content=content,
            output_tokens=output_tokens,
            latency_ms=25,
            model_name=self.model_name,
            model_id=self.model_id,
            metadata={"scenario": selected_scenario},
        )

    async def generate_repair(
        self,
        original_prompt: str,
        previous_response: str,
        failed_claims: List[ClaimVerificationItem],
        evidence: List[EvidenceSnippet],
        repair_prompt: str,
        scenario: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate repaired response text."""
        selected_scenario = (scenario or "").upper()

        if selected_scenario == "REPAIR_FAIL" or "REPEAT_FAIL" in repair_prompt.upper():
            # Scenario: Repair remains wrong
            content = "All customers are entitled to an immediate $1,000 cash waiver with zero approval required."
        else:
            # Scenario: Successful evidence-constrained correction
            content = self.REPAIRED_RESPONSES["DEFAULT"]

        output_tokens = max(1, len(content) // 4)
        if max_tokens and output_tokens > max_tokens:
            content = content[: max_tokens * 4]
            output_tokens = max_tokens

        return ModelResponse(
            content=content,
            output_tokens=output_tokens,
            latency_ms=30,
            model_name=self.model_name,
            model_id=self.model_id,
            metadata={"repair_scenario": selected_scenario or "SUCCESS"},
        )
