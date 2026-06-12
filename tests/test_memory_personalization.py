import unittest
import os
from src.response_engine.memory_profile import (
    load_profile, save_profile, get_profile_path, add_to_profile,
    build_summary_for_prompt, detect_and_add_advice_topics,
    get_advice_prevention_instructions
)
from src.response_engine.memory_extractor import extract_and_update_profile
from src.response_engine.personal_context_engine import PersonalContextEngine
from src.response_engine.prompts import build_system_prompt, get_memory_instructions
from src.response_engine.response_ranker import score_response

class TestMemoryPersonalization(unittest.TestCase):

    def setUp(self):
        self.test_user = "test_pers_user"
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def tearDown(self):
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def test_summary_natural_turkish_no_english(self):
        """1. Memory summary is Turkish and does not contain English headers."""
        add_to_profile(self.test_user, "stressors", "sınav stresi")
        add_to_profile(self.test_user, "goals", "sleep improvement")
        add_to_profile(self.test_user, "coping_methods", "günlük tutmak")
        add_to_profile(self.test_user, "relationship_context", "partner ilişkisi")
        add_to_profile(self.test_user, "work_or_school_context", "akademik süreç")

        summary = build_summary_for_prompt(self.test_user)
        self.assertIn("Kullanıcı Profil Özeti:", summary)
        
        # Verify it doesn't contain English headers/categories
        self.assertNotIn("User Profile Summary", summary)
        self.assertNotIn("Advice Repetition Rule", summary)
        self.assertNotIn("recurring stressors", summary)
        self.assertNotIn("coping methods", summary)
        self.assertNotIn("stressors", summary)
        self.assertNotIn("goals", summary)
        
        # Verify natural Turkish statements
        self.assertIn("Son zamanlarda sınav stresi nedeniyle stres/kaygı yaşıyor olabilir.", summary)
        self.assertIn("uyku düzenini iyileştirme", summary)
        self.assertIn("Kendisine iyi gelen/yardımcı olan baş etme yöntemi: günlük tutmak.", summary)

    def test_memory_prompt_no_internal_categories(self):
        """2. Memory prompt does not expose internal categories."""
        pce = PersonalContextEngine()
        memories = [
            {"memory_type": "preference", "memory_value": "Kullanıcı kısa cevap tercih ediyor", "sensitivity": "low", "confidence": 0.9},
            {"memory_type": "routine", "memory_value": "Her sabah yürüyüş yapar", "sensitivity": "low", "confidence": 0.8}
        ]
        injection = pce.build_injection(memories, self.test_user)
        
        # Verify no raw category names are exposed
        self.assertNotIn("preference", injection)
        self.assertNotIn("routine", injection)
        self.assertNotIn("coping_strategy", injection)
        self.assertNotIn("wellness_pattern", injection)
        self.assertIn("Kullanıcı kısa cevap tercih ediyor", injection)
        self.assertIn("Her sabah yürüyüş yapar", injection)

    def test_advice_translation_and_natural_rules(self):
        """3. Advice repetition rule translates advice topics naturally and prevents duplication."""
        detect_and_add_advice_topics(self.test_user, "Nefes egzersizi yapabilir ve günlük tutabilirsin.")
        detect_and_add_advice_topics(self.test_user, "Biraz yürüyüşe çıkmak iyi gelebilir.")
        
        profile = load_profile(self.test_user)
        self.assertIn("breathing exercise", profile["last_advice_topics"])
        self.assertIn("journaling", profile["last_advice_topics"])
        self.assertIn("walking", profile["last_advice_topics"])
        
        instructions = get_advice_prevention_instructions(self.test_user)
        self.assertIn("nefes egzersizi", instructions)
        self.assertIn("günlük tutma", instructions)
        self.assertIn("yürüyüş", instructions)
        
        # Verify natural tone rules are included
        self.assertIn("aynı önerileri şablon gibi tekrarlamaktan kaçın", instructions)
        self.assertIn("Bunu daha önce denediysen, aynı öneriyi tekrar etmek yerine", instructions)
        self.assertIn("Geçen sefer nefes egzersizi gibi daha bedensel bir yöntemden", instructions)

    def test_crisis_does_not_update_memory(self):
        """4. Crisis message does not update memory."""
        # Active crisis turn (risk="1")
        extract_and_update_profile(self.test_user, "Bugün sınav stresi yaşadım ve intihar etmek istiyorum.", "sadness", "1")
        profile = load_profile(self.test_user)
        self.assertEqual(len(profile["stressors"]), 0)

        # PCE process turn checks
        pce = PersonalContextEngine()
        turn_res = pce.process_turn(self.test_user, "Kendime zarar vermek istiyorum.", "sadness", "1")
        self.assertFalse(turn_res["memory_injected"])
        self.assertEqual(turn_res["injection_text"], "")

    def test_memory_use_instruction_natural_guidelines(self):
        """5. Memory use instruction says memory should be used only when natural."""
        instructions = get_memory_instructions("Kullanıcı sınav stresi yaşıyor.")
        self.assertIn("GEÇMİŞ KONUŞMALARDAN EDİNİLEN BAĞLAM:", instructions)
        self.assertIn("BELLEK/BELLEK KULLANIM KURALLARI:", instructions)
        self.assertIn("yalnızca konuşma akışı uygunsa yumuşakça ve doğal bir şekilde", instructions)
        self.assertIn("Hafızayı her yanıtta kullanma; sadece anlamlı ve empatiyi artıracak", instructions)
        self.assertIn("Yanıtlarda asla 'hafızamda var', 'sistemde kayıtlı'", instructions)

    def test_prompt_construction_safety_and_memory(self):
        """6. Prompt construction includes memory context without breaking safety."""
        # Non-crisis prompt construction
        system_prompt, meta = build_system_prompt(
            language="tr",
            emotion="neutral",
            risk="Normal",
            memory_context="Kullanıcı sınav stresi yaşıyor.",
            text="Sınavlar beni yoruyor."
        )
        self.assertIn("GEÇMİŞ KONUŞMALARDAN EDİNİLEN BAĞLAM:", system_prompt)
        self.assertIn("BELLEK/BELLEK KULLANIM KURALLARI:", system_prompt)
        self.assertIn("memory", meta["prompt_sections"])

        # Crisis prompt construction
        system_prompt_crisis, meta_crisis = build_system_prompt(
            language="tr",
            emotion="neutral",
            risk="1",
            memory_context="Kullanıcı sınav stresi yaşıyor.",
            text="İntihar etmek istiyorum."
        )
        self.assertNotIn("GEÇMİŞ KONUŞMALARDAN EDİNİLEN BAĞLAM:", system_prompt_crisis)
        self.assertNotIn("memory", meta_crisis["prompt_sections"])

    def test_robotic_memory_phrase_penalty(self):
        """7. Score response penalizes robotic memory phrases."""
        good_response = "Bunu yapmayı deneyebilirsin, sana faydalı olacağını düşünüyorum."
        robotic_response = "Sistemde kayıtlı olan bilgilere göre daha önce sınav stresi yaşamıştın."
        
        good_score = score_response(good_response, risk="Normal")
        robotic_score = score_response(robotic_response, risk="Normal")
        
        self.assertTrue(good_score.passes)
        self.assertFalse(robotic_score.passes)
        self.assertIn("robotic_memory_phrase", robotic_score.reasons)

if __name__ == "__main__":
    unittest.main()
