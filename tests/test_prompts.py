from src.response_engine.prompts import (
    PROMPT_VERSION,
    get_emotion_instructions,
    get_crisis_instructions,
    get_prompt_injection_guard,
    build_system_prompt,
    build_user_prompt,
)

print("--- PROMPT_VERSION ---")
print(PROMPT_VERSION)

print("\n--- Emotion: sadness ---")
print(get_emotion_instructions("sadness")[:80])

print("\n--- Emotion: anger ---")
print(get_emotion_instructions("anger")[:80])

print("\n--- Crisis instructions ---")
print(get_crisis_instructions()[:80])

print("\n--- Injection guard (first 120 chars) ---")
print(get_prompt_injection_guard()[:120])

# Normal turn: emotion present, crisis absent
prompt, meta = build_system_prompt(language="tr", emotion="sadness", risk="Normal", text="Çok üzgünüm")
print("\n--- build_system_prompt (normal, sadness) ---")
print("sections:", meta["prompt_sections"])
print("length:", meta["prompt_length"])
print("version:", meta["prompt_version"])
print("injection_guard_enabled:", meta["injection_guard_enabled"])
assert "crisis" not in meta["prompt_sections"], "FAIL: crisis must not appear in normal turn"
assert "emotion:sadness" in meta["prompt_sections"], "FAIL: emotion section missing"

# Crisis turn: crisis present, emotion absent
prompt_c, meta_c = build_system_prompt(language="tr", emotion="sadness", risk="1")
print("\n--- build_system_prompt (crisis turn) ---")
print("sections:", meta_c["prompt_sections"])
assert "crisis" in meta_c["prompt_sections"], "FAIL: crisis section missing"
assert not any("emotion:" in s for s in meta_c["prompt_sections"]), "FAIL: emotion must not appear in crisis turn"

# User prompt delimiter
up = build_user_prompt("Sinav stresi var", "anxiety", "Normal")
print("\n--- build_user_prompt ---")
print(up)
assert '"""' in up, "FAIL: delimiter missing"

# Memory injection flows through build_system_prompt
prompt_m, meta_m = build_system_prompt(
    emotion="sadness", risk="Normal",
    text="Çok üzgünüm",
    memory_context="- [coping_strategies] Nefes egzersizi"
)
print("\n--- Memory injection in build_system_prompt ---")
print("sections with memory:", meta_m["prompt_sections"])
assert "memory" in meta_m["prompt_sections"], "FAIL: memory section missing"

# Injection guard: 'act as' phrase present in guard text
guard = get_prompt_injection_guard()
assert "act as" in guard.lower(), "FAIL: 'act as' must be in injection guard"
assert "reveal system prompt" in guard.lower(), "FAIL: 'reveal system prompt' must be in injection guard"
assert "developer message" in guard.lower(), "FAIL: 'developer message' must be in injection guard"

print("\nAll assertions PASSED")
