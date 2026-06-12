import sys
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

sys.path.insert(0, ".")

from src.core.config import settings
from src.response_engine.prompts import build_system_prompt, build_retry_quality_instruction
from src.response_engine.response_ranker import score_response
from src.ai_providers import ai_orchestrator
from src.ai_providers.mock_provider import MockProvider
from src.ai_providers.base import AIProviderResult
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
from src.services.database import clear_user_memories_db
from src.core.redis_client import redis_client

class CustomStatefulMockProvider:
    """Mock provider to simulate stateful responses across multiple attempts for testing retry prompt injection."""
    def __init__(self):
        self.calls = []

    def generate(self, messages, model_config):
        self.calls.append(messages)
        # First call returns response that fails quality (bullet points)
        if len(self.calls) == 1:
            return AIProviderResult(
                text="Sana bazı önerilerde bulunmak isterim:\n- Derin nefes al.\n- Günlük tutmayı dene.\n- Yürüyüşe çık.",
                provider="mock",
                model="mock-stateful",
                latency_ms=1.0,
                token_estimate=20,
                cost_estimate=0.001,
                finish_reason="stop",
                fallback_used=False,
                error=None
            )
        # Second call returns response that passes quality
        return AIProviderResult(
            text="Yaşadığın bu sıkıntılı durum seni gerçekten bunaltmış görünüyor, duygularını paylaşmakta son derece haklısın.",
            provider="mock",
            model="mock-stateful",
            latency_ms=1.0,
            token_estimate=20,
            cost_estimate=0.001,
            finish_reason="stop",
            fallback_used=False,
            error=None
        )

class TestQualityRetryCalibration(unittest.TestCase):

    def setUp(self):
        self.original_primary_provider = settings.AI_PRIMARY_PROVIDER
        self.original_api_key = settings.OPENAI_API_KEY
        self.original_max_retries = settings.AI_MAX_RETRIES
        
        # Disable Redis connection attempts to make unit tests run instantly
        redis_client._client = False

        # Force offline fast fallback/mocking setup
        settings.AI_PRIMARY_PROVIDER = "mock_provider"
        settings.OPENAI_API_KEY = ""
        settings.AI_MAX_RETRIES = 0
        
        self.test_user = "test_retry_user"
        clear_user_memories_db(self.test_user)

    def tearDown(self):
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.OPENAI_API_KEY = self.original_api_key
        settings.AI_MAX_RETRIES = self.original_max_retries
        clear_user_memories_db(self.test_user)
        # Reset standard provider registry
        ai_orchestrator.register_provider("openai", ai_orchestrator.openai_provider)
        ai_orchestrator.register_provider("local", ai_orchestrator.local_provider)

    def test_build_retry_quality_instruction_too_many_bullets(self):
        """1. build_retry_quality_instruction maps too_many_bullets correctly."""
        instr = build_retry_quality_instruction(["too_many_bullets"])
        self.assertIn("Madde işaretleri kullanma", instr)
        self.assertIn("cevabı doğal paragraflarla ver", instr)

    def test_multiple_reason_tags_combine_concisely(self):
        """2. Multiple reason tags combine into concise Turkish instruction."""
        instr = build_retry_quality_instruction(["too_many_bullets", "too_many_questions"])
        self.assertIn("Önceki taslak bazı kalite kriterlerini karşılamadı.", instr)
        self.assertIn("Madde işaretleri kullanma", instr)
        self.assertIn("En fazla bir açık uçlu soru sor.", instr)

    def test_unknown_reason_tags_ignored_safely(self):
        """3. Unknown reason tags are ignored safely."""
        instr = build_retry_quality_instruction(["too_many_bullets", "some_random_tag", "another_unknown"])
        self.assertIn("Madde işaretleri kullanma", instr)
        # Ensure unknown tags are not present or didn't throw exceptions
        self.assertNotIn("some_random_tag", instr)
        self.assertNotIn("another_unknown", instr)

        # All unknown tags result in empty instruction
        instr_empty = build_retry_quality_instruction(["unknown1", "unknown2"])
        self.assertEqual(instr_empty, "")

    def test_retry_instruction_no_english_leakage(self):
        """4. Retry instruction does not contain English leakage."""
        for tag in ["too_many_bullets", "too_many_questions", "generic_response", 
                    "robotic_memory_phrase", "unnatural_turkish", "repeated_advice", 
                    "overused_suggestion", "too_short", "english_leakage", 
                    "empty_response", "repetitive", "context_mismatch"]:
            instr = build_retry_quality_instruction([tag])
            english_words = ["bullet", "point", "question", "generic", "response", "robotic", "unnatural", "advice", "suggestion", "leakage"]
            for word in english_words:
                self.assertNotIn(word, instr.lower(), f"English word '{word}' leaked in instruction for tag '{tag}': {instr}")

    def test_engine_injects_retry_only_on_second_attempt(self):
        """5. Engine injects retry instruction only on second attempt, not first."""
        stateful_mock = CustomStatefulMockProvider()
        ai_orchestrator.register_provider("mock_provider", stateful_mock)
        
        inp = EngineInput(
            user_id=self.test_user,
            text="Okul stresi beni eziyor.",
            emotion="stress",
            risk="Normal"
        )
        
        res = response_engine.generate_response(inp)
        
        # Verify exactly 2 generate calls were recorded in stateful mock
        self.assertEqual(len(stateful_mock.calls), 2)
        
        first_call_system_prompt = stateful_mock.calls[0][0]["content"]
        second_call_system_prompt = stateful_mock.calls[1][0]["content"]
        
        # 1st attempt should NOT have retry instructions
        self.assertNotIn("KALİTE DÜZELTME TALİMATI", first_call_system_prompt)
        
        # 2nd attempt MUST have quality calibration retry instructions
        self.assertIn("KALİTE DÜZELTME TALİMATI", second_call_system_prompt)
        self.assertIn("Madde işaretleri kullanma", second_call_system_prompt)
        self.assertTrue(res.metadata["ranking"]["retry_count"] == 1)

    def test_retry_count_remains_exactly_1(self):
        """6. Retry count remains exactly 1, fallbacks to local provider if retry fails quality."""
        # Stateful mock that always returns low quality (bullets)
        always_fail_provider = MockProvider(
            mock_response="- Madde 1.\n- Madde 2.\n- Madde 3." # fails ranker
        )
        ai_orchestrator.register_provider("mock_provider", always_fail_provider)
        
        inp = EngineInput(
            user_id=self.test_user,
            text="Çok kötüyüm.",
            emotion="sadness",
            risk="Normal"
        )
        
        res = response_engine.generate_response(inp)
        
        # Verify retry_count is exactly 1 in metadata
        self.assertEqual(res.metadata["ranking"]["retry_count"], 1)
        # Verification that fallback to local provider was used after retry failed
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["final_model"], "local-deterministic")

    def test_crisis_path_does_not_use_retry_calibration(self):
        """7. Crisis path bypasses retry calibration entirely."""
        always_fail_provider = MockProvider(
            mock_response="İntihar etmek istiyorum."
        )
        ai_orchestrator.register_provider("mock_provider", always_fail_provider)
        
        # When risk="1" (crisis), it bypasses prompt calibration completely
        inp = EngineInput(
            user_id=self.test_user,
            text="Hayatıma son vereceğim.",
            emotion="sadness",
            risk="1"
        )
        
        res = response_engine.generate_response(inp)
        ranking = res.metadata.get("ranking", {})
        self.assertEqual(ranking.get("retry_count", 0), 0)
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["final_model"], "crisis_safe_template")

    def test_existing_ranker_tests_still_pass(self):
        """8. Existing ranker scoring returns valid results and passes normal expectations."""
        # Simple test to verify score_response API signature
        res = score_response("Seni çok iyi anlıyorum. Paylaştığın için teşekkür ederim.", emotion="sadness")
        self.assertTrue(res.passes)
        self.assertTrue(res.score > 0.8)

if __name__ == "__main__":
    unittest.main()
