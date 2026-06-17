import sys
import os

sys.path.insert(0, ".")

from src.core.config import settings
from src.response_engine.theme_need_engine import detect_theme_and_need
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput
from src.ai_providers import ai_orchestrator
from src.ai_providers.mock_provider import MockProvider

class CaptureSystemPromptMockProvider(MockProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_system_prompt = None

    def generate(self, messages, model_config):
        for msg in messages:
            if msg.get("role") == "system":
                self.last_system_prompt = msg.get("content")
        return super().generate(messages, model_config)

mock_provider = CaptureSystemPromptMockProvider(mock_response="Test")
ai_orchestrator.register_provider("mock_provider", mock_provider)
settings.AI_PRIMARY_PROVIDER = "mock_provider"
settings.OPENAI_API_KEY = ""
settings.AI_MAX_RETRIES = 0

inp = EngineInput(
    user_id="test_user",
    text="Kendimi çok yalnız hissediyorum, ne yapmalıyım?",
    emotion="loneliness",
    risk="Normal"
)
response_engine.generate_response(inp)
prompt = mock_provider.last_system_prompt
print("--- LAST SYSTEM PROMPT ---")
print(prompt)
print("--- END ---")

substring = "kullanıcının durumuna uygun, onu yormayacak şekilde KESİNLİKLE YALNIZCA BİR ADET"
print("Contains expected substring?", substring in prompt)
