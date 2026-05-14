import pandas as pd
import os

dummy_data = [
    {"text": "Kendimi çok kötü hissediyorum.", "emotion": "sadness", "crisis": 0},
    {"text": "Bugün aşırı mutluyum 😊", "emotion": "happy", "crisis": 0},
    {"text": "Öğrenciyim, çünkü sınav stresim çok yüksek.", "emotion": "fear", "crisis": "0"},
    {"text": "Seni öldüreceğim!", "emotion": "anger", "crisis": 1},
    {"text": "", "emotion": "sadness", "crisis": 1}, # empty_text
    {"text": "Kendimi çok kötü hissediyorum.", "emotion": "sadness", "crisis": 0}, # duplicate_text
    {"text": "Harika", "emotion": "joy", "crisis": 0}, # invalid_emotion_label
    {"text": "Bilmiyorum", "emotion": "neutral", "crisis": 2}, # invalid_crisis_value
    {"text": "https://example.com URL içeren text", "emotion": "sadness", "crisis": 0}, # clean url
    {"text": "<script>alert('x')</script> HTML script içeren", "emotion": "anger", "crisis": 0}, # clean html
    {"text": "!!!", "emotion": "sadness", "crisis": 0}, # meaningless_input
    {"text": "😊😊😊", "emotion": "happy", "crisis": 0}, # meaningless_input
]

os.makedirs("data/raw", exist_ok=True)
pd.DataFrame(dummy_data).to_csv("data/raw/test_dummy.csv", index=False, encoding="utf-8")
print("Dummy dataset created at data/raw/test_dummy.csv")
