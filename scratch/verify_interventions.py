import sys
import os
from datetime import datetime

# Adjust path to import src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.database import save_emotion_event, get_user_emotion_summary
from src.services.smart_interventions import generate_smart_interventions

def test_smart_interventions():
    print("=== STARTING SMART INTERVENTION SYSTEM INTEGRATION TESTS ===")
    user_id = "test_intervention_user"
    
    # Locate sqlite file path from DATABASE_URL
    import sqlite3
    from src.services.database import DATABASE_URL
    
    # Strip sqlite:/// prefix
    db_path = DATABASE_URL.replace("sqlite:///", "")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emotion_events WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    # Test Case 1: Minimum Threshold Check (< 4 messages should return empty list)
    save_emotion_event(user_id, "msg_1", "joy", "0")
    save_emotion_event(user_id, "msg_2", "joy", "0")
    
    interventions = generate_smart_interventions(user_id, days=7)
    assert len(interventions) == 0, f"Expected 0 interventions due to threshold, got {len(interventions)}"
    print("✓ Test 1 Passed: Noise reduction threshold (< 4 messages) successfully returns empty.")

    # Test Case 2: Standard Triggering & Cap (>= 4 messages)
    save_emotion_event(user_id, "msg_3", "anxiety", "0")
    save_emotion_event(user_id, "msg_4", "anxiety", "0")
    save_emotion_event(user_id, "msg_5", "anxiety", "0")
    save_emotion_event(user_id, "msg_6", "anxiety", "0")
    
    interventions = generate_smart_interventions(user_id, days=7)
    assert len(interventions) > 0, "Expected generated interventions, got empty list"
    assert len(interventions) <= 3, f"Expected at most 3 interventions, got {len(interventions)}"
    
    # Ensure anxiety matches breathing_break
    types = [i["type"] for i in interventions]
    assert "breathing_break" in types, f"Expected breathing_break to be triggered, got {types}"
    print("✓ Test 2 Passed: Standard trigger (anxiety -> breathing_break) successfully extracted and capped at 3.")

    # Test Case 3: Crisis Safety Guidance Override
    # Insert a critical self-harm/suicide event
    save_emotion_event(user_id, "msg_crisis", "sadness", "1", source="suicide_warning")
    
    interventions = generate_smart_interventions(user_id, days=7)
    types = [i["type"] for i in interventions]
    
    # Ensure crisis override priority support card is generated
    assert "priority_support" in types, f"Expected priority_support override under crisis, got {types}"
    assert interventions[0]["type"] == "priority_support", "Expected priority support card to be the highest priority (first element)"
    print("✓ Test 3 Passed: Crisis override prioritizing expert support successfully verified.")

    # Test Case 4: Non-Diagnostic Medical Word Restrictions
    for i in interventions:
        desc = i["description"].lower()
        title = i["title"].lower()
        forbidden = ["tedavi", "tanı", "depresyon", "anksiyete bozukluğu", "bipolar", "teşhis", "hastalık"]
        for f in forbidden:
            assert f not in desc and f not in title, f"Forbidden word '{f}' found in intervention description: {desc}"
            
    print("✓ Test 4 Passed: Non-diagnostic wording compliance verified successfully.")
    print("=== ALL SMART INTERVENTION SYSTEM INTEGRATION TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    test_smart_interventions()
