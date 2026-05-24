from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class AIProviderResult(BaseModel):
    """
    Standardized response payload returned by all AI providers.
    Ensures complete contract separation and structured logging capabilities.
    """
    text: str
    provider: str
    model: str
    latency_ms: float
    token_estimate: int
    cost_estimate: float
    finish_reason: str
    fallback_used: bool = False
    error: Optional[str] = None

class BaseAIProvider(ABC):
    """
    Abstract Base Class for Multi-Model AI Providers.
    All providers must implement the generate() contract.
    """
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any]
    ) -> AIProviderResult:
        """
        Executes a prompt generation turn.

        Args:
            messages: List of message dicts (role, content) conforming to ChatML/GPT structure.
            model_config: Config options (temperature, max_tokens, timeout_seconds, model).

        Returns:
            AIProviderResult containing generated response and metadata metrics.
        """
        pass
