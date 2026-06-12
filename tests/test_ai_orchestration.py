import sys
import os
import unittest
import time
from datetime import datetime, timezone

sys.path.insert(0, ".")

from src.core.config import settings
from src.ai_providers import ai_orchestrator
from src.ai_providers.mock_provider import MockProvider
from src.ai_providers.local_provider import LocalProvider
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
import src.ai_providers.orchestrator as orch

class TestAIOrchestration(unittest.TestCase):

    def setUp(self):
        # Backup original settings
        self.original_primary_provider = settings.AI_PRIMARY_PROVIDER
        self.original_secondary_provider = settings.AI_SECONDARY_PROVIDER
        self.original_fallback_provider = settings.AI_FALLBACK_PROVIDER
        self.original_primary_model = settings.AI_PRIMARY_MODEL
        self.original_fallback_model = settings.AI_FALLBACK_MODEL
        self.original_timeout = settings.AI_TIMEOUT_SECONDS
        self.original_max_retries = settings.AI_MAX_RETRIES
        self.original_cost_limit = settings.AI_COST_LIMIT_DAILY
        self.original_api_key = settings.OPENAI_API_KEY

        # Disable secondary provider for legacy orchestrator tests
        settings.AI_SECONDARY_PROVIDER = "none"

        # Reset orchestrator internal in-memory state
        orch._in_memory_consecutive_failures = 0
        orch._in_memory_circuit_open_until = 0.0
        orch._in_memory_daily_cost = 0.0
        orch._in_memory_daily_cost_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Clear Redis state if Redis is active
        try:
            from src.core.redis_client import redis_client
            r = redis_client.client
            if r:
                r.delete("ai_orchestrator:openai_consecutive_failures")
                r.delete("ai_orchestrator:openai_circuit_open_until")
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                r.delete(f"ai_orchestrator:daily_cost:{today}")
        except Exception:
            pass

        # Re-register standard providers
        ai_orchestrator.register_provider("openai", ai_orchestrator.openai_provider)
        ai_orchestrator.register_provider("local", ai_orchestrator.local_provider)

    def tearDown(self):
        # Restore settings
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.AI_SECONDARY_PROVIDER = self.original_secondary_provider
        settings.AI_FALLBACK_PROVIDER = self.original_fallback_provider
        settings.AI_PRIMARY_MODEL = self.original_primary_model
        settings.AI_FALLBACK_MODEL = self.original_fallback_model
        settings.AI_TIMEOUT_SECONDS = self.original_timeout
        settings.AI_MAX_RETRIES = self.original_max_retries
        settings.AI_COST_LIMIT_DAILY = self.original_cost_limit
        settings.OPENAI_API_KEY = self.original_api_key

        # Re-register standard providers
        ai_orchestrator.register_provider("openai", ai_orchestrator.openai_provider)
        ai_orchestrator.register_provider("local", ai_orchestrator.local_provider)

    def test_openai_api_key_missing_failover(self):
        """Verify that missing OpenAI API key bypasses OpenAI calls and uses local fallback instantly."""
        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.OPENAI_API_KEY = ""  # Simulate missing key

        # Call orchestrator directly
        messages = [{"role": "user", "content": "Merhaba, canım çok sıkkın."}]
        res = ai_orchestrator.generate_response(messages)

        self.assertTrue(res.fallback_used)
        self.assertEqual(res.provider, "local")
        self.assertEqual(res.model, "local-deterministic")
        self.assertEqual(res.error, "api_key_missing")

    def test_mock_provider_timeout_failover(self):
        """Verify that provider timeouts trigger seamless local failover."""
        # Set primary to mock provider with high delay
        slow_primary = MockProvider(
            mock_response="Bu yanıt gelmemeli çünkü yavaş.",
            force_error=TimeoutError("Request timed out")
        )
        ai_orchestrator.register_provider("mock_primary", slow_primary)
        
        settings.AI_PRIMARY_PROVIDER = "mock_primary"
        settings.AI_TIMEOUT_SECONDS = 0.05  # lower than mock delay
        settings.AI_MAX_RETRIES = 0  # no retries for fast test

        messages = [{"role": "user", "content": "Beni duyuyor musun?"}]
        res = ai_orchestrator.generate_response(messages, model_config={"timeout_seconds": 0.05})

        self.assertTrue(res.fallback_used)
        self.assertEqual(res.provider, "local")
        self.assertTrue("primary_failed" in res.error)

    def test_circuit_breaker_tripping(self):
        """Verify that consecutive failures trip the circuit breaker and route instantly to fallback."""
        failing_primary = MockProvider(
            force_error=RuntimeError("Connection refused by server.")
        )
        ai_orchestrator.register_provider("failing_primary", failing_primary)
        
        settings.AI_PRIMARY_PROVIDER = "failing_primary"
        settings.AI_MAX_RETRIES = 0  # speed up failures

        messages = [{"role": "user", "content": "Bağlantı hatası denemesi."}]

        # 1st failure
        res = ai_orchestrator.generate_response(messages)
        self.assertTrue(res.fallback_used)
        self.assertFalse(ai_orchestrator._is_circuit_open())

        # 2nd failure
        res = ai_orchestrator.generate_response(messages)
        self.assertTrue(res.fallback_used)
        self.assertFalse(ai_orchestrator._is_circuit_open())

        # 3rd failure - should trip
        res = ai_orchestrator.generate_response(messages)
        self.assertTrue(res.fallback_used)
        self.assertTrue(ai_orchestrator._is_circuit_open())

        # 4th request should bypass failing_primary completely and instantly fallback
        # Let's count calls to failing_primary by checking if it gets invoked.
        # We can temporarily swap its response to verify it's never run.
        failing_primary.force_error = None
        failing_primary.mock_response = "Bu kesinlikle basılmamalı!"

        res4 = ai_orchestrator.generate_response(messages)
        self.assertTrue(res4.fallback_used)
        self.assertEqual(res4.provider, "local")
        self.assertEqual(res4.error, "circuit_breaker_open")
        self.assertNotEqual(res4.text, "Bu kesinlikle basılmamalı!")

    def test_cost_limit_blocks(self):
        """Verify that exceeding the daily cost budget blocks primary calls and falls back to local."""
        expensive_primary = MockProvider(
            mock_response="Çok pahalı bir yanıt üretiyorum.",
            cost_rate=10.0  # Generates high cost based on token estimate
        )
        ai_orchestrator.register_provider("expensive_primary", expensive_primary)

        settings.AI_PRIMARY_PROVIDER = "expensive_primary"
        settings.AI_COST_LIMIT_DAILY = 5.0  # limit is 5 USD

        messages = [{"role": "user", "content": "Bütçe deneme mesajı."}]

        # First request succeeds and records high cost
        res = ai_orchestrator.generate_response(messages)
        self.assertEqual(res.provider, "mock")
        self.assertFalse(res.fallback_used)
        self.assertGreater(res.cost_estimate, 5.0)

        # Second request should be blocked by cost limit checker and failover to local
        res2 = ai_orchestrator.generate_response(messages)
        self.assertTrue(res2.fallback_used)
        self.assertEqual(res2.provider, "local")
        self.assertEqual(res2.error, "cost_limit_exceeded")

    def test_crisis_bypass_route(self):
        """Verify that crisis/suicide risks bypass remote LLMs entirely and return safe deterministic templates."""
        # Setup a mock primary that normally works
        working_primary = MockProvider(mock_response="Bu normal bir konuşma.")
        ai_orchestrator.register_provider("working_primary", working_primary)
        settings.AI_PRIMARY_PROVIDER = "working_primary"

        # 1. Normal Input
        normal_input = EngineInput(
            user_id="test_user_crisis",
            text="Merhaba nasılsın?",
            emotion="neutral",
            risk="Normal",
            language="tr"
        )
        res_normal = response_engine.generate_response(normal_input)
        self.assertEqual(res_normal.metadata["final_model"], "mock-simulator")

        # 2. Crisis Input (risk="1")
        crisis_input = EngineInput(
            user_id="test_user_crisis",
            text="Artık yaşamak istemiyorum, her şeyi sonlandıracağım.",
            emotion="sadness",
            risk="1",
            language="tr"
        )
        res_crisis = response_engine.generate_response(crisis_input)
        
        # Verify crisis safety template is used
        self.assertTrue(res_crisis.is_fallback)
        self.assertEqual(res_crisis.metadata["final_model"], "crisis_safe_template")
        self.assertTrue("112" in res_crisis.final_text or "yalnız değilsiniz" in res_crisis.final_text.lower() or "destek" in res_crisis.final_text.lower())

    def test_predict_response_schema_contract(self):
        """Verify that response matches the exact JSON contract of /predict response without breaking Android client."""
        working_primary = MockProvider(mock_response="Empatik ve nazik bir asistan yanıtı. Harika hissetmene sevindim.")
        ai_orchestrator.register_provider("working_primary", working_primary)
        settings.AI_PRIMARY_PROVIDER = "working_primary"

        inp = EngineInput(
            user_id="test_user_schema",
            text="Kendimi bugün çok huzurlu hissediyorum.",
            emotion="joy",
            risk="Normal",
            language="tr"
        )

        res = response_engine.generate_response(inp)

        # Check required root properties of /predict response contract
        self.assertTrue(hasattr(res, "final_text"))
        self.assertTrue(hasattr(res, "is_fallback"))
        self.assertTrue(hasattr(res, "metadata"))

        self.assertIsInstance(res.final_text, str)
        self.assertIsInstance(res.is_fallback, bool)
        self.assertIsInstance(res.metadata, dict)

        # Check required metadata fields that existing workflows / clients might depend on
        self.assertIn("latency_sec", res.metadata)
        self.assertIn("final_model", res.metadata)
        self.assertIn("safety", res.metadata)
        self.assertIn("memory", res.metadata)
        self.assertIn("preferences", res.metadata)

        # Make sure values are populated correctly
        self.assertEqual(res.metadata["final_model"], "mock-simulator")
        self.assertTrue(res.metadata["safety"]["is_safe"])

if __name__ == "__main__":
    unittest.main()
