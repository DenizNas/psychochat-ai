import unittest
from datetime import datetime, timezone
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    EmotionEvent,
    save_emotion_event
)
from src.services.wellness_reports import generate_wellness_report


class TestWellnessReports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Clear database and recreate clean state before each test
        db = SessionLocal()
        try:
            db.query(EmotionEvent).delete()
            db.query(User).delete()
            
            # Create a test user
            test_user = User(username="report_user", password_hash="dummy")
            db.add(test_user)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_empty_safe_insufficient_history(self):
        """Verify that less than 4 emotion timeline events yields a friendly empty fallback response."""
        # Save only 2 events
        for i in range(2):
            save_emotion_event(
                user_id="report_user",
                message_id=f"msg_empty_{i}",
                emotion="Mutluluk",
                risk="düşük"
            )
            
        report = generate_wellness_report(user_id="report_user", period="weekly", days=7)
        
        self.assertEqual(report["period"], "weekly")
        self.assertEqual(report["summary_title"], "Henüz yeterli veri oluşmadı.")
        self.assertIn("en az 4 günlük sohbet geçmişi", report["summary_text"])
        self.assertEqual(report["dominant_emotion"], "Nötr")
        self.assertEqual(report["total_messages"], 2)
        self.assertEqual(len(report["highlights"]), 0)
        self.assertGreater(len(report["suggestions"]), 0)

    def test_anxiety_report_mapping(self):
        """Verify that Kaygı triggers the anxiety-themed non-diagnostic wellness report."""
        # Save 5 anxiety events to cross the threshold of 4
        for i in range(5):
            save_emotion_event(
                user_id="report_user",
                message_id=f"msg_anx_{i}",
                emotion="Kaygı",
                risk="düşük"
            )
            
        report = generate_wellness_report(user_id="report_user", period="daily", days=7)
        
        self.assertEqual(report["period"], "daily")
        self.assertEqual(report["dominant_emotion"], "anxiety")
        self.assertEqual(report["summary_title"], "Dengede Kaygı ve Stres Yönetimi")
        self.assertIn("gerginlik benzeri duygu tonlarının öne çıktığı gözlemlendi", report["summary_text"])
        self.assertGreater(len(report["highlights"]), 0)
        self.assertGreater(len(report["suggestions"]), 0)
        
        # Verify maximum limits
        self.assertLessEqual(len(report["highlights"]), 5)
        self.assertLessEqual(len(report["suggestions"]), 5)

    def test_sadness_report_mapping(self):
        """Verify that Üzüntü triggers the sadness-themed non-diagnostic wellness report."""
        # Save 6 sadness events
        for i in range(6):
            save_emotion_event(
                user_id="report_user",
                message_id=f"msg_sad_{i}",
                emotion="Üzüntü",
                risk="düşük"
            )
            
        report = generate_wellness_report(user_id="report_user", period="weekly", days=7)
        
        self.assertEqual(report["dominant_emotion"], "sadness")
        self.assertEqual(report["summary_title"], "İçe Dönüş ve Dinginlik Dönemi")
        self.assertIn("hüzün veya melankoli", report["summary_text"])

    def test_crisis_override_safety(self):
        """Verify that an active crisis suppresses standard mapping and returns gentle safety guidance."""
        # Save 4 normal events
        for i in range(4):
            save_emotion_event("report_user", f"msg_norm_{i}", "Kaygı", "düşük")
        # Save 1 crisis event
        save_emotion_event(
            user_id="report_user",
            message_id="msg_crisis_1",
            emotion="Kriz",
            risk="kriz"
        )
        
        report = generate_wellness_report(user_id="report_user", period="weekly", days=7)
        
        self.assertEqual(report["dominant_emotion"], "crisis")
        self.assertEqual(report["summary_title"], "Hassas Dönem & Öncelikli Destek Hatırlatıcısı")
        self.assertIn("112 Acil Çağrı veya 114 Psikolojik Destek", str(report["suggestions"]))
        self.assertNotIn("Depresyondasın", report["summary_text"])
        self.assertNotIn("anksiyete", report["summary_text"].lower())


if __name__ == "__main__":
    unittest.main()
