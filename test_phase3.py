import os
import sys
import json
import subprocess
from pathlib import Path

def test_preprocessing():
    print("--- Preprocessing Tests ---")
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from src.ai.preprocessing import prepare_model_input
        
        # 1. UTF-8 predict testi
        t1 = "Öğrenciyim, çünkü sınav stresim çok yüksek."
        r1 = prepare_model_input(t1)
        assert "Öğrenciyim, çünkü sınav stresim çok yüksek." in r1
        
        # 2. Emoji testi
        t2 = "Bugün aşırı mutluyum 😊"
        r2 = prepare_model_input(t2)
        assert "Bugün aşırı mutluyum 😊" in r2
        
        # 3. HTML temizleme testi
        t3 = "<script>alert('x')</script> çok üzgünüm"
        r3 = prepare_model_input(t3)
        assert "alert('x') çok üzgünüm" in r3
        
        # 4. URL temizleme testi
        t4 = "https://example.com Kendimi kötü hissediyorum"
        r4 = prepare_model_input(t4)
        assert "Kendimi kötü hissediyorum" in r4
        
        # 5. Anlamsız input testi
        try:
            prepare_model_input("!!!")
            assert False, "Should have failed"
        except ValueError:
            pass
            
        # 6. Sadece emoji testi
        try:
            prepare_model_input("😊😊😊")
            assert False, "Should have failed"
        except ValueError:
            pass
            
        # 7. Boş input testi
        try:
            prepare_model_input("")
            assert False, "Should have failed"
        except ValueError:
            pass
            
        print("PASS: Preprocessing tests passed.")
    except Exception as e:
        print(f"FAIL: Preprocessing tests failed. {e}")

def test_imports_paths():
    print("--- Imports & Paths Tests ---")
    try:
        from src.core.paths import EMOTION_MODEL_DIR_STR, CRISIS_MODEL_DIR_STR
        from src.core.text_utils import normalize_turkish_text
        assert EMOTION_MODEL_DIR_STR.endswith("models\\emotion_model") or EMOTION_MODEL_DIR_STR.endswith("models/emotion_model")
        print("PASS: Imports & Paths tests passed.")
    except Exception as e:
        print(f"FAIL: Imports & Paths tests failed. {e}")

def main():
    test_preprocessing()
    test_imports_paths()
    print("--- Review complete ---")

if __name__ == "__main__":
    main()
