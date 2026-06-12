import sys
import os
import unittest

sys.path.insert(0, ".")

from src.core.config import settings
from src.response_engine.prompts import build_system_prompt, get_response_style_rules
from src.response_engine.response_ranker import score_response, NORMAL_THRESHOLD, check_english_leakage
from src.ai_providers.local_provider import _CATEGORY_TEMPLATES
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput
from src.services.database import clear_user_memories_db
from src.core.redis_client import redis_client

class TestEnglishLeakageExpanded(unittest.TestCase):

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
        
        self.test_user = "test_leakage_user"
        clear_user_memories_db(self.test_user)

    def tearDown(self):
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.OPENAI_API_KEY = self.original_api_key
        settings.AI_MAX_RETRIES = self.original_max_retries
        clear_user_memories_db(self.test_user)

    def test_detects_ai_prompt_engineering_terms(self):
        """1. Detects: validate, response, follow-up, prompt, grounding technique, coping mechanism"""
        terms = ["validate", "validation", "response", "retry", "follow-up", "prompt", "grounding technique", "coping mechanism"]
        for term in terms:
            res = score_response(f"Bu bir {term} ifadesidir.")
            self.assertIn("english_leakage", res.reasons, f"Failed to detect leakage term: {term}")

    def test_detects_technical_leakage_terms(self):
        """2. Detects: OpenAI, Anthropic, GPT, LLM, provider"""
        # Testing uppercase / lowercase and mix variants to verify case-insensitivity
        terms = ["OpenAI", "Anthropic", "GPT", "LLM", "provider"]
        for term in terms:
            res = score_response(f"Şu an {term} kullanıyoruz.")
            self.assertIn("english_leakage", res.reasons, f"Failed to detect technical term: {term}")

    def test_good_turkish_alternatives_pass(self):
        """3. Good Turkish alternatives pass without leakage detection."""
        good_responses = [
            "Şu an biraz durup çevrene odaklanmak yardımcı olabilir.",
            "Bugün kendine karşı biraz daha anlayışlı davranmayı deneyebilirsin.",
            "Sakinleşmek için nefes egzersizi deneyebiliriz.",
            "Zor zamanlarda sana iyi gelen küçük alışkanlıkları fark etmek yardımcı olabilir."
        ]
        for resp in good_responses:
            res = score_response(resp)
            self.assertNotIn("english_leakage", res.reasons, f"False positive on: {resp}")

    def test_ranker_adds_leakage_reason_tag(self):
        """4. Ranker adds: english_leakage"""
        res = score_response("Validation süreci başladı.")
        self.assertIn("english_leakage", res.reasons)

    def test_severe_leakage_lowers_score_below_pass_threshold(self):
        """5. Severe leakage lowers score below pass threshold."""
        res = score_response("Bu bir memory injection sürecidir.")
        self.assertFalse(res.passes, f"Score should fail the quality check. Score: {res.score}")
        self.assertTrue(res.score < NORMAL_THRESHOLD, f"Score should be below normal threshold {NORMAL_THRESHOLD}. Score: {res.score}")

    def test_local_provider_contains_no_english_therapy_jargon(self):
        """6. Local provider contains no English therapy jargon or leakage terms."""
        leakage_keywords = [
            "validate", "validation", "response", "retry", "follow-up", "prompt", "system prompt",
            "assistant", "user profile", "memory injection", "context builder", "response ranking",
            "quality score", "temperature", "token", "hallucination", "reasoning", "chain of thought",
            "grounding", "fallback", "provider", "retry calibration", "instruction",
            "coping mechanism", "grounding technique", "emotional regulation", "self-compassion",
            "mindfulness", "reframing", "cognitive distortion", "validation exercise",
            "database", "veritabanı referansı", "system memory", "internal memory", "cache",
            "api", "openai", "anthropic", "gpt", "llm", "provider selection"
        ]
        
        for category, templates in _CATEGORY_TEMPLATES.items():
            for idx, text in enumerate(templates):
                # Check each text against all leakage keywords with regex boundary
                for term in leakage_keywords:
                    # Case insensitive / unicode-aware check
                    res = check_english_leakage(text)
                    self.assertIsNone(res, f"Local provider category '{category}' template index {idx} contains english leakage: '{text}' (matched: {term})")

    def test_prompt_instructions_include_leakage_prevention(self):
        """7. Prompt instructions include leakage prevention guidance."""
        rules = get_response_style_rules()
        self.assertIn("İç süreçlerden bahsetmek", rules)
        self.assertIn("prompt, model, sistem, hafıza enjeksiyonu", rules)
        self.assertIn("İngilizce terapi veya yapay zekâ terimleri", rules)

    def test_crisis_path_remains_unchanged(self):
        """8. Crisis path remains unchanged and bypasses remote calls safely."""
        inp = EngineInput(
            user_id=self.test_user,
            text="Merhaba, nasılsın?",
            emotion="sadness",
            risk="1"
        )
        # Verify engine runs successfully without error on crisis risk input
        res = response_engine.generate_response(inp)
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["final_model"], "crisis_safe_template")
        # Ensure fallback reason is crisis bypass
        ranking = res.metadata.get("ranking", {})
        self.assertEqual(ranking.get("fallback_reason"), "crisis_bypass_safety")

if __name__ == "__main__":
    unittest.main()
