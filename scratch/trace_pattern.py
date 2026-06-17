"""
Sprint 7.5 Regression Investigation Trace Script
"""
import sys
sys.path.insert(0, '.')

from src.response_engine.counseling_examples import categorize_input
from src.ai.preprocessing import turkish_lower
from src.ai_providers.local_provider import _CATEGORY_TEMPLATES, _PATTERN_TEMPLATES

text = 'Kimseyle konuşmak istemiyorum.'
clean = turkish_lower(text)
words = clean.split()

print("=== TEXT ANALYSIS ===")
print(f"clean text: {repr(clean)}")
print(f"word count: {len(words)}")
print(f"words: {words}")
print()

_SHORT_EMOTIONAL_EXCEPTIONS = {
    "üzgünüm", "üzüldüm", "ağlıyorum", "korkuyorum", "öfkeliyim",
    "sinirli", "kaygılı", "bunaldım", "yoruldum", "depresyon",
    "suçlu", "suçluyum", "utanç", "utanıyorum", "pişmanım", "pişman",
    "belirsiz", "kararsız", "kararsızım", "ne yapacağımı", "ne yapsam", "bilmiyorum",
    "yönünü", "yönümü",
    "seçmeliyim", "seçeneği", "kararımı", "hangişi", "seçeyim",
    "neyi seç", "hangisi",
    "anlamıyorum", "çözemedim", "sürekli", "tekrar tekrar",
    "yalnız", "kimsem", "yapayalnız",
}

print("=== SHORT-MESSAGE NEUTRALIZATION RULE ===")
is_short = len(words) <= 3
has_exception = any(exc in clean for exc in _SHORT_EMOTIONAL_EXCEPTIONS)
print(f"Is short (<=3 words)? {is_short}")
print(f"Has emotional exception? {has_exception}")
if is_short and not has_exception:
    print(">>> RESULT: Returns 'neutral' (short-message rule fires!)")
print()

category_result = categorize_input(text, "sadness")
print(f"categorize_input('Kimseyle konuşmak istemiyorum.', 'sadness') = {repr(category_result)}")
print()

print("=== ROOT CAUSE ===")
print("'Kimseyle konuşmak istemiyorum.' has 3 words in Turkish after processing:")
print(" -> kimseyle konuşmak istemiyorum")
print(" -> Exactly 3 words, no exception token found -> categorized as 'neutral'")
print()
print("In engine.py prompts.py build_system_prompt():")
print(" -> category = categorize_input(text, emotion) = 'neutral'")
print(" -> emotion section uses 'neutral' strategy")
print(" -> memory_context is forced to empty (neutral category)")
print(" -> BUT conversation_pattern IS injected (non-crisis check only)")
print()

print("=== LOCAL PROVIDER BEHAVIOR WHEN category=neutral ===")
print("When LocalProvider receives counseling_category='neutral':")
print(" -> It uses _CATEGORY_TEMPLATES['neutral'] = generic 'Seni dinlemeye...' text")
print(" -> Pattern templates in _PATTERN_TEMPLATES are NEVER checked!")
print()
print("LocalProvider pattern templates:")
for k, v in _PATTERN_TEMPLATES.items():
    print(f"  {k}: {repr(v[0][:60])}...")
print()

print("=== LocalProvider generate() pattern handling gap ===")
print("LocalProvider.generate() reads model_config['conversation_pattern']")
print("BUT: it only falls through to pattern templates when a pattern is detected,")
print("and the code path for it may not be implemented correctly.")
print()
print("Let me check...")

# Simulate what LocalProvider does with this input
from src.ai_providers.local_provider import LocalProvider
provider = LocalProvider()

model_config = {
    "counseling_category": "neutral",   # <- this is the problem
    "counseling_strategy": "exploration",
    "counseling_subtype": None,
    "intent": "emotional_expression",
    "answer_length_preference": "medium",
    "response_style": "supportive",
    "safe_memory_inlays": {},
    "conversation_pattern": {
        "pattern_name": "withdrawal_pattern",
        "confidence": 0.85,
        "hit_count": 6
    },
}

messages = [
    {
        "role": "system",
        "content": "Sen empatik bir psikolojik destek asistanısın."
    },
    {
        "role": "user",
        "content": '[BAĞLAM - Duygu: SADNESS, Risk: NORMAL]\nKullanıcı Mesajı: """Kimseyle konuşmak istemiyorum."""'
    }
]

result = provider.generate(messages, model_config)
print(f"=== LocalProvider response with category=neutral ===")
print(repr(result.text))
