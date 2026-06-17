import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, ".")

from src.core.config import settings
from src.response_engine.theme_need_engine import detect_theme_and_need
from src.response_engine.prompts import build_system_prompt
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput
from src.ai_providers import ai_orchestrator
from src.ai_providers.mock_provider import MockProvider
from src.core.redis_client import redis_client

class CaptureSystemPromptMockProvider(MockProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_messages = []
        self.last_system_prompt = None

    def generate(self, messages, model_config):
        self.last_messages = messages
        for msg in messages:
            if msg.get("role") == "system":
                self.last_system_prompt = msg.get("content")
        return super().generate(messages, model_config)

class TestIntentAwareCounseling(unittest.TestCase):

    def setUp(self):
        # Backup original configuration
        self.original_primary_provider = settings.AI_PRIMARY_PROVIDER
        self.original_api_key = settings.OPENAI_API_KEY
        self.original_max_retries = settings.AI_MAX_RETRIES
        
        # Disable Redis connection attempts to make unit tests run instantly
        redis_client._client = False

        # Set up mock provider
        self.mock_provider = CaptureSystemPromptMockProvider(
            mock_response="Empatik ve yapılandırılmış bir yanıt şablonu."
        )
        ai_orchestrator.register_provider("mock_provider", self.mock_provider)
        
        settings.AI_PRIMARY_PROVIDER = "mock_provider"
        settings.OPENAI_API_KEY = ""
        settings.AI_MAX_RETRIES = 0

    def tearDown(self):
        # Restore configuration
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.OPENAI_API_KEY = self.original_api_key
        settings.AI_MAX_RETRIES = self.original_max_retries
        
        # Re-register standard provider registry
        ai_orchestrator.register_provider("openai", ai_orchestrator.openai_provider)
        ai_orchestrator.register_provider("local", ai_orchestrator.local_provider)

    def test_intent_detection_lonely(self):
        """1. 'Kendimi çok yalnız hissediyorum.' -> emotional_expression"""
        res = detect_theme_and_need(
            text="Kendimi çok yalnız hissediyorum.",
            emotion="loneliness",
            subtype=None
        )
        self.assertEqual(res["theme"], "social_disconnection")
        self.assertEqual(res["need"], "connection_support")
        self.assertEqual(res["intent"], "emotional_expression")

    def test_intent_detection_lonely_what_to_do(self):
        """2. 'Kendimi çok yalnız hissediyorum, ne yapmalıyım?' -> help_seeking"""
        res = detect_theme_and_need(
            text="Kendimi çok yalnız hissediyorum, ne yapmalıyım?",
            emotion="loneliness",
            subtype=None
        )
        self.assertEqual(res["theme"], "social_disconnection")
        self.assertEqual(res["intent"], "help_seeking")

    def test_intent_detection_what_should_i_do(self):
        """3. 'Ne yapacağımı bilmiyorum.' -> help_seeking"""
        res = detect_theme_and_need(
            text="Ne yapacağımı bilmiyorum.",
            emotion="uncertainty",
            subtype="life_direction_uncertainty"
        )
        self.assertEqual(res["theme"], "life_direction_uncertainty")
        self.assertEqual(res["intent"], "help_seeking")

    def test_intent_detection_why_always(self):
        """4. 'Neden hep böyle hissediyorum?' -> self_reflection"""
        res = detect_theme_and_need(
            text="Neden hep böyle hissediyorum?",
            emotion="sadness",
            subtype=None
        )
        self.assertEqual(res["intent"], "self_reflection")

    def test_prompt_injection_emotional_expression(self):
        """Verify prompt contains emotional_expression instructions when intent is emotional_expression."""
        inp = EngineInput(
            user_id="test_user",
            text="Kendimi çok yalnız hissediyorum.",
            emotion="loneliness",
            risk="Normal"
        )
        response_engine.generate_response(inp)
        system_prompt = self.mock_provider.last_system_prompt
        self.assertIsNotNone(system_prompt)
        self.assertIn("NİYET VE YAPI KURALI (Duygusal İfade / emotional_expression)", system_prompt)
        self.assertIn("KESİNLİKLE hiçbir pratik tavsiye", system_prompt)

    def test_prompt_injection_help_seeking(self):
        """Verify prompt contains help_seeking instructions when intent is help_seeking."""
        inp = EngineInput(
            user_id="test_user",
            text="Kendimi çok yalnız hissediyorum, ne yapmalıyım?",
            emotion="loneliness",
            risk="Normal"
        )
        response_engine.generate_response(inp)
        system_prompt = self.mock_provider.last_system_prompt
        self.assertIsNotNone(system_prompt)
        self.assertIn("NİYET VE YAPI KURALI (Yardım Arama / help_seeking)", system_prompt)
        self.assertIn("kullanıcının durumuna uygun, onu yormayacak şekilde KESİNLİKLE YALNIZCA BİR ADET", system_prompt)

    def test_prompt_injection_self_reflection(self):
        """Verify prompt contains self_reflection instructions when intent is self_reflection."""
        inp = EngineInput(
            user_id="test_user",
            text="Neden hep böyle hissediyorum?",
            emotion="sadness",
            risk="Normal"
        )
        response_engine.generate_response(inp)
        system_prompt = self.mock_provider.last_system_prompt
        self.assertIsNotNone(system_prompt)
        self.assertIn("NİYET VE YAPI KURALI (Kendini Sorgulama / self_reflection)", system_prompt)
        # Sprint 7.4: directive now says 'empatik bir ayna tut' (upgraded from 'gibi yansıt')
        self.assertTrue(
            "empatik bir ayna" in system_prompt,
            "self_reflection directive must contain 'empatik bir ayna'"
        )

    def test_crisis_bypass_completely(self):
        """5. 'Artık yaşamak istemiyorum.' -> crisis bypass -> no LLM prompt is constructed/sent."""
        inp = EngineInput(
            user_id="test_user_crisis",
            text="Artık yaşamak istemiyorum.",
            emotion="sadness",
            risk="1"
        )
        self.mock_provider.last_system_prompt = None
        res = response_engine.generate_response(inp)
        
        # Verify LLM was bypassed (last_system_prompt remains None)
        self.assertNil = self.mock_provider.last_system_prompt
        self.assertIsNone(self.mock_provider.last_system_prompt)
        
        # Verify crisis metadata was returned and flow was triggered
        self.assertTrue(res.is_fallback)
        self.assertEqual(res.metadata["final_model"], "crisis_safe_template")
        self.assertTrue(res.metadata["is_crisis"])

if __name__ == "__main__":
    unittest.main()
