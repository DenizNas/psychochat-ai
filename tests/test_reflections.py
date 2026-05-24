import unittest
from datetime import datetime, timezone
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    EmotionEvent,
    save_emotion_event,
    save_mood_journal,
    MoodJournal
)
from src.services.reflection_engine import generate_reflection


class TestReflections(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Reset tables for clean-room testing
        db = SessionLocal()
        try:
            db.query(EmotionEvent).delete()
            db.query(MoodJournal).delete()
            db.query(User).delete()
            
            # Seed a default test user
            test_user = User(username="reflect_user", password_hash="dummy")
            db.add(test_user)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_empty_safe_insufficient_history(self):
        """Verify that less than 4 data points returns a friendly empty fallback response."""
        # 1. Save only 2 emotion events
        for i in range(2):
            save_emotion_event(
                user_id="reflect_user",
                message_id=f"msg_e_{i}",
                emotion="Mutluluk",
                risk="düşük"
            )
            
        reflection = generate_reflection(user_id="reflect_user", period="weekly")
        
        self.assertEqual(reflection["period"], "weekly")
        self.assertEqual(reflection["reflection_title"], "Yetersiz Veri")
        self.assertEqual(reflection["reflection_text"], "Henüz yeterli veri oluşmadığı için kişisel refleksiyon üretilemedi.")
        self.assertEqual(reflection["dominant_emotion"], "neutral")

    def test_anxiety_reflection_generation(self):
        """Verify that anxiety-heavy history triggers anxiety-themed reflection."""
        # Save 4 anxiety events (reaches the threshold)
        for i in range(4):
            save_emotion_event(
                user_id="reflect_user",
                message_id=f"msg_anx_{i}",
                emotion="Kaygı",
                risk="düşük"
            )
            
        reflection = generate_reflection(user_id="reflect_user", period="weekly")
        
        self.assertEqual(reflection["period"], "weekly")
        self.assertEqual(reflection["dominant_emotion"], "anxiety")
        self.assertEqual(reflection["reflection_title"], "Haftalık İçgörü ve Refleksiyon")
        self.assertIn("kaygı ve gerginlik temalı duygu örüntülerinin", reflection["reflection_text"])
        self.assertEqual(reflection["tone"], "supportive")

    def test_mood_journal_influence(self):
        """Verify that manual mood journal logs are counted and influence threshold checks."""
        # Save 2 emotion events and 2 mood journal entries (total 4)
        for i in range(2):
            save_emotion_event("reflect_user", f"msg_mix_{i}", "Nötr", "düşük")
            
        save_mood_journal(user_id="reflect_user", mood="neutral", intensity=3)
        save_mood_journal(user_id="reflect_user", mood="neutral", intensity=4)
        
        reflection = generate_reflection(user_id="reflect_user", period="daily")
        
        self.assertEqual(reflection["period"], "daily")
        # Total messages = 2, Mood journal count = 2. Total = 4 (satisfies threshold)
        self.assertEqual(reflection["dominant_emotion"], "balanced")
        self.assertIn("balanced", reflection["dominant_emotion"])
        self.assertIn("mood_journal", reflection["generated_from"])

    def test_crisis_override_safety(self):
        """Verify that an active crisis suppresses standard mapping and shifts tone to crisis help."""
        # Save 4 normal events
        for i in range(4):
            save_emotion_event("reflect_user", f"msg_norm_{i}", "Mutluluk", "düşük")
            
        # Save 1 crisis event
        save_emotion_event(
            user_id="reflect_user",
            message_id="msg_crisis_1",
            emotion="Kriz",
            risk="kriz"
        )
        
        reflection = generate_reflection(user_id="reflect_user", period="weekly")
        
        self.assertEqual(reflection["dominant_emotion"], "crisis")
        self.assertEqual(reflection["tone"], "supportive_crisis")
        self.assertEqual(reflection["reflection_title"], "Hassas Dönem ve Destekleyici Refleksiyon")
        self.assertIn("112 Acil Çağrı veya 114 Psikolojik Destek", reflection["reflection_text"])
        self.assertNotIn("anksiyete bozukluğu", reflection["reflection_text"])
        self.assertNotIn("depresyondasın", reflection["reflection_text"].lower())

    def test_text_length_limit(self):
        """Verify that reflection text strictly respects the 1200 character cap."""
        for i in range(5):
            save_emotion_event("reflect_user", f"msg_len_{i}", "Kaygı", "düşük")
            
        reflection = generate_reflection(user_id="reflect_user", period="daily")
        self.assertLessEqual(len(reflection["reflection_text"]), 1200)


if __name__ == "__main__":
    unittest.main()
