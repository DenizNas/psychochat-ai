import unittest
from src.response_engine.counseling_examples import (
    categorize_input, get_few_shot_examples, COUNSELING_EXAMPLES
)
from src.response_engine.prompts import build_system_prompt, PROMPT_VERSION

class TestCounselingPrompting(unittest.TestCase):

    def test_version_bump(self):
        """Verify prompt version is bumped to v1.3.0."""
        self.assertEqual(PROMPT_VERSION, "v1.3.0")

    def test_categorize_input_keywords(self):
        """Verify keyword matching categorizes correctly with turkish_lower()."""
        # Loneliness
        self.assertEqual(categorize_input("Bugün kendimi çok YALNIZ hissediyorum.", "sadness"), "loneliness")
        # Motivation loss
        self.assertEqual(categorize_input("Hiçbir şey Yapmak isteMiyorum, canım SIKILIYOR.", "neutral"), "motivation_loss")
        # Relationship problems
        self.assertEqual(categorize_input("Eşimle sürekli kavga ediyoruz.", "anger"), "relationship_problems")
        # Self-esteem issues
        self.assertEqual(categorize_input("KENDİMİ ÇOK YETERSİZ hissediyorum.", "sadness"), "self_esteem_issues")
        # Stress
        self.assertEqual(categorize_input("Sınav stresi beni çok geriyor.", "anxiety"), "stress")

    def test_categorize_input_fallback(self):
        """Verify fallback to emotion works if no keywords match."""
        # Sadness fallback
        self.assertEqual(categorize_input("Bugün günüm kötü geçti.", "sadness"), "sadness")
        self.assertEqual(categorize_input("Bugün günüm kötü geçti.", "sad"), "sadness")
        # Anxiety fallback
        self.assertEqual(categorize_input("İçimde bir sıkışma var.", "anxiety"), "anxiety")
        # Neutral fallback
        self.assertEqual(categorize_input("Sıradan bir şey.", "happiness"), "neutral")

    def test_get_few_shot_examples(self):
        """Verify we retrieve exactly 2 unique examples when requested."""
        examples = get_few_shot_examples("yalnızım", "sadness", num_examples=2)
        self.assertEqual(len(examples), 2)
        self.assertNotEqual(examples[0]["user"], examples[1]["user"])

        # Check examples are indeed from loneliness
        all_lonely_users = {ex["user"] for ex in COUNSELING_EXAMPLES["loneliness"]}
        self.assertIn(examples[0]["user"], all_lonely_users)

    def test_build_system_prompt_non_crisis(self):
        """Verify non-crisis system prompt contains few-shot examples and style instructions."""
        prompt, meta = build_system_prompt(
            language="tr",
            emotion="sadness",
            risk="Normal",
            text="Kendimi yalnız hissediyorum."
        )

        self.assertIn("response_style_rules", meta["prompt_sections"])
        self.assertIn("few_shot_examples", meta["prompt_sections"])
        self.assertEqual(meta["counseling_category"], "loneliness")
        self.assertEqual(meta["prompt_version"], "v1.3.0")

        self.assertIn("TEPKİ STİLİ VE İLETİŞİM İLKELERİ", prompt)
        self.assertIn("DANIŞAN-ASİSTAN YANIT ÖRNEKLERİ", prompt)

        # Confirm we have diverse openings recommendation and no "Anlıyorum" repeating mandate
        self.assertIn("Yanıta başlarken sürekli kendini tekrar eden 'Anlıyorum', 'Bu zor olabilir' gibi basmakalıp, robotik giriş cümlelerini KESİNLİKLE kullanma", prompt)

    def test_build_system_prompt_crisis(self):
        """Verify crisis system prompt bypasses few-shot examples and style instructions for safety."""
        prompt, meta = build_system_prompt(
            language="tr",
            emotion="sadness",
            risk="1",
            text="Kendimi yalnız hissediyorum."
        )

        self.assertNotIn("response_style_rules", meta["prompt_sections"])
        self.assertNotIn("few_shot_examples", meta["prompt_sections"])
        self.assertEqual(meta["counseling_category"], "crisis")

        self.assertNotIn("TEPKİ STİLİ VE İLETİŞİM İLKELERİ", prompt)
        self.assertNotIn("DANIŞAN-ASİSTAN YANIT ÖRNEKLERİ", prompt)
        self.assertIn("KRİZ DURUMU", prompt)

if __name__ == "__main__":
    unittest.main()
