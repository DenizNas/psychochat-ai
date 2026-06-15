"""
Phase 4.0D — Unit and integration tests for chatbot response quality upgrade.
"""
import os
import sys
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment stubs
os.environ.setdefault("OPENAI_API_KEY", "sk-dummy-test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("APP_ENV", "development")

from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
from src.response_engine.counseling_examples import categorize_input
from src.ai_providers.local_provider import LocalProvider
from src.services.database import init_db

class TestPhase40DResponseQuality(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.user_id = "test_phase_40d_user"
        # Reset OpenAI API key to dummy to enforce fallback provider
        import src.core.config as config
        config.settings.OPENAI_API_KEY = "sk-dummy-test-key"

    def test_merhaba_greeting(self):
        """1. 'Merhaba' should receive a short neutral response, no memory injection."""
        inp = EngineInput(
            user_id=self.user_id,
            text="Merhaba",
            emotion="neutral",
            risk="Normal",
            language="tr",
            preferences=UserPreferences(
                response_style="supportive",
                preferred_language="tr",
                privacy_mode=False,
                answer_length_preference="medium"
            )
        )
        res = response_engine.generate_response(inp)
        
        # Verify response is short, friendly, and not over-therapized
        self.assertIn("Merhaba", res.final_text)
        self.assertTrue(len(res.final_text) < 120, f"Greeting response is too long: {res.final_text}")
        self.assertFalse(res.metadata["memory"]["memory_injected"])
        self.assertEqual(res.metadata["memory"]["selected_memory_count"], 0)

    def test_connection_test(self):
        """2. 'Bağlantı testi' should receive a neutral response, no memory injection."""
        inp = EngineInput(
            user_id=self.user_id,
            text="Bağlantı testi",
            emotion="neutral",
            risk="Normal",
            language="tr",
            preferences=UserPreferences(
                response_style="supportive",
                preferred_language="tr",
                privacy_mode=False,
                answer_length_preference="medium"
            )
        )
        res = response_engine.generate_response(inp)
        
        # Verify neutral connection test response
        self.assertIn("başarılı", res.final_text.lower())
        self.assertFalse(res.metadata["memory"]["memory_injected"])
        self.assertEqual(res.metadata["memory"]["selected_memory_count"], 0)

    def test_sadness_reflection_and_steps(self):
        """3. 'Bugün kendimi çok kötü hissediyorum. Hiçbir şey yapmak istemiyorum.' should return reflection, micro-education, 1-3 practical steps, and follow-up."""
        inp = EngineInput(
            user_id=self.user_id,
            text="Bugün kendimi çok kötü hissediyorum. Hiçbir şey yapmak istemiyorum.",
            emotion="sadness",
            risk="Normal",
            language="tr",
            preferences=UserPreferences(
                response_style="supportive",
                preferred_language="tr",
                privacy_mode=False,
                answer_length_preference="medium"
            )
        )
        res = response_engine.generate_response(inp)
        
        text = res.final_text
        # Emotional reflection / validation
        self.assertTrue(
            "anlaşılır" in text or "ağırlığı" in text or "yorgunluğu" in text or "doğal" in text or "normal" in text,
            f"Missing emotional reflection in sadness response: {text}"
        )
        # Micro-education on low energy/withdrawal cycle
        self.assertTrue(
            "enerjimizi" in text or "kış uykusu" in text or "çekilmeye" in text or "yavaşlama" in text or "nadasa" in text or "enerji" in text,
            f"Missing psychoeducational explanation in sadness response: {text}"
        )
        # 1-3 practical steps
        self.assertTrue(
            "pencereden" in text or "derin bir nefes" in text or "adım" in text or "suçlamadan" in text or "ılık bir bardak su" in text,
            f"Missing practical steps in sadness response: {text}"
        )
        # Gentle follow-up question
        self.assertTrue(
            "?" in text,
            f"Missing gentle follow-up question in sadness response: {text}"
        )

    def test_anxiety_body_alarm_response(self):
        """4. 'Çok kaygılıyım, kalbim hızlı atıyor.' should return anxiety/body alarm explanation, grounding/breathing suggestion, and warm tone."""
        inp = EngineInput(
            user_id=self.user_id,
            text="Çok kaygılıyım, kalbim hızlı atıyor.",
            emotion="anxiety",
            risk="Normal",
            language="tr",
            preferences=UserPreferences(
                response_style="supportive",
                preferred_language="tr",
                privacy_mode=False,
                answer_length_preference="medium"
            )
        )
        res = response_engine.generate_response(inp)
        
        text = res.final_text
        # Anxiety body alarm explanation
        self.assertTrue(
            "alarm" in text or "tehdit" in text or "korumak" in text or "kalbin" in text,
            f"Missing body alarm response explanation in anxiety response: {text}"
        )
        # Grounding and breathing suggestion
        self.assertTrue(
            "nefes" in text or "dokunmayı" in text or "şimdiye" in text or "nesne" in text,
            f"Missing grounding/breathing suggestion in anxiety response: {text}"
        )
        # Ststrictly avoid saying "sakin ol"
        self.assertNotIn("sakin ol", text.lower())

    def test_new_categories_categorize_input(self):
        """Verify categorization logic for guilt_shame and uncertainty."""
        self.assertEqual(categorize_input("Kendimi çok suçlu hissediyorum", "neutral"), "guilt_shame")
        self.assertEqual(categorize_input("Çok utanıyorum pişmanım", "neutral"), "guilt_shame")
        self.assertEqual(categorize_input("Hayatımda ne yapacağımı bilmiyorum kararsızım", "neutral"), "uncertainty")
        self.assertEqual(categorize_input("Hangi yolu seçeceğimi bilmiyorum, emin değilim", "neutral"), "uncertainty")

if __name__ == "__main__":
    unittest.main(verbosity=2)
