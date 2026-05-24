import time
from typing import Any, Dict, List, Optional
from src.ai_providers.base import BaseAIProvider, AIProviderResult

class MockProvider(BaseAIProvider):
    """
    Simulation provider for unit tests.
    Enables precise testing of timeouts, circuit breaking, cost limits, and retries.
    """

    def __init__(
        self,
        mock_response: str = "Mock response from simulation provider.",
        force_delay: float = 0.0,
        force_error: Optional[Exception] = None,
        cost_rate: float = 0.0
    ):
        self.mock_response = mock_response
        self.force_delay = force_delay
        self.force_error = force_error
        self.cost_rate = cost_rate

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any]
    ) -> AIProviderResult:
        if self.force_delay > 0:
            time.sleep(self.force_delay)

        if self.force_error:
            raise self.force_error

        # Compute character count based cost estimate
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        prompt_tokens = prompt_chars // 4
        completion_tokens = len(self.mock_response) // 4
        total_tokens = prompt_tokens + completion_tokens

        cost = total_tokens * self.cost_rate

        return AIProviderResult(
            text=self.mock_response,
            provider="mock",
            model="mock-simulator",
            latency_ms=self.force_delay * 1000.0,
            token_estimate=total_tokens,
            cost_estimate=cost,
            finish_reason="stop",
            fallback_used=False
        )
