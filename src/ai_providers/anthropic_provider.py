import time
import logging
import requests
from typing import Any, Dict, List
from src.ai_providers.base import BaseAIProvider, AIProviderResult
from src.core.config import settings

logger = logging.getLogger(__name__)

# Standard model cost rates per token (USD)
_MODEL_RATES = {
    "claude-3-5-sonnet-20241022": {
        "prompt": 0.000003,      # $3.00 per million
        "completion": 0.000015   # $15.00 per million
    },
    "claude-3-opus-20240229": {
        "prompt": 0.000015,     # $15.00 per million
        "completion": 0.000075   # $75.00 per million
    },
    "default": {
        "prompt": 0.000003,
        "completion": 0.000015
    }
}

class AnthropicProvider(BaseAIProvider):
    """
    Concrete implementation of BaseAIProvider calling Anthropic's Messages API.
    """

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any]
    ) -> AIProviderResult:
        model = model_config.get("model", settings.ANTHROPIC_MODEL)
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 450)
        timeout = model_config.get("timeout_seconds", settings.AI_TIMEOUT_SECONDS)

        from src.ai_providers.orchestrator import _is_placeholder_key
        if not settings.ANTHROPIC_API_KEY or _is_placeholder_key(settings.ANTHROPIC_API_KEY):
            raise ValueError("Anthropic API key missing.")

        # Extract system prompt (Anthropic requires it as a top-level parameter)
        system_prompt = ""
        filtered_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_prompt += content + "\n"
            else:
                # Anthropic messages API only accepts 'user' and 'assistant' roles
                # Map other roles to user if they appear
                mapped_role = "user" if role not in ("user", "assistant") else role
                filtered_messages.append({
                    "role": mapped_role,
                    "content": content
                })

        system_prompt = system_prompt.strip()

        # Approximate token count for estimation in case of failure/empty usage
        prompt_chars = sum(len(m.get("content", "")) for m in filtered_messages) + len(system_prompt)
        prompt_tokens_est = max(1, prompt_chars // 4)

        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.time()
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            # Check for HTTP errors
            resp.raise_for_status()
            
            resp_json = resp.json()
            latency_ms = (time.time() - start_time) * 1000.0
            
            # Extract content text
            content_list = resp_json.get("content", [])
            text_response = ""
            if content_list and content_list[0].get("type") == "text":
                text_response = content_list[0].get("text", "")
            
            finish_reason = resp_json.get("stop_reason") or "stop"
            
            # Extract usage
            usage = resp_json.get("usage", {})
            prompt_tokens = usage.get("input_tokens", prompt_tokens_est)
            completion_tokens = usage.get("output_tokens", max(1, len(text_response) // 4))
            total_tokens = prompt_tokens + completion_tokens
            
            # Compute cost estimate
            rates = _MODEL_RATES.get(model, _MODEL_RATES["default"])
            cost = (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])
            
            return AIProviderResult(
                text=text_response.strip(),
                provider="anthropic",
                model=model,
                latency_ms=latency_ms,
                token_estimate=total_tokens,
                cost_estimate=cost,
                finish_reason=finish_reason,
                fallback_used=False
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.error("AnthropicProvider API call failed: %s", e)
            raise e
