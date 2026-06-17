import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_engine.variation_engine import select_linguistic_variants
from src.response_engine.counseling_examples import categorize_input, detect_emotion_subtype
from src.response_engine.strategy_engine import detect_conversation_strategy
from src.inference.predict import EmotionCrisisPredictor

print("Initializing Predictor...")
predictor = EmotionCrisisPredictor()

# 1. Simulate Sadness consecutively
print("\n=== Test 1: Sadness Messages Consecutively ===")
sad_history = []
for i in range(1, 4):
    text = "Bugün kendimi çok mutsuz hissediyorum."
    analysis = predictor.predict_both(text)
    emotion = categorize_input(text, analysis["emotion"]["label"])
    subtype = detect_emotion_subtype(text, emotion)
    strategy = detect_conversation_strategy(text, emotion, subtype)
    
    var_id, directive = select_linguistic_variants(sad_history, emotion, subtype, strategy)
    print(f"Turn {i}: '{text}'")
    print(f"  Emotion: {emotion} | Strategy: {strategy}")
    print(f"  Selected Variant ID: {var_id}")
    print(f"  Directive: {directive}")
    # Add variant to simulated assistant history (using some placeholder text containing variant keywords to filter it out)
    if var_id == "val_1":
        sad_history.append("Bu yükü taşırken ne kadar yorulduğunu görebiliyorum. Paylaşman çok değerli.")
    elif var_id == "val_2":
        sad_history.append("Bunun seni ne kadar yorduğunu hissedebiliyorum. Duygularını hissetmene izin ver.")
    elif var_id == "val_3":
        sad_history.append("Bu duygularla tek başına baş etmeye çalışmak kolay görünmüyor, yanındayım.")
    elif var_id == "val_4":
        sad_history.append("Yaşadığın şeyin ağırlığını en derinden duyabiliyorum. Bu hislerinde yalnız değilsin.")

# 2. Simulate Anxiety consecutively
print("\n=== Test 2: Anxiety/Fear Messages Consecutively ===")
anx_history = []
for i in range(1, 4):
    text = "Yarınki sınav için çok kaygılanıyorum."
    analysis = predictor.predict_both(text)
    emotion = categorize_input(text, analysis["emotion"]["label"])
    subtype = detect_emotion_subtype(text, emotion)
    strategy = detect_conversation_strategy(text, emotion, subtype)
    
    var_id, directive = select_linguistic_variants(anx_history, emotion, subtype, strategy)
    print(f"Turn {i}: '{text}'")
    print(f"  Emotion: {emotion} | Strategy: {strategy}")
    print(f"  Selected Variant ID: {var_id}")
    print(f"  Directive: {directive}")
    if var_id == "psy_1":
        anx_history.append("Zihnimiz belirsizlik ve baskı durumlarında tehdit algılayıp bu tarz alarm tepkileri verebilir.")
    elif var_id == "psy_2":
        anx_history.append("Psikolojik olarak, bu tür yoğun kaygılar bedenin kendini korumaya yönelik geliştirdiği otomatik bir uyarılma halidir.")
    elif var_id == "psy_3":
        anx_history.append("İçsel dengemiz bazen dış beklentiler ve gelecek kaygısı altında gerilebilir, bu geçici bir tepkidir.")

# 3. Simulate Crisis messages
print("\n=== Test 3: Crisis Messages ===")
crisis_text = "Kendimi öldürmek istiyorum."
analysis = predictor.predict_both(crisis_text)
emotion = categorize_input(crisis_text, analysis["emotion"]["label"])
subtype = detect_emotion_subtype(crisis_text, emotion)
strategy = detect_conversation_strategy(crisis_text, emotion, subtype)
is_crisis = str(analysis["crisis_detection"]["label"]).lower() in ["kriz", "1", "crisis"]

print(f"Message: '{crisis_text}'")
print(f"  Emotion: {emotion} | Risk: {analysis['crisis_detection']['label']}")
print(f"  Is Crisis: {is_crisis}")
if is_crisis:
    print("  Variation Engine bypassed completely (No variants selected).")
else:
    var_id, directive = select_linguistic_variants([], emotion, subtype, strategy)
    print(f"  Selected Variant ID: {var_id}")

# 4. Simulate Greetings / Neutral
print("\n=== Test 4: Greeting / Neutral ===")
greeting_text = "Merhaba"
analysis = predictor.predict_both(greeting_text)
emotion = categorize_input(greeting_text, analysis["emotion"]["label"])
subtype = detect_emotion_subtype(greeting_text, emotion)
strategy = detect_conversation_strategy(greeting_text, emotion, subtype)

var_id, directive = select_linguistic_variants([], emotion, subtype, strategy)
print(f"Message: '{greeting_text}'")
print(f"  Emotion: {emotion} | Strategy: {strategy}")
print(f"  Selected Variant ID: {var_id}")
print(f"  Directive: {directive}")
