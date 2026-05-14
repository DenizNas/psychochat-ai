import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ai.preprocessing import prepare_model_input

tests = [
    "Kendimi çok kötü hissediyorum.",
    "Bugün aşırı mutluyum 😊",
    "Öğrenciyim ve sınav stresim var.",
    "    Çok    yorgunum     ",
    "https://example.com Kendimi kötü hissediyorum",
    "<script>alert('x')</script> çok üzgünüm",
    "!!!",
    "😊😊😊",
    "",
    None
]

for t in tests:
    try:
        res = prepare_model_input(t)
        print(f"INPUT: {repr(t)} => OUTPUT: {repr(res)}")
    except ValueError as e:
        print(f"INPUT: {repr(t)} => REJECTED: {e}")
