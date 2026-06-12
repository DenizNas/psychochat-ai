import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ai_providers.local_provider import _KEYWORD_TO_CATEGORY
from src.ai.preprocessing import turkish_lower

text = "Sadece seninle biraz sohbet etmek istiyorum bugün nasılsın ne yapıyorsun"
last_message = f"[BAĞLAM - Duygu: NEUTRAL, Risk: NORMAL]\nKullanıcı Mesajı: \"\"\"{text}\"\"\""
last_message_lower = turkish_lower(last_message)

matched_kw = []
for keyword, cat in _KEYWORD_TO_CATEGORY.items():
    if keyword in last_message_lower:
        matched_kw.append((keyword, cat))

print("Matched keywords:", matched_kw)
