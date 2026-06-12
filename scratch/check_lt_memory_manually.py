import sys
import os
import json

sys.path.insert(0, ".")

from src.response_engine.memory_profile import load_profile, get_profile_path, build_summary_for_prompt
from src.response_engine.memory_extractor import extract_and_update_profile
from src.response_engine.personal_context_engine import PersonalContextEngine

test_user = "lt_manual_test_user"

# Clean up before starting
profile_path = get_profile_path(test_user)
if os.path.exists(profile_path):
    os.remove(profile_path)

conversations = [
    ("Bu ara sınavlar yüzünden çok stresliyim.", "anxiety", "Normal"),
    ("Bugün yine ders çalışırken kaygılandım.", "anxiety", "Normal"),
    ("Uyku düzenimi düzeltmeye çalışıyorum.", "neutral", "Normal"),
    ("Bu gece yine zor uyudum.", "sadness", "Normal")
]

pce = PersonalContextEngine()

print("================ LONG-TERM MEMORY MANUAL VERIFICATION ================\n")

for i, (text, emotion, risk) in enumerate(conversations, 1):
    print(f"--- TURN {i}: \"{text}\" (Emotion: {emotion.upper()}) ---")
    
    # 1. Process turn inside PCE (runs extraction and retrieves injection)
    turn_res = pce.process_turn(
        user_id=test_user,
        text=text,
        emotion=emotion,
        risk=risk,
        privacy_mode=False
    )
    
    # Load profile to show current state
    profile = load_profile(test_user)
    
    print("[Profile Content]")
    print(json.dumps({
        "goals": profile.get("goals"),
        "stressors": profile.get("stressors"),
        "work_or_school_context": profile.get("work_or_school_context"),
        "last_advice_topics": profile.get("last_advice_topics")
    }, indent=2, ensure_ascii=False))
    
    print("\n[Injected Memory Prompt Context]")
    if turn_res["memory_injected"]:
        print(turn_res["injection_text"])
    else:
        print("<No memory injected>")
        
    print("=" * 80 + "\n")
