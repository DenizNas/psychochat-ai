import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment stubs
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///data/psikochat_test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["APP_ENV"] = "development"

from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
from src.response_engine.counseling_examples import categorize_input, detect_emotion_subtype
from src.response_engine.strategy_engine import detect_conversation_strategy
from src.services.database import init_db

# Initialize database
init_db()

# Target test cases
test_cases = [
    {
        "text": "Hiçbir şeyden keyif alamıyorum.",
        "desc": "sadness + anhedonia + validation; no generic fallback response."
    },
    {
        "text": "Yarınki sınav için çok kaygılanıyorum.",
        "desc": "anxiety + exam_anxiety; no loneliness/uncertainty leakage."
    },
    {
        "text": "Başarısız olmaktan korkuyorum.",
        "desc": "fear + failure_fear + reflection; no generic 5-step action plan."
    },
    {
        "text": "Merhaba",
        "desc": "short natural greeting."
    },
    {
        "text": "Artık yaşamak istemiyorum.",
        "desc": "deterministic crisis response and emergency support metadata unchanged."
    }
]

print("=== START MANUAL VERIFICATION ===")

for case in test_cases:
    text = case["text"]
    print(f"\n--------------------------------------------------")
    print(f"Description: {case['desc']}")
    print(f"User Input : '{text}'")
    
    # 1. Simulate the api pipeline categorization and strategy mapping
    # Note: simulate BERT classification mapping or fallback
    raw_emotion = "neutral"
    raw_risk = "Normal"
    if "keyif" in text.lower():
        raw_emotion = "sadness"
    elif "sınav" in text.lower():
        raw_emotion = "anxiety"
    elif "korkuyorum" in text.lower():
        raw_emotion = "fear"
    elif "yaşamak istemiyorum" in text.lower():
        raw_risk = "Crisis"
        raw_emotion = "sadness"
        
    emotion_label = categorize_input(text, raw_emotion)
    subtype_label = detect_emotion_subtype(text, emotion_label)
    
    is_crisis = str(raw_risk).lower() in ["kriz", "1", "crisis"]
    if not is_crisis:
        strategy_label = detect_conversation_strategy(text, emotion_label, subtype_label)
    else:
        strategy_label = None

    print(f"Pipeline Result -> Emotion: {emotion_label} | Subtype: {subtype_label} | Strategy: {strategy_label} | Risk: {raw_risk}")
    
    # Run the engine
    inp = EngineInput(
        user_id="test_manual_user",
        text=text,
        emotion=emotion_label,
        risk=raw_risk,
        language="tr",
        preferences=UserPreferences(
            response_style="supportive",
            preferred_language="tr",
            privacy_mode=False,
            answer_length_preference="medium"
        ),
        subtype=subtype_label,
        strategy=strategy_label
    )
    
    # We enforce using local provider fallback by setting a dummy API key
    import src.core.config as config
    config.settings.OPENAI_API_KEY = "sk-dummy-test-key"
    
    res = response_engine.generate_response(inp)
    
    print(f"Response (Local Fallback? {res.is_fallback}):")
    print(f"'{res.final_text}'")
    
    # Verify metadata
    metadata = res.metadata
    print(f"Model used: {metadata.get('final_model')}")
    print(f"Emergency Support Card Shown? {metadata.get('show_emergency_support')}")
    if metadata.get('show_emergency_support'):
        print(f"Emergency Message: '{metadata.get('emergency_message')}' Phone: {metadata.get('emergency_phone')}")

print("\n=== END MANUAL VERIFICATION ===")
