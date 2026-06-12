import unittest
import os
import shutil
from src.response_engine.memory_profile import (
    load_profile, save_profile, get_profile_path, add_to_profile,
    build_summary_for_prompt, detect_and_add_advice_topics,
    get_advice_prevention_instructions
)
from src.response_engine.memory_extractor import extract_and_update_profile
from src.response_engine.personal_context_engine import PersonalContextEngine

class TestLongTermMemory(unittest.TestCase):

    def setUp(self):
        # Backup/clean test profiles
        self.test_user = "test_lt_user"
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def tearDown(self):
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def test_get_profile_path_sanitization_and_traversal(self):
        """Verify get_profile_path sanitizes usernames and blocks path traversal."""
        path = get_profile_path("Deniz Nas 123!@#")
        self.assertIn("DenizNas123.json", path)

        # Path traversal guard
        with self.assertRaises(ValueError):
            get_profile_path("../../../attack")

    def test_rule_based_extraction(self):
        """Verify extractor detects stressors, relations, academic context, and goals correctly."""
        # 1. Test exam stressors
        extract_and_update_profile(self.test_user, "Bu ara sınavlar yüzünden çok stresliyim.", "anxiety", "Normal")
        profile = load_profile(self.test_user)
        self.assertIn("sınav stresi", profile["stressors"])
        self.assertIn("akademik süreç", profile["work_or_school_context"])

        # 2. Test sleep issues
        extract_and_update_profile(self.test_user, "Bu gece yine hiç uyuyamadım, uyku sorunum var.", "sadness", "Normal")
        profile = load_profile(self.test_user)
        self.assertIn("uyku sorunları", profile["stressors"])

        # 3. Test loneliness
        extract_and_update_profile(self.test_user, "Kendimi çok yalnız hissediyorum.", "sadness", "Normal")
        profile = load_profile(self.test_user)
        self.assertIn("yalnızlık", profile["stressors"])

        # 4. Test motivation issues
        extract_and_update_profile(self.test_user, "Hiçbir şey yapmak içimden gelmiyor, çok isteksizim.", "neutral", "Normal")
        profile = load_profile(self.test_user)
        self.assertIn("motivasyon kaybı", profile["stressors"])

        # 5. Test goals mapping
        extract_and_update_profile(self.test_user, "Hedefim uyku düzenimi düzeltmek.", "neutral", "Normal")
        profile = load_profile(self.test_user)
        self.assertIn("sleep improvement", profile["goals"])

    def test_profile_summary_line_limits(self):
        """Verify summary does not exceed 10 lines and is based on facts."""
        add_to_profile(self.test_user, "stressors", "sınav stresi")
        add_to_profile(self.test_user, "stressors", "uyku sorunları")
        add_to_profile(self.test_user, "goals", "sleep improvement")
        add_to_profile(self.test_user, "goals", "stress management")
        add_to_profile(self.test_user, "coping_methods", "günlük tutmak")
        add_to_profile(self.test_user, "relationship_context", "partner ilişkisi")
        add_to_profile(self.test_user, "work_or_school_context", "akademik süreç")

        summary = build_summary_for_prompt(self.test_user)
        lines = summary.split("\n")
        self.assertLessEqual(len(lines), 10)
        self.assertIn("Kullanıcı Profil Özeti:", lines[0])
        self.assertTrue(any("sınav stresi" in l for l in lines))

    def test_memory_safety_blocks(self):
        """Verify passwords, tokens, API keys, and raw crisis text are not extracted."""
        # Crisis text should be rejected
        extract_and_update_profile(self.test_user, "Yürüyüş iyi geliyor ama intihar etmek istiyorum.", "sadness", "1")
        profile = load_profile(self.test_user)
        self.assertEqual(len(profile["stressors"]), 0)

        # Credentials should be rejected
        extract_and_update_profile(self.test_user, "Şifrem 123456 olup spor bana iyi geliyor.", "neutral", "Normal")
        profile = load_profile(self.test_user)
        self.assertEqual(len(profile["coping_methods"]), 0)

    def test_advice_repetition_tracking(self):
        """Verify suggested advice topics are detected and stored, and advice guidelines are generated."""
        detect_and_add_advice_topics(self.test_user, "Nefes egzersizi yapmayı ve günlüğe yazmayı deneyebilirsin.")
        profile = load_profile(self.test_user)
        self.assertIn("breathing exercise", profile["last_advice_topics"])
        self.assertIn("journaling", profile["last_advice_topics"])

        instructions = get_advice_prevention_instructions(self.test_user)
        self.assertIn("nefes egzersizi", instructions)
        self.assertIn("Tavsiye Tekrarını Önleme Kuralı", instructions)

    def test_pce_integration_non_crisis(self):
        """Verify PersonalContextEngine injects the profile summary and advice instructions."""
        add_to_profile(self.test_user, "stressors", "sınav stresi")
        detect_and_add_advice_topics(self.test_user, "Nefes egzersizi yap.")

        pce = PersonalContextEngine()
        turn_res = pce.process_turn(
            user_id=self.test_user,
            text="Sınavlar beni yoruyor.",
            emotion="anxiety",
            risk="Normal",
            privacy_mode=False
        )

        self.assertTrue(turn_res["memory_injected"])
        self.assertIn("Kullanıcı Profil Özeti:", turn_res["injection_text"])
        self.assertIn("Son Önerilen Tavsiyeler", turn_res["injection_text"])

    def test_pce_integration_crisis_bypasses(self):
        """Verify PersonalContextEngine bypasses profile memory completely during crisis turns."""
        add_to_profile(self.test_user, "stressors", "sınav stresi")
        pce = PersonalContextEngine()
        turn_res = pce.process_turn(
            user_id=self.test_user,
            text="İntihar etmek istiyorum.",
            emotion="sadness",
            risk="1",
            privacy_mode=False
        )

        self.assertFalse(turn_res["memory_injected"])
        self.assertEqual(turn_res["injection_text"], "")

if __name__ == "__main__":
    unittest.main()
