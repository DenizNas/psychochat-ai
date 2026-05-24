import time
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.ai_providers.base import BaseAIProvider, AIProviderResult
from src.ai_providers.openai_provider import OpenAIProvider
from src.ai_providers.local_provider import LocalProvider
from src.core.metrics import (
    AI_REQUESTS_TOTAL,
    AI_FALLBACKS_TOTAL,
    AI_COST_ESTIMATE_TOTAL,
    AI_LATENCY_MS,
    AI_PROVIDER_ERROR_TOTAL
)

logger = logging.getLogger(__name__)

# Lock to ensure thread-safe in-memory circuit breaker and cost limits
_state_lock = threading.Lock()

# Thread-safe in-memory health/cost registry for fallback when Redis is offline
_in_memory_consecutive_failures = 0
_in_memory_circuit_open_until = 0.0
_in_memory_daily_cost = 0.0
_in_memory_daily_cost_date = ""

class AIOrchestrator:
    """
    Multi-Model AI Orchestrator coordinating all LLM providers.
    Provides exponential retry, health circuit breakers, and budget control.
    """

    def __init__(self):
        self.openai_provider = OpenAIProvider()
        self.local_provider = LocalProvider()
        # Allows swapping providers in tests
        self._provider_registry: Dict[str, BaseAIProvider] = {
            "openai": self.openai_provider,
            "local": self.local_provider
        }

    def register_provider(self, name: str, provider: BaseAIProvider):
        """Helper to inject mock providers for testing."""
        self._provider_registry[name] = provider

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any] = None,
        bypass_openai: bool = False
    ) -> AIProviderResult:
        """
        Routes the chat prompt using primary or fallback providers safely.
        """
        model_config = model_config or {}
        primary = settings.AI_PRIMARY_PROVIDER
        fallback = settings.AI_FALLBACK_PROVIDER
        
        # 1. Cost limit check
        if self._is_daily_cost_limit_exceeded():
            logger.warning("AI_ORCHESTRATOR | Daily cost budget limit exceeded! Falling back to local deterministic model.")
            # Trigger fallback
            return self._execute_fallback(messages, model_config, "cost_limit_exceeded")

        # 2. Check OpenAI circuit breaker / API key presence
        is_openai_primary = (primary == "openai")
        if bypass_openai or (is_openai_primary and not settings.OPENAI_API_KEY) or self._is_circuit_open():
            if self._is_circuit_open():
                reason = "circuit_breaker_open"
            elif is_openai_primary and not settings.OPENAI_API_KEY:
                reason = "api_key_missing"
            else:
                reason = "bypass_openai"
            logger.info("AI_ORCHESTRATOR | OpenAI bypassed! Reason: %s", reason)
            return self._execute_fallback(messages, model_config, reason)

        # 3. Primary Execution with Retries & Backoff
        max_retries = settings.AI_MAX_RETRIES
        primary_provider = self._provider_registry.get(primary, self.openai_provider)
        
        last_exception = None
        attempt = 0
        
        while attempt <= max_retries:
            attempt += 1
            start_time = time.time()
            try:
                # Call primary provider
                res = primary_provider.generate(messages, model_config)
                
                # Success -> record metrics and reset failures
                latency_ms = (time.time() - start_time) * 1000.0
                self._record_success(res, latency_ms)
                return res
            except Exception as e:
                last_exception = e
                latency_ms = (time.time() - start_time) * 1000.0
                
                # Increment error counters (low-cardinality label)
                AI_PROVIDER_ERROR_TOTAL.labels(provider=primary, error_type=type(e).__name__).inc()
                
                logger.warning(
                    "AI_ORCHESTRATOR | Primary provider '%s' failed (Attempt %d/%d). Error: %s",
                    primary, attempt, max_retries + 1, e
                )
                
                # Linear/Exponential backoff delay (max 1 second delay to bound wait)
                if attempt <= max_retries:
                    sleep_sec = min(1.0, 0.2 * (2 ** (attempt - 1)))
                    time.sleep(sleep_sec)

        # All retries failed -> trip circuit breaker and execute fallback
        self._record_failure()
        logger.error(
            "AI_ORCHESTRATOR | Primary provider '%s' completely failed after %d attempts. Switching to fallback.",
            primary, max_retries + 1
        )
        AI_FALLBACKS_TOTAL.labels(from_provider=primary, to_provider=fallback).inc()
        
        return self._execute_fallback(messages, model_config, f"primary_failed: {type(last_exception).__name__}")

    # ── Fallback Execution ──────────────────────────────────────────────────

    def _execute_fallback(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any],
        reason: str
    ) -> AIProviderResult:
        fallback = settings.AI_FALLBACK_PROVIDER
        fallback_provider = self._provider_registry.get(fallback, self.local_provider)
        
        start_time = time.time()
        res = fallback_provider.generate(messages, model_config)
        res.fallback_used = True
        res.error = reason
        
        latency_ms = (time.time() - start_time) * 1000.0
        
        # Record fallback metrics
        AI_REQUESTS_TOTAL.labels(
            provider=res.provider,
            model=res.model,
            status="fallback_success"
        ).inc()
        AI_LATENCY_MS.labels(provider=res.provider, model=res.model).observe(latency_ms)
        
        return res

    # ── Health & Circuit Breaker Logic (Redis + In-Memory Fallback) ─────────

    def _is_circuit_open(self) -> bool:
        """Determines if the primary provider circuit breaker is open (tripped)."""
        now = time.time()
        
        # Try Redis first
        try:
            from src.core.redis_client import redis_client
            r = redis_client.client
            if r:
                open_until = r.get("ai_orchestrator:openai_circuit_open_until")
                if open_until and float(open_until) > now:
                    return True
                return False
        except Exception:
            # Fall back to Redis connection loss logger
            pass

        # Fallback to in-memory state
        with _state_lock:
            return _in_memory_circuit_open_until > now

    def _record_success(self, res: AIProviderResult, latency_ms: float):
        """Records a successful primary request, resetting health metrics."""
        # 1. Prometheus Telemetry
        AI_REQUESTS_TOTAL.labels(provider=res.provider, model=res.model, status="success").inc()
        AI_COST_ESTIMATE_TOTAL.labels(provider=res.provider, model=res.model).inc(res.cost_estimate)
        AI_LATENCY_MS.labels(provider=res.provider, model=res.model).observe(latency_ms)

        # 2. Reset circuit failures & Accumulate Cost in Redis
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            from src.core.redis_client import redis_client
            r = redis_client.client
            if r:
                r.set("ai_orchestrator:openai_consecutive_failures", 0)
                r.incrbyfloat(f"ai_orchestrator:daily_cost:{today}", res.cost_estimate)
                r.expire(f"ai_orchestrator:daily_cost:{today}", 86400 * 2) # 2 days TTL
                return
        except Exception:
            pass

        # In-memory fallback
        global _in_memory_consecutive_failures, _in_memory_daily_cost, _in_memory_daily_cost_date
        with _state_lock:
            _in_memory_consecutive_failures = 0
            if _in_memory_daily_cost_date != today:
                _in_memory_daily_cost_date = today
                _in_memory_daily_cost = 0.0
            _in_memory_daily_cost += res.cost_estimate

    def _record_failure(self):
        """Records a primary provider execution failure, checking circuit limits."""
        # Trip threshold
        now = time.time()
        
        # Try Redis
        try:
            from src.core.redis_client import redis_client
            r = redis_client.client
            if r:
                fails = r.incr("ai_orchestrator:openai_consecutive_failures")
                if fails >= 3:
                    # Trip circuit for 5 minutes (300 seconds)
                    r.setex("ai_orchestrator:openai_circuit_open_until", 300, str(now + 300.0))
                    logger.critical("AI_ORCHESTRATOR | Circuit Breaker TRIPPED for OpenAI provider! Blocked for 5 minutes.")
                return
        except Exception:
            pass

        # In-memory fallback
        global _in_memory_consecutive_failures, _in_memory_circuit_open_until
        with _state_lock:
            _in_memory_consecutive_failures += 1
            if _in_memory_consecutive_failures >= 3:
                _in_memory_circuit_open_until = now + 300.0
                logger.critical("AI_ORCHESTRATOR | In-Memory Circuit Breaker TRIPPED for OpenAI provider! Blocked for 5 minutes.")

    # ── Cost Limit Checking ─────────────────────────────────────────────────

    def _is_daily_cost_limit_exceeded(self) -> bool:
        """Enforces daily API cost limits to prevent budget runaways."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        limit = settings.AI_COST_LIMIT_DAILY

        # Try Redis
        try:
            from src.core.redis_client import redis_client
            r = redis_client.client
            if r:
                cost_str = r.get(f"ai_orchestrator:daily_cost:{today}")
                if cost_str and float(cost_str) >= limit:
                    return True
                return False
        except Exception:
            pass

        # In-memory fallback
        global _in_memory_daily_cost, _in_memory_daily_cost_date
        with _state_lock:
            if _in_memory_daily_cost_date != today:
                _in_memory_daily_cost_date = today
                _in_memory_daily_cost = 0.0
            return _in_memory_daily_cost >= limit
            
    def get_circuit_open_until(self) -> float:
        """Returns the timestamp until which the circuit is open (for health check)."""
        # Try Redis
        try:
            from src.core.redis_client import redis_client
            r = redis_client.client
            if r:
                val = r.get("ai_orchestrator:openai_circuit_open_until")
                if val:
                    return float(val)
        except Exception:
            pass
            
        with _state_lock:
            return _in_memory_circuit_open_until
