import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock/initialize required imports
from src.inference.predict import EmotionCrisisPredictor
from src.response_engine.counseling_examples import categorize_input, detect_emotion_subtype
from src.response_engine.strategy_engine import detect_conversation_strategy

print("Initializing Predictor...")
predictor = EmotionCrisisPredictor()

phrases = [
    "Bugün kendimi çok mutsuz hissediyorum.",
    "Ne yapacağımı bilmiyorum.",
    "Başarısız olmaktan korkuyorum.",
    "Yarınki sınav için çok kaygılanıyorum.",
    "Kendimi çok yalnız hissediyorum."
]

print("\n--- Verifying Phrases ---")
for phrase in phrases:
    analysis = predictor.predict_both(phrase)
    raw_emotion = analysis["emotion"]["label"]
    raw_risk = analysis["crisis_detection"]["label"]
    
    emotion = categorize_input(phrase, raw_emotion)
    subtype = detect_emotion_subtype(phrase, emotion)
    strategy = detect_conversation_strategy(phrase, emotion, subtype)
    
    print(f"Phrase: '{phrase}'")
    print(f"  Raw Emotion: {raw_emotion} | Raw Risk: {raw_risk}")
    print(f"  Resolved Emotion: {emotion} | Subtype: {subtype}")
    print(f"  Detected Strategy: {strategy}")
    print("-" * 40)
