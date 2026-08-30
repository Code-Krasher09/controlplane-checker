"""Tier 0 token estimation and cost calculation."""

from app.domain.models import CostTelemetry


class CostEstimator:
    """Estimates tokens, model costs, and adjudication costs."""

    # Default baseline pricing per 1M tokens (e.g. gpt-4o-mini rates)
    INPUT_COST_PER_MILLION: float = 0.15
    OUTPUT_COST_PER_MILLION: float = 0.60
    ADJUDICATION_COST_PER_CALL: float = 0.005

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text (~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        adjudication_calls: int = 0,
        latency_ms: int = 0,
        retry_attempts: int = 0,
    ) -> CostTelemetry:
        """Calculate estimated cost telemetry."""
        model_cost = (
            (input_tokens / 1_000_000) * self.INPUT_COST_PER_MILLION
            + (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_MILLION
        )
        adj_cost = adjudication_calls * self.ADJUDICATION_COST_PER_CALL
        total_cost = model_cost + adj_cost

        return CostTelemetry(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            total_latency_ms=latency_ms,
            estimated_model_cost_usd=round(model_cost, 6),
            estimated_adjudication_cost_usd=round(adj_cost, 6),
            total_cost_usd=round(total_cost, 6),
            repair_attempts=retry_attempts,
        )
