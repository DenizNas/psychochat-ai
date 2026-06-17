import sys
import os
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_engine.conversation_pattern_engine import detect_conversation_pattern
from src.response_engine.engine import ResponseEngine
from src.response_engine.models import EngineInput
from src.services.database import init_db, SessionLocal, ChatHistory, save_chat_message

def test_direct_withdrawal_pattern():
    # Test 1 (withdrawal): "Bugün çok mutsuzum." -> "Hiçbir şeyden keyif alamıyorum." -> "Kimseyle konuşmak istemiyorum."
    recent = [
        "Bugün çok mutsuzum.",
        "Hiçbir şeyden keyif alamıyorum.",
        "Kimseyle konuşmak istemiyorum."
    ]
    res = detect_conversation_pattern(recent, current_theme="loss_of_pleasure", current_need="validation_normalization")
    assert res["pattern_name"] == "withdrawal_pattern"
    assert res["confidence"] >= 0.70

def test_direct_anxiety_spiral():
    # Test 2 (anxiety): "Yarın sınavım var." -> "Başarısız olmaktan korkuyorum." -> "Sürekli bunu düşünüyorum."
    recent = [
        "Yarın sınavım var.",
        "Başarısız olmaktan korkuyorum.",
        "Sürekli bunu düşünüyorum."
    ]
    res = detect_conversation_pattern(recent, current_theme="exam_pressure", current_need="gentle_reassurance")
    assert res["pattern_name"] == "anxiety_spiral"
    assert res["confidence"] >= 0.70

def test_direct_uncertainty_cycle():
    # Test 3 (uncertainty): "Ne yapacağımı bilmiyorum." -> "Hayatımın yönünü kaybettim." -> "Ne yapacağımı seçemiyorum."
    recent = [
        "Ne yapacağımı bilmiyorum.",
        "Hayatımın yönünü kaybettim.",
        "Ne yapacağımı seçemiyorum."
    ]
    res = detect_conversation_pattern(recent, current_theme="life_direction_uncertainty", current_need="emotional_exploration")
    assert res["pattern_name"] == "uncertainty_cycle"
    assert res["confidence"] >= 0.70

def test_direct_self_worth_loop():
    # Test 4 (self-worth): "Kendimi yetersiz hissediyorum." -> "Hep başarısız oluyorum." -> "Hiçbir şeyi beceremiyorum."
    recent = [
        "Kendimi yetersiz hissediyorum.",
        "Hep başarısız oluyorum.",
        "Hiçbir şeyi beceremiyorum."
    ]
    res = detect_conversation_pattern(recent, current_theme="self_worth_doubt", current_need="validation_normalization")
    assert res["pattern_name"] == "self_worth_loop"
    assert res["confidence"] >= 0.70

def test_pattern_calibration_steps():
    # Test calibration flow (Sprint 7.5.1):
    # Turn 1: "Bugün çok mutsuzum."
    recent = ["Bugün çok mutsuzum."]
    res = detect_conversation_pattern(recent, current_theme="general_distress")
    assert res["pattern_name"] == "none"

    # Turn 2: "Hiçbir şeyden keyif alamıyorum."
    recent.append("Hiçbir şeyden keyif alamıyorum.")
    res = detect_conversation_pattern(recent, current_theme="loss_of_pleasure")
    # Should still not trigger because confidence is conf_base = 0.65, which is < 0.70
    assert res["pattern_name"] == "none"

    # Turn 3: "Kimseyle konuşmak istemiyorum."
    recent.append("Kimseyle konuşmak istemiyorum.")
    res = detect_conversation_pattern(recent, current_theme="social_disconnection")
    assert res["pattern_name"] == "withdrawal_pattern"
    assert res["confidence"] >= 0.70
    assert res["hit_count"] >= 2

def test_direct_crisis_no_pattern():
    # Test 5 (crisis): Crisis inputs should not trigger pattern reasoning.
    recent = [
        "Bugün çok mutsuzum.",
        "Hiçbir şeyden keyif alamıyorum.",
        "Artık yaşamak istemiyorum."
    ]
    # In engine.py, if the risk is kriz/crisis/1, pattern detection is bypassed.
    # We will test the integration of this bypass below.
    pass

def test_direct_low_confidence():
    # If no matching keywords are found: should return "none" and 0.0 confidence
    recent = [
        "Bugün hava çok güzel.",
        "Kitap okuyorum."
    ]
    res = detect_conversation_pattern(recent)
    assert res["pattern_name"] == "none"
    assert res["confidence"] == 0.0

def test_integration_patterns_and_crisis():
    init_db()
    db = SessionLocal()
    user_id = "test_user_pattern_integration"
    try:
        db.query(ChatHistory).filter(ChatHistory.user_id == user_id).delete()
        db.commit()
    finally:
        db.close()

    engine = ResponseEngine()

    # Step 1: Send "Bugün çok mutsuzum."
    save_chat_message(user_id, "user", "Bugün çok mutsuzum.")
    
    # Step 2: Send "Hiçbir şeyden keyif alamıyorum."
    save_chat_message(user_id, "user", "Hiçbir şeyden keyif alamıyorum.")
    
    # Step 3: Call generate_response with "Kimseyle konuşmak istemiyorum."
    # This should detect withdrawal_pattern
    engine_input = EngineInput(
        text="Kimseyle konuşmak istemiyorum.",
        emotion="sadness",
        risk="Normal",
        user_id=user_id,
        language="tr"
    )
    
    # Generate response and check metadata
    output = engine.generate_response(engine_input)
    assert "conversation_pattern" in output.metadata
    pat = output.metadata["conversation_pattern"]
    assert pat["pattern_name"] == "withdrawal_pattern"
    assert pat["confidence"] >= 0.65

    # Check that prompt is generated without absolute phrasing ("sen sürekli", etc.)
    # We can check that the system prompt or generated response does not contain bad words
    response_text = output.final_text.lower()
    for forbidden in ["sen sürekli", "her zaman", "kesinlikle"]:
        assert forbidden not in response_text

    # Step 4: Crisis input should bypass pattern detection and return no pattern injection
    crisis_input = EngineInput(
        text="Artık yaşamak istemiyorum.",
        emotion="sadness",
        risk="crisis",
        user_id=user_id,
        language="tr"
    )
    crisis_output = engine.generate_response(crisis_input)
    # The crisis bypass returns safe template, but let's make sure if there is any conversation_pattern,
    # it is either "none" or absent/bypassed.
    metadata = crisis_output.metadata
    assert metadata.get("is_crisis") is True
    # In safety bypass, metadata["conversation_pattern"] is not injected, or if it was processed, it is "none"
    pat = metadata.get("conversation_pattern")
    if pat:
        assert pat["pattern_name"] == "none"
