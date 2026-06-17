import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_engine.counseling_examples import categorize_input, detect_emotion_subtype
from src.response_engine.strategy_engine import detect_conversation_strategy
from src.response_engine.prompts import build_system_prompt

phrases = [
    ("Hiçbir şeyden keyif alamıyorum.", "sadness"),
    ("Yarınki sınav için çok kaygılanıyorum.", "anxiety"),
    ("Başarısız olmaktan korkuyorum.", "fear"),
]

for text, raw_emo in phrases:
    category = categorize_input(text, raw_emo)
    subtype = detect_emotion_subtype(text, category)
    strategy = detect_conversation_strategy(text, category, subtype)
    
    # Build the system prompt
    sys_prompt, meta = build_system_prompt(
        language="tr",
        emotion=category,
        risk="Normal",
        memory_context="",
        preferences={"response_style": "supportive", "answer_length_preference": "medium"},
        text=text,
        subtype=subtype,
        strategy=strategy,
        variation_directive=None
    )
    
    print("==========================================================")
    print(f"Text:     \"{text}\"")
    print(f"Category: {category} | Subtype: {subtype} | Strategy: {strategy}")
    print("------------------------- PROMPT -------------------------")
    print(sys_prompt)
    print("==========================================================\n")
