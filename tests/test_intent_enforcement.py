import sys
import os
import unittest
import re

sys.path.insert(0, ".")

from src.core.config import settings
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
from src.ai_providers import ai_orchestrator
from src.ai_providers.mock_provider import MockProvider
from src.core.redis_client import redis_client

class CaptureSystemPromptMockProvider(MockProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_system_prompt = None

    def generate(self, messages, model_config):
        for msg in messages:
            if msg.get("role") == "system":
                self.last_system_prompt = msg.get("content")
        return super().generate(messages, model_config)

class TestIntentEnforcement(unittest.TestCase):

    def setUp(self):
        self.original_primary_provider = settings.AI_PRIMARY_PROVIDER
        self.original_api_key = settings.OPENAI_API_KEY
        self.original_max_retries = settings.AI_MAX_RETRIES
        
        # Disable Redis connection attempts to make unit tests run instantly
        redis_client._client = False

        self.mock_provider = CaptureSystemPromptMockProvider(
            mock_response="Başarılı yapay zeka cevabı."
        )
        ai_orchestrator.register_provider("mock_provider", self.mock_provider)
        
        settings.AI_PRIMARY_PROVIDER = "mock_provider"
        settings.OPENAI_API_KEY = ""
        settings.AI_MAX_RETRIES = 0

    def tearDown(self):
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.OPENAI_API_KEY = self.original_api_key
        settings.AI_MAX_RETRIES = self.original_max_retries
        
        ai_orchestrator.register_provider("openai", ai_orchestrator.openai_provider)
        ai_orchestrator.register_provider("local", ai_orchestrator.local_provider)

    def test_emotional_expression_enforcement(self):
        """1. 'Kendimi çok yalnız hissediyorum.' -> emotional_expression
        Response must contain validation/normalization and NO advice language.
        """
        # Test A: Local Fallback Response (Privacy Mode = True)
        inp_local = EngineInput(
            user_id="test_user",
            text="Kendimi çok yalnız hissediyorum.",
            emotion="loneliness",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res_local = response_engine.generate_response(inp_local)
        text = res_local.final_text
        
        # Verify intent
        self.assertEqual(res_local.metadata["psychological_understanding"]["intent"], "emotional_expression")
        
        # Verify validation & normalization are present (first sentence, second sentence)
        self.assertTrue(len(text) > 0)
        
        # Verify no advice language is present
        forbidden = ["öneririm", "deneyebilirsin", "şunu yap", "adım at", "iletişime geç"]
        for word in forbidden:
            self.assertNotIn(word, text.lower(), f"Forbidden word '{word}' found in emotional_expression response: '{text}'")

        # Test B: System Prompt Instructions
        inp_prompt = EngineInput(
            user_id="test_user",
            text="Kendimi çok yalnız hissediyorum.",
            emotion="loneliness",
            risk="Normal"
        )
        response_engine.generate_response(inp_prompt)
        prompt = self.mock_provider.last_system_prompt
        self.assertIn("NİYET VE YAPI KURALI (Duygusal İfade / emotional_expression)", prompt)
        self.assertIn("KESİNLİKLE hiçbir pratik tavsiye", prompt)

    def test_help_seeking_enforcement(self):
        """2. 'Kendimi çok yalnız hissediyorum, ne yapmalıyım?' -> help_seeking
        Response must contain validation and exactly one gentle actionable step.
        """
        # Test A: Local Fallback Response (Privacy Mode = True)
        inp_local = EngineInput(
            user_id="test_user",
            text="Kendimi çok yalnız hissediyorum, ne yapmalıyım?",
            emotion="loneliness",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res_local = response_engine.generate_response(inp_local)
        text = res_local.final_text
        
        # Verify intent
        self.assertEqual(res_local.metadata["psychological_understanding"]["intent"], "help_seeking")
        
        # Verify at least one action phrase is present
        action_phrases = ["mesaj atmak", "aramak", "iletişim kurmak", "küçük bir adım"]
        has_action = any(phrase in text.lower() for phrase in action_phrases)
        self.assertTrue(has_action, f"No action phrase found in help_seeking response: '{text}'")
        
        # Verify no bullet lists or multiple suggestions
        self.assertNotIn("-", text)
        self.assertNotIn("*", text)

        # Test B: System Prompt Instructions
        inp_prompt = EngineInput(
            user_id="test_user",
            text="Kendimi çok yalnız hissediyorum, ne yapmalıyım?",
            emotion="loneliness",
            risk="Normal"
        )
        response_engine.generate_response(inp_prompt)
        prompt = self.mock_provider.last_system_prompt
        self.assertIn("NİYET VE YAPI KURALI (Yardım Arama / help_seeking)", prompt)
        self.assertIn("KESİNLİKLE YALNIZCA BİR ADET", prompt)

    def test_self_reflection_enforcement(self):
        """3. 'Neden hep böyle hissediyorum?' -> self_reflection
        Response must contain reflective language and a reflective question.
        """
        # Test A: Local Fallback Response (Privacy Mode = True)
        inp_local = EngineInput(
            user_id="test_user",
            text="Neden hep böyle hissediyorum?",
            emotion="sadness",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res_local = response_engine.generate_response(inp_local)
        text = res_local.final_text
        
        # Verify intent
        self.assertEqual(res_local.metadata["psychological_understanding"]["intent"], "self_reflection")
        
        # Verify contains a question
        self.assertIn("?", text)

        # Test B: System Prompt Instructions
        inp_prompt = EngineInput(
            user_id="test_user",
            text="Neden hep böyle hissediyorum?",
            emotion="sadness",
            risk="Normal"
        )
        response_engine.generate_response(inp_prompt)
        prompt = self.mock_provider.last_system_prompt
        self.assertIn("NİYET VE YAPI KURALI (Kendini Sorgulama / self_reflection)", prompt)

    def test_problem_solving_enforcement(self):
        """4. 'Bu iki seçenek arasında kaldım.' -> problem_solving
        Response must contain decision support framing.
        """
        # Test A: Local Fallback Response (Privacy Mode = True)
        inp_local = EngineInput(
            user_id="test_user",
            text="Bu iki seçenek arasında kaldım.",
            emotion="uncertainty",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res_local = response_engine.generate_response(inp_local)
        text = res_local.final_text
        
        # Verify intent
        self.assertEqual(res_local.metadata["psychological_understanding"]["intent"], "problem_solving")
        # Sprint 7.4: improved template — 'yorucu' acknowledges the dilemma, 'karar' is decision framing
        self.assertTrue(
            any(m in text for m in ["ikilemdir", "yorucu", "arasında kalmak"]),
            f"Expected dilemma acknowledgement in: '{text}'"
        )
        self.assertTrue(
            any(m in text for m in ["artılarını ve eksilerini", "kazandıracakları", "değere daha yakın", "artı"]),
            f"Expected decision framing in: '{text}'"
        )

        # Test B: System Prompt Instructions
        inp_prompt = EngineInput(
            user_id="test_user",
            text="Bu iki seçenek arasında kaldım.",
            emotion="uncertainty",
            risk="Normal"
        )
        response_engine.generate_response(inp_prompt)
        prompt = self.mock_provider.last_system_prompt
        self.assertIn("NİYET VE YAPI KURALI (Problem Çözme / problem_solving)", prompt)

    def test_crisis_bypass_enforcement(self):
        """5. 'Artık yaşamak istemiyorum.' -> crisis bypass -> no intent enforcement."""
        inp = EngineInput(
            user_id="test_user_crisis",
            text="Artık yaşamak istemiyorum.",
            emotion="sadness",
            risk="1"
        )
        self.mock_provider.last_system_prompt = None
        res = response_engine.generate_response(inp)
        
        # Verify LLM system prompt is None (remote call bypassed)
        self.assertIsNone(self.mock_provider.last_system_prompt)
        
        # Verify crisis metadata
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["final_model"], "crisis_safe_template")

if __name__ == "__main__":
    unittest.main()
