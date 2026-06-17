import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_engine.counseling_examples import categorize_input, detect_emotion_subtype

phrases = [
    ("Hiçbir şeyden keyif alamıyorum.", "sadness"),
    ("Yarınki sınav için çok kaygılanıyorum.", "anxiety"),
    ("Başarısız olmaktan korkuyorum.", "fear"),
    ("Ne yapacağımı bilmiyorum.", "neutral"),
    ("Hayatımın yönünü kaybettim.", "neutral"),
]

print("==========================================================")
print("EMOTION SUBTYPE CLASSIFICATION MANUAL VERIFICATION")
print("==========================================================")
for text, raw_emo in phrases:
    category = categorize_input(text, raw_emo)
    subtype = detect_emotion_subtype(text, category)
    print(f"Text:    \"{text}\"")
    print(f"Primary: {category}")
    print(f"Subtype: {subtype}")
    print("----------------------------------------------------------")
