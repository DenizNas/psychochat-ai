"""
Sprint 7.5 End-to-End Verification:
Conversation: "Bugün çok mutsuzum." / "Hiçbir şeyden keyif alamıyorum." / "Kimseyle konuşmak istemiyorum."
"""
import sys
sys.path.insert(0, '.')

from src.response_engine.counseling_examples import categorize_input
from src.response_engine.theme_need_engine import detect_theme_and_need
from src.response_engine.conversation_pattern_engine import detect_conversation_pattern
from src.response_engine.prompts import build_system_prompt, get_conversation_pattern_section
from src.ai_providers.local_provider import LocalProvider

print("=" * 65)
print("SPRINT 7.5 END-TO-END VERIFICATION")
print("=" * 65)

msgs = [
    "Bugün çok mutsuzum.",
    "Hiçbir şeyden keyif alamıyorum.",
    "Kimseyle konuşmak istemiyorum.",
]

# ── Turn 3 input ───────────────────────────────────────────────
text    = msgs[2]
emotion = "sadness"
subtype = None
risk    = "Normal"

print(f"\nTurn 3 text: {repr(text)}")
print(f"Emotion:     {emotion}")

# A. categorize_input (Fix 1)
cat = categorize_input(text, emotion)
print(f"\nA. categorize_input -> {repr(cat)}")
assert cat != "neutral", f"FAIL: category is still neutral! Fix 1 not working."
print("   ✓ Not neutral — Fix 1 OK")

# B. theme/need/intent
tne = detect_theme_and_need(text=text, emotion=emotion, subtype=subtype)
print(f"\nB. Theme/Need/Intent:")
print(f"   theme:  {tne['theme']}")
print(f"   need:   {tne['need']}")
print(f"   intent: {tne['intent']}")

# C. Pattern detection
pat = detect_conversation_pattern(msgs, current_theme=tne["theme"], current_need=tne["need"])
print(f"\nC. Pattern Detection:")
print(f"   pattern_name: {pat['pattern_name']}")
print(f"   confidence:   {pat['confidence']}")
print(f"   hit_count:    {pat['hit_count']}")
assert pat["pattern_name"] == "withdrawal_pattern", f"FAIL: expected withdrawal_pattern, got {pat['pattern_name']}"
assert pat["confidence"] >= 0.65, f"FAIL: confidence {pat['confidence']} < 0.65"
print("   ✓ withdrawal_pattern detected @ ≥65% — pattern detection OK")

# D. Prompt section
section = get_conversation_pattern_section(pat["pattern_name"], pat["confidence"], pat.get("hit_count", 0))
print(f"\nD. Prompt Section Injected:")
print(f"   {'YES — KONUŞMA ÖRÜNTÜSÜ ANALİZİ present' if section else 'NO (empty!)'}")
assert section, "FAIL: pattern section is empty — prompt injection broken"

sys_prompt, meta = build_system_prompt(
    language="tr",
    emotion=emotion,
    risk=risk,
    memory_context="",
    preferences={"response_style": "supportive", "answer_length_preference": "medium", "privacy_mode": False},
    text=text,
    subtype=subtype,
    strategy=None,
    theme=tne["theme"],
    need=tne["need"],
    intent=tne["intent"],
    conversation_pattern=pat,
)
has_pattern_in_prompt = "KONUŞMA ÖRÜNTÜSÜ ANALİZİ" in sys_prompt
print(f"   KONUŞMA ÖRÜNTÜSÜ ANALİZİ in system prompt: {has_pattern_in_prompt}")
assert has_pattern_in_prompt, "FAIL: pattern section missing from assembled system prompt"
print("   ✓ Pattern section in prompt — Fix B OK")
print(f"   Sections: {meta['prompt_sections']}")

# E. LocalProvider response
print(f"\nE. LocalProvider Response (Fix 2):")
model_config = {
    "counseling_category": cat,
    "counseling_strategy": "validation",
    "counseling_subtype": subtype,
    "intent": tne["intent"],
    "answer_length_preference": "medium",
    "response_style": "supportive",
    "safe_memory_inlays": {},
    "conversation_pattern": pat,
}
messages = [
    {"role": "system", "content": sys_prompt},
    {"role": "user",   "content": f'[BAĞLAM - Duygu: SADNESS, Risk: NORMAL]\nKullanıcı Mesajı: """{text}"""'},
]
provider = LocalProvider()
result   = provider.generate(messages, model_config)
response = result.text

print(f"\n   Response:\n   {response}")
print()

# F. Acceptance criteria checks
FORBIDDEN = ["sen sürekli", "her zaman", "kesinlikle"]
REQUIRED_SOFT = ["son birkaç mesajında", "bir süredir", "dikkatimi çeken", "son mesajlarında"]
PATTERN_SIGNAL = ["keyifsizlik", "uzaklaş", "çekilme", "insanlardan"]

print("F. Acceptance Criteria:")
response_lower = response.lower()

# Forbidden phrases
for f in FORBIDDEN:
    assert f not in response_lower, f"FAIL: forbidden phrase '{f}' found in response!"
print("   ✓ No forbidden absolute phrases (sen sürekli / her zaman / kesinlikle)")

# Soft continuity phrases
has_soft = any(s in response_lower for s in REQUIRED_SOFT)
assert has_soft, f"FAIL: no soft continuity phrase found! Expected one of: {REQUIRED_SOFT}"
print("   ✓ Soft continuity phrase present")

# Pattern signal
has_signal = any(s in response_lower for s in PATTERN_SIGNAL)
if has_signal:
    print("   ✓ Withdrawal pattern signal present in response")
else:
    print("   ⚠ No explicit withdrawal signal (may still be acceptable)")

print()
print("=" * 65)
print("ALL CHECKS PASSED — Sprint 7.5 regression fixed.")
print("=" * 65)
