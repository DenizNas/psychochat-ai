import unittest
import sys
import os

sys.path.insert(0, ".")

from src.response_engine.response_ranker import score_response
from src.ai_providers.local_provider import LocalProvider
from src.response_engine.safety import check_safety, get_crisis_safe_response
from src.response_engine.memory_profile import get_profile_path, add_to_profile, save_profile

class TestAntiRepetitionRanker(unittest.TestCase):

    def setUp(self):
        self.test_user = "test_rep_user"
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def tearDown(self):
        profile_path = get_profile_path(self.test_user)
        if os.path.exists(profile_path):
            os.remove(profile_path)

    def test_penalizes_standalone_generic_empathy(self):
        """1. Penalizes standalone generic empathy."""
        standalone = "Seni anlıyorum."
        res = score_response(standalone, risk="Normal")
        self.assertFalse(res.passes, "Standalone generic empathy should fail the rank check")
        self.assertIn("generic_response", res.reasons)

    def test_allows_contextual_empathy(self):
        """2. Allows contextual empathy."""
        contextual = "Bu kadar yük üst üste gelince yorulman çok anlaşılır; bugün biraz nefes alacak alan bulmak zor olabilir."
        res = score_response(contextual, risk="Normal")
        self.assertTrue(res.passes, "Contextual empathy should pass the rank check")
        self.assertNotIn("generic_response", res.reasons)

    def test_penalizes_repeated_advice(self):
        """3. Penalizes repeated advice across turns."""
        first_resp = "Nefes egzersizi yapabilirsin."
        # Seed it into user's memory profile via add_to_profile or direct mapping
        # Add 'breathing exercise' to last_advice_topics
        add_to_profile(self.test_user, "last_advice_topics", "breathing exercise")
        
        second_resp = "Bugün stres için biraz nefes egzersizi yapmayı deneyebilirsin."
        # Run rank check passing user_id to look up the memory profile
        res_profile = score_response(second_resp, risk="Normal", user_id=self.test_user)
        self.assertFalse(res_profile.passes)
        self.assertIn("repeated_advice", res_profile.reasons)
        
        # Test comparison against recent responses in current session
        res_session = score_response(
            second_resp, 
            risk="Normal", 
            recent_responses=["Geçen mesajda nefes egzersizi önermiştim."]
        )
        self.assertFalse(res_session.passes)
        self.assertIn("repeated_advice", res_session.reasons)

    def test_penalizes_too_many_questions(self):
        """4. Penalizes too many questions (3+ question marks)."""
        too_many_q = "Nasılsın? Bugün ne yaptın? Kendini nasıl hissediyorsun?"
        res = score_response(too_many_q, risk="Normal")
        self.assertFalse(res.passes, "Response with 3+ questions should fail the rank check")
        self.assertIn("too_many_questions", res.reasons)

        normal_q = "Kendini bugün nasıl hissediyorsun?"
        res_ok = score_response(normal_q, risk="Normal")
        self.assertTrue(res_ok.passes)

    def test_penalizes_robotic_memory_phrases(self):
        """5. Penalizes robotic memory phrases."""
        phrase1 = "Bu bilgi hafızamda kayıtlı."
        phrase2 = "Veritabanımda bu görünüyor."
        
        res1 = score_response(phrase1, risk="Normal")
        self.assertFalse(res1.passes)
        self.assertIn("robotic_memory_phrase", res1.reasons)

        res2 = score_response(phrase2, risk="Normal")
        self.assertFalse(res2.passes)
        self.assertIn("robotic_memory_phrase", res2.reasons)

    def test_local_provider_returns_natural_turkish(self):
        """6. Local provider returns natural Turkish and does not use English phrases."""
        lp = LocalProvider()
        # Mock messages and config
        messages = [
            {"role": "system", "content": "KULLANICI TERCİHLERİ: Yanıtın nazik ve kısa olsun. Yanıtını çok kısa tut."},
            {"role": "user", "content": "Çok mutsuzum bugün."}
        ]
        config = {"counseling_category": "sadness", "answer_length_preference": "short"}
        
        res = lp.generate(messages, config)
        self.assertEqual(res.provider, "local")
        self.assertTrue(len(res.text) > 0)
        
        # Verify no English words leaked
        english_words = ["understand", "empathy", "sorry", "sadness", "session"]
        for word in english_words:
            self.assertNotIn(word, res.text.lower())
            
        # Verify it has natural Turkish tone
        self.assertTrue(any(k in res.text for k in ["hüzün", "kırgın", "doğal", "destek", "buradayım", "normal", "zor", "paylaş"]))

    def test_crisis_safety_tests_still_pass(self):
        """7. Crisis safety tests still pass."""
        # 1. Verification of check_safety detecting crisis signals
        safe_user, reason_user = check_safety("intihar etmek istiyorum", mode="user_input")
        self.assertFalse(safe_user, "Crisis user message must be flagged as unsafe")
        self.assertEqual(reason_user, "suicide_ideation")
        
        # 2. get_crisis_safe_response returns a valid Turkish crisis template with emergency anchors
        safe_resp = get_crisis_safe_response(language="tr", category="suicide_ideation")
        self.assertTrue(any(anchor in safe_resp for anchor in ["112", "114", "güven", "destek"]))

if __name__ == "__main__":
    unittest.main()
