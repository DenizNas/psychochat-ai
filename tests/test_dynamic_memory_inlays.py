import sys
import os
import unittest

sys.path.insert(0, ".")

from src.core.config import settings
from src.ai_providers.local_provider import LocalProvider, sanitize_memory_inlay, _CATEGORY_TEMPLATES
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput
from src.services.database import clear_user_memories_db, get_or_create_profile, update_user_profile
from src.response_engine.memory_profile import load_profile, save_profile
from src.core.redis_client import redis_client

class TestDynamicMemoryInlays(unittest.TestCase):

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
        
        self.test_user = "test_inlay_user"
        clear_user_memories_db(self.test_user)
        
        # Reset profile database entry
        profile = get_or_create_profile(self.test_user)
        update_user_profile(self.test_user, {"display_name": "Deniz"})
        
        # Clear profile json
        p_json = load_profile(self.test_user)
        p_json["stressors"] = []
        p_json["goals"] = []
        p_json["recurring_emotions"] = []
        p_json["last_advice_topics"] = []
        save_profile(self.test_user, p_json)

    def tearDown(self):
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.OPENAI_API_KEY = self.original_api_key
        settings.AI_MAX_RETRIES = self.original_max_retries
        clear_user_memories_db(self.test_user)

    def test_sanitize_memory_inlay_removes_unsafe_terms(self):
        """1. sanitize_memory_inlay removes unsafe/private terms."""
        unsafe_values = [
            "intihar etmeyi düşünüyorum",
            "kanser teşhisi aldım",
            "lgbt bireyim",
            "chp üyesiyim",
            "camide ibadet ederim",
            "bipolar bozukluğum var"
        ]
        for val in unsafe_values:
            san = sanitize_memory_inlay(val)
            self.assertEqual(san, "", f"Value was not blocked: {val}")

    def test_sanitize_memory_inlay_length_limits(self):
        """2. sanitize_memory_inlay length-limits long values."""
        long_val = "A" * 150
        san = sanitize_memory_inlay(long_val)
        self.assertTrue(len(san) <= 100, f"Expected length <= 100, got: {len(san)}")
        self.assertTrue(san.endswith("..."), "Expected truncated indicator")

    def test_local_provider_uses_display_name_naturally(self):
        """3. LocalProvider uses display_name naturally when provided."""
        lp = LocalProvider()
        messages = [{"role": "user", "content": "Nasılsın?"}]
        model_config = {
            "counseling_category": "neutral",
            "safe_memory_inlays": {
                "display_name": "Deniz",
                "active_stressor": "",
                "current_goal": "",
                "recent_emotion": "",
                "last_advice_topic": ""
            }
        }
        res = lp.generate(messages, model_config)
        self.assertIn("Deniz", res.text)
        # Verify it doesn't expose system keywords
        self.assertNotIn("hafıza", res.text.lower())

    def test_local_provider_uses_active_stressor_naturally(self):
        """4. LocalProvider uses active_stressor naturally when category matches."""
        lp = LocalProvider()
        messages = [{"role": "user", "content": "Nasılsın?"}]
        model_config = {
            "counseling_category": "anxiety",
            "safe_memory_inlays": {
                "display_name": "Deniz",
                "active_stressor": "sınav",
                "current_goal": "",
                "recent_emotion": "",
                "last_advice_topic": ""
            }
        }
        res = lp.generate(messages, model_config)
        # Should combine display_name and active_stressor naturally
        self.assertIn("Deniz", res.text)
        self.assertIn("sınav", res.text)
        self.assertIn("uyumakta zorlanman", res.text)

    def test_local_provider_does_not_expose_system_phrases(self):
        """5. LocalProvider does not expose words like hafıza, veritabanı, sistem, kayıtlı, memory, database."""
        lp = LocalProvider()
        messages = [{"role": "user", "content": "Nasılsın?"}]
        model_config = {
            "counseling_category": "neutral",
            "safe_memory_inlays": {
                "display_name": "Deniz",
                "active_stressor": "hafıza kaydı", # Should be sanitized out
                "current_goal": "veritabanı temizleme", # Should be sanitized out
                "recent_emotion": "sistem hatası", # Should be sanitized out
                "last_advice_topic": "database backup" # Should be sanitized out
            }
        }
        
        # Test sanitization directly first
        self.assertEqual(sanitize_memory_inlay("hafıza kaydı"), "")
        self.assertEqual(sanitize_memory_inlay("veritabanı temizleme"), "")
        self.assertEqual(sanitize_memory_inlay("sistem hatası"), "")
        
        # Generate and check response text
        res = lp.generate(messages, model_config)
        for forbidden in ["hafıza", "veritabanı", "sistem", "kayıtlı", "memory", "database"]:
            self.assertNotIn(forbidden, res.text.lower())

    def test_local_provider_does_not_invent_context(self):
        """6. LocalProvider does not invent context when no memory exists."""
        lp = LocalProvider()
        messages = [{"role": "user", "content": "Merhaba."}]
        model_config = {
            "counseling_category": "sadness",
            "safe_memory_inlays": {
                "display_name": "",
                "active_stressor": "",
                "current_goal": "",
                "recent_emotion": "",
                "last_advice_topic": ""
            }
        }
        res = lp.generate(messages, model_config)
        # Should fallback to a standard category template
        expected_templates = _CATEGORY_TEMPLATES["sadness"]
        self.assertIn(res.text, expected_templates)

    def test_only_one_memory_inlay_appears_in_response(self):
        """7. Only one memory inlay fact (stressor, goal, emotion, or advice) appears in a response."""
        lp = LocalProvider()
        messages = [{"role": "user", "content": "Nasılsın?"}]
        model_config = {
            "counseling_category": "anxiety",
            "safe_memory_inlays": {
                "display_name": "Deniz",
                "active_stressor": "okul",
                "current_goal": "kaygıyı azaltma",
                "recent_emotion": "korku",
                "last_advice_topic": "breathing exercise"
            }
        }
        res = lp.generate(messages, model_config)
        # Based on priority, it should use active_stressor (okul) and display_name (Deniz), but not current_goal, recent_emotion, or advice_topic
        self.assertIn("Deniz", res.text)
        self.assertIn("okul", res.text)
        self.assertNotIn("kaygıyı azaltma", res.text)
        self.assertNotIn("korku", res.text)
        self.assertNotIn("nefes egzersizi", res.text)

    def test_crisis_path_does_not_use_memory_inlays(self):
        """8. Crisis path does not use memory inlays and remains deterministic."""
        # 1. Update user profile so database is populated with inlays
        update_user_profile(self.test_user, {"display_name": "Deniz"})
        p_json = load_profile(self.test_user)
        p_json["stressors"] = ["okul"]
        save_profile(self.test_user, p_json)
        
        # 2. Run engine with high crisis risk
        inp = EngineInput(
            user_id=self.test_user,
            text="Merhaba, nasılsın?",
            emotion="sadness",
            risk="1"
        )
        res = response_engine.generate_response(inp)
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["final_model"], "crisis_safe_template")
        # Crisis safe template does not contain Deniz or active_stressor
        self.assertNotIn("Deniz", res.final_text)
        self.assertNotIn("okul", res.final_text)

    def test_sensitive_context_is_not_injected(self):
        """9. Sensitive context is not injected (it gets blocked by sanitizer)."""
        lp = LocalProvider()
        messages = [{"role": "user", "content": "Nasılsın?"}]
        model_config = {
            "counseling_category": "anxiety",
            "safe_memory_inlays": {
                "display_name": "Deniz",
                "active_stressor": "intihar düşüncesi", # Unsafe - should be sanitized to empty
                "current_goal": "",
                "recent_emotion": "",
                "last_advice_topic": ""
            }
        }
        res = lp.generate(messages, model_config)
        self.assertNotIn("intihar", res.text)
        # Should fallback to prefixing display name on normal template or clean message
        self.assertIn("Deniz", res.text)

    def test_existing_local_provider_category_tests_still_pass(self):
        """10. Existing local provider category tests still pass."""
        lp = LocalProvider()
        for cat, templates in _CATEGORY_TEMPLATES.items():
            messages = [{"role": "user", "content": "Test"}]
            model_config = {"counseling_category": cat}
            res = lp.generate(messages, model_config)
            self.assertTrue(len(res.text) > 0)
            self.assertIn(res.text.strip("."), [t.strip(".") for t in templates] or [""])

if __name__ == "__main__":
    unittest.main()
