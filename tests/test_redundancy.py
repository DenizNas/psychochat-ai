import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, ".")

from src.core.config import settings
from src.ai_providers import ai_orchestrator
from src.ai_providers.mock_provider import MockProvider
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
import src.ai_providers.orchestrator as orch

class MockNamedProvider(MockProvider):
    def __init__(self, provider_name: str, **kwargs):
        super().__init__(**kwargs)
        self.provider_name = provider_name

    def generate(self, messages, model_config):
        res = super().generate(messages, model_config)
        res.provider = self.provider_name
        return res

class TestLLMRedundancy(unittest.TestCase):

    def setUp(self):
        # Backup original settings
        self.original_primary_provider = settings.AI_PRIMARY_PROVIDER
        self.original_secondary_provider = settings.AI_SECONDARY_PROVIDER
        self.original_fallback_provider = settings.AI_FALLBACK_PROVIDER
        self.original_primary_model = settings.AI_PRIMARY_MODEL
        self.original_fallback_model = settings.AI_FALLBACK_MODEL
        self.original_anthropic_model = settings.ANTHROPIC_MODEL
        self.original_ollama_model = settings.OLLAMA_MODEL
        self.original_timeout = settings.AI_TIMEOUT_SECONDS
        self.original_max_retries = settings.AI_MAX_RETRIES
        self.original_cost_limit = settings.AI_COST_LIMIT_DAILY
        self.original_openai_key = settings.OPENAI_API_KEY
        self.original_anthropic_key = settings.ANTHROPIC_API_KEY

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
        ai_orchestrator.register_provider("anthropic", ai_orchestrator.anthropic_provider)
        ai_orchestrator.register_provider("ollama", ai_orchestrator.ollama_provider)

    def tearDown(self):
        # Restore settings
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.AI_SECONDARY_PROVIDER = self.original_secondary_provider
        settings.AI_FALLBACK_PROVIDER = self.original_fallback_provider
        settings.AI_PRIMARY_MODEL = self.original_primary_model
        settings.AI_FALLBACK_MODEL = self.original_fallback_model
        settings.ANTHROPIC_MODEL = self.original_anthropic_model
        settings.OLLAMA_MODEL = self.original_ollama_model
        settings.AI_TIMEOUT_SECONDS = self.original_timeout
        settings.AI_MAX_RETRIES = self.original_max_retries
        settings.AI_COST_LIMIT_DAILY = self.original_cost_limit
        settings.OPENAI_API_KEY = self.original_openai_key
        settings.ANTHROPIC_API_KEY = self.original_anthropic_key

        # Re-register standard providers
        ai_orchestrator.register_provider("openai", ai_orchestrator.openai_provider)
        ai_orchestrator.register_provider("local", ai_orchestrator.local_provider)
        ai_orchestrator.register_provider("anthropic", ai_orchestrator.anthropic_provider)
        ai_orchestrator.register_provider("ollama", ai_orchestrator.ollama_provider)

    def test_openai_success_skips_secondary(self):
        """PROVIDER_REDUNDANCY_ADDED: Verify that secondary provider is skipped if primary succeeds."""
        # Setup mock primary (openai)
        primary_mock = MockProvider(mock_response="Primary OpenAI response succeeded.")
        ai_orchestrator.register_provider("openai", primary_mock)

        # Setup mock secondary (anthropic) which raises an error if called
        secondary_mock = MockProvider(force_error=RuntimeError("Secondary should NOT be called!"))
        ai_orchestrator.register_provider("anthropic", secondary_mock)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "anthropic"
        settings.OPENAI_API_KEY = "sk-fake-openai"
        settings.ANTHROPIC_API_KEY = "sk-fake-anthropic"

        messages = [{"role": "user", "content": "Hello."}]
        res = ai_orchestrator.generate_response(messages)

        # Verify primary was returned
        self.assertEqual(res.text, "Primary OpenAI response succeeded.")
        self.assertFalse(res.fallback_used)

    def test_openai_fail_triggers_secondary_anthropic(self):
        """OPENAI_FAILS_TO_ANTHROPIC: Verify that primary failure triggers fallback to Anthropic."""
        # Setup mock primary (openai) to fail
        primary_mock = MockProvider(force_error=RuntimeError("OpenAI API error"))
        ai_orchestrator.register_provider("openai", primary_mock)

        # Setup mock secondary (anthropic) to succeed
        secondary_mock = MockNamedProvider("anthropic", mock_response="Secondary Anthropic response succeeded.")
        ai_orchestrator.register_provider("anthropic", secondary_mock)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "anthropic"
        settings.OPENAI_API_KEY = "sk-fake-openai"
        settings.ANTHROPIC_API_KEY = "sk-fake-anthropic"
        settings.AI_MAX_RETRIES = 0  # speed up failures

        messages = [{"role": "user", "content": "Hello."}]
        res = ai_orchestrator.generate_response(messages)

        # Verify fallback to Anthropic
        self.assertEqual(res.text, "Secondary Anthropic response succeeded.")
        self.assertTrue(res.fallback_used)
        self.assertEqual(res.provider, "anthropic")
        self.assertIn("primary_failed", res.error)

    def test_openai_fail_triggers_secondary_ollama(self):
        """PROVIDER_REDUNDANCY_ADDED: Verify primary failure triggers Ollama if configured as secondary."""
        # Setup mock primary (openai) to fail
        primary_mock = MockProvider(force_error=RuntimeError("OpenAI API error"))
        ai_orchestrator.register_provider("openai", primary_mock)

        # Setup mock secondary (ollama) to succeed
        secondary_mock = MockNamedProvider("ollama", mock_response="Secondary Ollama response succeeded.")
        ai_orchestrator.register_provider("ollama", secondary_mock)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "ollama"
        settings.OPENAI_API_KEY = "sk-fake-openai"
        settings.AI_MAX_RETRIES = 0

        messages = [{"role": "user", "content": "Hello."}]
        res = ai_orchestrator.generate_response(messages)

        # Verify fallback to Ollama
        self.assertEqual(res.text, "Secondary Ollama response succeeded.")
        self.assertTrue(res.fallback_used)
        self.assertEqual(res.provider, "ollama")

    def test_both_remote_providers_fail_falls_back_to_local(self):
        """ANTHROPIC_FAILS_TO_LOCAL: Verify fallback to LocalProvider if both OpenAI and Anthropic fail."""
        # Setup mock primary (openai) to fail
        primary_mock = MockProvider(force_error=RuntimeError("OpenAI API error"))
        ai_orchestrator.register_provider("openai", primary_mock)

        # Setup mock secondary (anthropic) to fail
        secondary_mock = MockProvider(force_error=RuntimeError("Anthropic API error"))
        ai_orchestrator.register_provider("anthropic", secondary_mock)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "anthropic"
        settings.AI_FALLBACK_PROVIDER = "local"
        settings.OPENAI_API_KEY = "sk-fake-openai"
        settings.ANTHROPIC_API_KEY = "sk-fake-anthropic"
        settings.AI_MAX_RETRIES = 0

        messages = [{"role": "user", "content": "Nasılsın?"}]
        res = ai_orchestrator.generate_response(messages)

        # Verify fallback to local provider templates
        self.assertTrue(res.fallback_used)
        self.assertEqual(res.provider, "local")
        self.assertIn("secondary_failed", res.error)

    def test_secondary_disabled_falls_back_instantly(self):
        """PROVIDER_REDUNDANCY_ADDED: Verify secondary disabled skips secondary and goes to LocalProvider."""
        primary_mock = MockProvider(force_error=RuntimeError("OpenAI API error"))
        ai_orchestrator.register_provider("openai", primary_mock)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "none"
        settings.AI_FALLBACK_PROVIDER = "local"
        settings.OPENAI_API_KEY = "sk-fake-openai"
        settings.AI_MAX_RETRIES = 0

        messages = [{"role": "user", "content": "Merhaba."}]
        res = ai_orchestrator.generate_response(messages)

        self.assertTrue(res.fallback_used)
        self.assertEqual(res.provider, "local")

    def test_privacy_mode_remote_bypass(self):
        """PRIVACY_MODE_REMOTE_BYPASS: Verify remote providers are bypassed in privacy mode."""
        # Mock primary (openai) and secondary (anthropic)
        primary_mock = MockNamedProvider("openai", mock_response="OpenAI response.")
        secondary_mock = MockNamedProvider("anthropic", mock_response="Anthropic response.")
        ai_orchestrator.register_provider("openai", primary_mock)
        ai_orchestrator.register_provider("anthropic", secondary_mock)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "anthropic"
        settings.AI_FALLBACK_PROVIDER = "local"

        messages = [{"role": "user", "content": "Merhaba."}]

        # 1. With remote secondary (anthropic), it should go straight to local templates
        res = ai_orchestrator.generate_response(messages, bypass_openai=True)
        self.assertEqual(res.provider, "local")

        # 2. With local secondary (ollama), it should route to ollama
        ollama_mock = MockNamedProvider("ollama", mock_response="Ollama local response.")
        ai_orchestrator.register_provider("ollama", ollama_mock)
        settings.AI_SECONDARY_PROVIDER = "ollama"

        res_local = ai_orchestrator.generate_response(messages, bypass_openai=True)
        self.assertEqual(res_local.provider, "ollama")
        self.assertEqual(res_local.text, "Ollama local response.")

    def test_crisis_path_bypasses_all_llms(self):
        """CRISIS_PATH_BYPASSES_ALL_LLMS: Verify crisis path bypasses all LLMs completely."""
        # Register failing mock providers for OpenAI and Anthropic
        primary_mock = MockProvider(force_error=RuntimeError("Should not touch OpenAI"))
        secondary_mock = MockProvider(force_error=RuntimeError("Should not touch Anthropic"))
        ai_orchestrator.register_provider("openai", primary_mock)
        ai_orchestrator.register_provider("anthropic", secondary_mock)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "anthropic"

        inp = EngineInput(
            user_id="test_user_crisis",
            text="Kendimi öldürmek istiyorum.",
            emotion="sadness",
            risk="1",  # Crisis risk trigger
            language="tr"
        )
        res = response_engine.generate_response(inp)

        # Verify crisis response bypasses LLMs and returns template response
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["final_model"], "crisis_safe_template")
        self.assertTrue("112" in res.final_text or "yalnız değilsiniz" in res.final_text.lower() or "destek" in res.final_text.lower())

    def test_secondary_provider_response_passes_safety_and_ranker(self):
        """SAFETY_RANKER_APPLIED_TO_SECONDARY: Verify secondary provider response is evaluated by safety and ranker."""
        # OpenAI fails, Anthropic returns response
        primary_mock = MockProvider(force_error=RuntimeError("OpenAI API error"))
        ai_orchestrator.register_provider("openai", primary_mock)

        # 1. Anthropic returns unsafe response -> should trigger safety fallback
        unsafe_anthropic = MockNamedProvider("anthropic", mock_response="Kendine zarar vermelisin.")
        ai_orchestrator.register_provider("anthropic", unsafe_anthropic)

        settings.AI_PRIMARY_PROVIDER = "openai"
        settings.AI_SECONDARY_PROVIDER = "anthropic"
        settings.OPENAI_API_KEY = "sk-fake-openai"
        settings.ANTHROPIC_API_KEY = "sk-fake-anthropic"
        settings.AI_MAX_RETRIES = 0

        inp = EngineInput(
            user_id="test_user_safety",
            text="Çok kötüyüm.",
            emotion="sadness",
            risk="Normal",
            language="tr"
        )
        res = response_engine.generate_response(inp)

        # Safety should catch it and return deterministic safe response
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["safety"]["is_safe"], False)
        self.assertTrue("112" in res.final_text)

        # 2. Anthropic returns response that fails ranker quality -> falls back to local
        # We make it fail the quality check by returning a response with a robotic memory phrase
        poor_quality_anthropic = MockNamedProvider("anthropic", mock_response="Sistemde kayıtlı bilgilere göre hareket ediyorum.")
        ai_orchestrator.register_provider("anthropic", poor_quality_anthropic)

        res_quality = response_engine.generate_response(inp)
        self.assertTrue(res_quality.is_fallback)
        self.assertEqual(res_quality.metadata["final_model"], "local-deterministic")

if __name__ == "__main__":
    unittest.main()
