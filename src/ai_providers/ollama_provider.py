import time
import logging
import requests
from typing import Any, Dict, List
from src.ai_providers.base import BaseAIProvider, AIProviderResult
from src.core.config import settings

logger = logging.getLogger(__name__)

class OllamaProvider(BaseAIProvider):
    """
    Concrete implementation of BaseAIProvider calling a local Ollama / llama.cpp HTTP chat endpoint.
    """

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any]
    ) -> AIProviderResult:
        model = model_config.get("model", settings.OLLAMA_MODEL)
        temperature = model_config.get("temperature", 0.7)
        timeout = model_config.get("timeout_seconds", settings.AI_TIMEOUT_SECONDS)
        base_url = settings.OLLAMA_BASE_URL

        # Approximate token count for estimation
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        prompt_tokens_est = max(1, prompt_chars // 4)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        start_time = time.time()
        try:
            resp = requests.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=timeout
            )
            resp.raise_for_status()
            
            resp_json = resp.json()
            latency_ms = (time.time() - start_time) * 1000.0
            
            message_obj = resp_json.get("message", {})
            text_response = message_obj.get("content", "")
            
            # Ollama does not charge, so cost is 0.0
            prompt_tokens = resp_json.get("prompt_eval_count", prompt_tokens_est)
            completion_tokens = resp_json.get("eval_count", max(1, len(text_response) // 4))
            total_tokens = prompt_tokens + completion_tokens
            
            return AIProviderResult(
                text=text_response.strip(),
                provider="ollama",
                model=model,
                latency_ms=latency_ms,
                token_estimate=total_tokens,
                cost_estimate=0.0,
                finish_reason="stop",
                fallback_used=False
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.error("OllamaProvider API call failed: %s", e)
            raise e
