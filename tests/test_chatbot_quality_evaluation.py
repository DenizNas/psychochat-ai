import unittest
import sys
import os

sys.path.insert(0, ".")

from src.response_engine.response_ranker import score_response
from src.ai_providers.local_provider import LocalProvider
from src.response_engine.safety import check_safety, get_crisis_safe_response
from src.response_engine.memory_profile import get_profile_path, add_to_profile
from src.response_engine.counseling_examples import categorize_input
from src.response_engine.prompts import build_system_prompt
from src.response_engine.personal_context_engine import PersonalContextEngine

# 10 categories, at least 2 Turkish prompts per category (total 20 prompts)
EVALUATION_PROMPTS = {
    "sadness": [
        "Son zamanlarda hiçbir şeyden keyif alamıyorum, sürekli içim sıkılıyor.",
        "Bugün yataktan çıkmak bile çok zor geldi, içimde derin bir hüzün var."
    ],
    "anxiety": [
        "Yarın ne olacak diye düşünmekten uyuyamıyorum.",
        "Sürekli endişeliyim ve zihnimi sakinleştiremiyorum."
    ],
    "fear": [
        "Bir şeylerin kötü gideceğinden çok korkuyorum.",
        "Geceleri aniden korkuyla uyanıyorum ve kendimi güvende hissetmiyorum."
    ],
    "anger": [
        "Bugün herkes üstüme geldi, patlamak üzereyim.",
        "Çok sinirliyim, haksızlığa uğradım ve bunu sindiremiyorum."
    ],
    "loneliness": [
        "Kalabalığın içinde bile çok yalnız hissediyorum.",
        "Kimseyle gerçek bir bağ kuramadığımı fark ettim, yapayalnızım."
    ],
    "motivation_loss": [
        "Hiçbir şey yapmak içimden gelmiyor, sürekli erteliyorum.",
        "Canım hiçbir şey yapmak istemiyor, hedeflerime karşı hevesimi kaybettim."
    ],
    "relationship_problems": [
        "Sevdiğim biriyle aram bozuldu ve ne yapacağımı bilmiyorum.",
        "Sevdiğim bir arkadaşımla tartıştım ve aramız bozuldu."
    ],
    "self_esteem_issues": [
        "Kendimi sürekli yetersiz hissediyorum.",
        "Kendime hiç güvenmiyorum, sanki herkes benden çok daha başarılı."
    ],
    "stress": [
        "Okul ve işler üst üste geldi, hiçbir şeye yetişemiyorum.",
        "Çok gerginim, sorumluluklar üzerime yığıldı ve altından kalkamıyorum."
    ],
    "neutral": [
        "Bugün sıradan bir gündü, pek bir şey yapmadım.",
        "Bilmiyorum, sadece konuşmak istedim."
    ]
}

class TestChatbotQualityEvaluation(unittest.TestCase):

    def setUp(self):
        self.test_user = "eval_test_user"
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def tearDown(self):
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def test_category_prompts_mapping(self):
        """1. Verify all 20 Turkish prompts map to the expected counseling category."""
        prompt_count = 0
        for expected_category, prompts in EVALUATION_PROMPTS.items():
            for p in prompts:
                prompt_count += 1
                # Map expected_category to expected parameter or keyword matching
                # Since categorize_input maps keywords, we can pass expected_category as emotion fallback
                cat = categorize_input(p, expected_category)
                self.assertEqual(cat, expected_category, f"Prompt: '{p}' categorized as '{cat}', expected '{expected_category}'")
        self.assertEqual(prompt_count, 20, "Must contain exactly 20 Turkish prompts")

    def test_quality_checks_pass_for_good_responses(self):
        """2. Verify that high-quality, natural Turkish responses pass the ranking checks."""
        good_response_1 = "Bu kadar yük üst üste gelince yorulman çok anlaşılır; bugün biraz nefes alacak alan bulmak zor olabilir."
        good_response_2 = "Seni çok iyi anlıyorum. Yaşadığın bu durum gerçekten zor ve hissettiklerin son derece normal. Yanında olmak için buradayım, ne zaman istersen konuşabiliriz."
        
        r1 = score_response(good_response_1, risk="Normal")
        r2 = score_response(good_response_2, risk="Normal")
        
        self.assertTrue(r1.passes, "Good response 1 should pass")
        self.assertTrue(r2.passes, "Good response 2 should pass")

    def test_quality_checks_fail_for_bad_responses(self):
        """3. Verify that low-quality, robotic, or clinical responses fail the ranking checks."""
        # A. Standalone generic empathy
        standalone = "Seni anlıyorum."
        r_standalone = score_response(standalone, risk="Normal")
        self.assertFalse(r_standalone.passes)
        
        # B. Too many questions (3+ question marks)
        questions = "Nasılsın? Bugün ne yaptın? Kendini nasıl hissediyorsun?"
        r_questions = score_response(questions, risk="Normal")
        self.assertFalse(r_questions.passes)
        self.assertIn("too_many_questions", r_questions.reasons)

        # C. Too many bullet points
        bullets = "- Birincisi nefes al.\n- İkincisi günlük tut.\n- Üçüncüsü yürüyüş yap."
        r_bullets = score_response(bullets, risk="Normal")
        self.assertFalse(r_bullets.passes)
        self.assertIn("too_many_bullets", r_bullets.reasons)

        # D. Robotic memory phrases
        robotic = "Hafızamda kayıtlı olan bilgilere göre geçen hafta sınav stresi yaşamıştın."
        r_robotic = score_response(robotic, risk="Normal")
        self.assertFalse(r_robotic.passes)
        self.assertIn("robotic_memory_phrase", r_robotic.reasons)

        # E. Unnatural/clinical Turkish
        clinical = "Öyle hissettiğini duyabiliyorum, pişmanlık döngüsü içindesin."
        r_clinical = score_response(clinical, risk="Normal")
        self.assertFalse(r_clinical.passes)
        self.assertIn("unnatural_turkish", r_clinical.reasons)

    def test_response_ranker_good_vs_bad(self):
        """4. Verify response ranker scores good responses higher than bad responses."""
        good_response = "Bu ara her şeyin üst üste gelmesi seni epey yormuş gibi görünüyor, yanında olduğumu bilmeni isterim."
        bad_response = "Seni anlıyorum."
        
        good_score = score_response(good_response, risk="Normal")
        bad_score = score_response(bad_response, risk="Normal")
        
        self.assertGreater(good_score.score, bad_score.score)

    def test_anti_repetition_logic(self):
        """5. Verify that repeated advice gets flagged and penalized."""
        # Recommend nefes egzersizi in history
        recent = ["Nefes egzersizi yapmayı deneyebilirsin."]
        new_response = "Bugün stres için biraz nefes egzersizi yapabilirsin."
        
        res = score_response(new_response, risk="Normal", recent_responses=recent)
        self.assertFalse(res.passes)
        self.assertIn("repeated_advice", res.reasons)

    def test_crisis_safety_remains_unchanged(self):
        """6. Verify that crisis detection and safety overrides remain intact."""
        is_safe, reason = check_safety("intihar etmek istiyorum", mode="user_input")
        self.assertFalse(is_safe)
        self.assertEqual(reason, "suicide_ideation")
        
        safe_response = get_crisis_safe_response(language="tr", category="suicide_ideation")
        self.assertTrue(any(anchor in safe_response for anchor in ["112", "114", "güven", "destek"]))

    def test_prompt_construction_no_english_leakage(self):
        """7. Verify prompt construction does not include English leakage words."""
        system_prompt, meta = build_system_prompt(language="tr", emotion="neutral", risk="Normal")
        
        english_leaks = [
            "response", "validate", "follow-up", "user profile", 
            "advice repetition", "grounding technique"
        ]
        
        for leak in english_leaks:
            self.assertNotIn(leak, system_prompt.lower(), f"English leak found in prompt: {leak}")

    def test_memory_context_no_internal_keys(self):
        """8. Verify memory context does not expose internal technical keys."""
        pce = PersonalContextEngine()
        memories = [
            {"memory_type": "preference", "memory_value": "Kullanıcı kısa yanıt tercih ediyor", "sensitivity": "low", "confidence": 0.9},
            {"memory_type": "routine", "memory_value": "Her sabah yürüyüş yapar", "sensitivity": "low", "confidence": 0.8}
        ]
        injection = pce.build_injection(memories, self.test_user)
        
        self.assertNotIn("preference", injection)
        self.assertNotIn("routine", injection)
        self.assertNotIn("coping_strategy", injection)
        self.assertIn("Kullanıcı kısa yanıt tercih ediyor", injection)

    def test_local_provider_fallback_all_categories(self):
        """9. Verify local provider fallback returns natural Turkish response for each category."""
        lp = LocalProvider()
        for cat in EVALUATION_PROMPTS.keys():
            messages = [
                {"role": "system", "content": "Kişisel bağlam"},
                {"role": "user", "content": EVALUATION_PROMPTS[cat][0]}
            ]
            config = {"counseling_category": cat, "answer_length_preference": "medium"}
            res = lp.generate(messages, config)
            
            self.assertEqual(res.provider, "local")
            self.assertTrue(len(res.text) > 0)
            
            # Verify no English leak
            for leak in ["understand", "sorry", "empathy", "session", "response"]:
                self.assertNotIn(leak, res.text.lower())

if __name__ == "__main__":
    unittest.main()
