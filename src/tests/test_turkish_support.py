import unittest
from src.ai.preprocessing import (
    turkish_lower,
    clean_text,
    normalize_turkish_text,
    prepare_model_input
)

class TestTurkishSupport(unittest.TestCase):
    def test_turkish_lower(self):
        # Test basic Turkish uppercase letters converting to correct lowercase
        self.assertEqual(turkish_lower("IŞIK"), "ışık")
        self.assertEqual(turkish_lower("İSTANBUL"), "istanbul")
        self.assertEqual(turkish_lower("ÇĞÖŞÜ"), "çğöşü")
        self.assertEqual(turkish_lower("çğıiöşüÇĞIİÖŞÜ"), "çğıiöşüçğıiöşü")
        
        # Test standard characters
        self.assertEqual(turkish_lower("HELLO world"), "hello world")
        
        # Test None and non-string inputs
        self.assertEqual(turkish_lower(None), "")
        self.assertEqual(turkish_lower(123), "123")

    def test_clean_text_preserves_turkish(self):
        # Test that clean_text does not strip Turkish letters
        turkish_text = "Bugün çok üzgünüm çünkü özgüvenim düşük ve içim sıkılıyor."
        self.assertEqual(clean_text(turkish_text), turkish_text)
        
        # Test cleaning HTML tags and URLs but preserving Turkish text
        mixed_text = "<html><body>Deniz Işık Öztürk</body></html> http://example.com/ışık"
        cleaned = clean_text(mixed_text)
        self.assertIn("Deniz Işık Öztürk", cleaned)
        self.assertNotIn("<html>", cleaned)
        self.assertNotIn("http://", cleaned)

    def test_normalize_turkish_text(self):
        # Test whitespace normalization and NFC/NFKC formatting
        raw = "   Çok   yorgunum   "
        self.assertEqual(normalize_turkish_text(raw), "Çok yorgunum")
        
        raw_turkish = "ışık öztürk"
        self.assertEqual(normalize_turkish_text(raw_turkish), "ışık öztürk")

    def test_prepare_model_input(self):
        # Test that prepared input retains Turkish letters
        input_text = "Bugün çok üzgünüm çünkü özgüvenim düşük ve içim sıkılıyor."
        output = prepare_model_input(input_text)
        self.assertEqual(output, input_text)

if __name__ == "__main__":
    unittest.main()
