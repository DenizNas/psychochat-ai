import time
import logging
import openai
from typing import Any, Dict, List
from src.ai_providers.base import BaseAIProvider, AIProviderResult
from src.core.config import settings

logger = logging.getLogger(__name__)

# Standard model cost rates per token (USD)
_MODEL_RATES = {
    "gpt-4o": {
        "prompt": 0.000005,      # $5.00 per million
        "completion": 0.000015   # $15.00 per million
    },
    "gpt-3.5-turbo": {
        "prompt": 0.0000015,     # $1.50 per million
        "completion": 0.000002   # $2.00 per million
    },
    "default": {
        "prompt": 0.0000015,
        "completion": 0.000002
    }
}

class OpenAIProvider(BaseAIProvider):
    """
    Concrete implementation of BaseAIProvider calling OpenAI.
    """

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any]
    ) -> AIProviderResult:
        model = model_config.get("model", settings.AI_PRIMARY_MODEL)
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 250)
        timeout = model_config.get("timeout_seconds", settings.AI_TIMEOUT_SECONDS)

        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key missing.")

        # Pre-calculate prompt tokens (approximate TR density: 1 token ≈ 4 characters)
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        prompt_tokens_est = max(1, prompt_chars // 4)

        start_time = time.time()
        try:
            # Set OpenAI client key
            openai.api_key = settings.OPENAI_API_KEY
            
            resp = openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            
            latency_ms = (time.time() - start_time) * 1000.0
            
            content = resp.choices[0].message.content or ""
            finish_reason = resp.choices[0].finish_reason or "stop"
            
            # Extract or estimate token counts
            usage = getattr(resp, "usage", None)
            if usage:
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens
            else:
                prompt_tokens = prompt_tokens_est
                completion_tokens = max(1, len(content) // 4)

            total_tokens = prompt_tokens + completion_tokens

            # Compute cost estimate
            rates = _MODEL_RATES.get(model, _MODEL_RATES["default"])
            cost = (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])

            return AIProviderResult(
                text=content.strip(),
                provider="openai",
                model=model,
                latency_ms=latency_ms,
                token_estimate=total_tokens,
                cost_estimate=cost,
                finish_reason=finish_reason,
                fallback_used=False
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.error("OpenAIProvider API call failed: %s", e)
            raise e
