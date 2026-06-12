import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from decimal import Decimal
from src.api.main import app, get_current_user
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    EmotionEvent,
    MoodJournal,
    UserSubscription,
    SubscriptionPlan,
    SubscriptionStatus,
    save_emotion_event,
    save_mood_journal
)
from src.services.wellness_dashboard import generate_wellness_dashboard


class TestWellnessDashboard(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        # Reset DB tables
        db = SessionLocal()
        try:
            db.query(UserSubscription).delete()
            db.query(SubscriptionPlan).delete()
            db.query(EmotionEvent).delete()
            db.query(MoodJournal).delete()
            db.query(User).delete()
            
            # Seed premium plan
            premium_plan = SubscriptionPlan(
                id=2,
                name="premium",
                price_lira=Decimal("199.99"),
                billing_interval="monthly",
                description="Premium",
                is_active=True
            )
            db.add(premium_plan)
            db.commit()
            
            # Seed a default test user
            test_user = User(username="test_user", password_hash="dummy")
            db.add(test_user)
            db.commit()

            # Seed subscription
            sub = UserSubscription(
                user_id="test_user",
                plan_id=2,
                status=SubscriptionStatus.ACTIVE
            )
            db.add(sub)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()


    def test_empty_safe_insufficient_history(self):
        """Verify that less than 4 data points returns score: null with 'Yetersiz Veri' label."""
        # 1. Save only 2 emotion events
        for i in range(2):
            save_emotion_event(
                user_id="test_user",
                message_id=f"msg_e_{i}",
                emotion="Mutluluk",
                risk="düşük"
            )
            
        dashboard = generate_wellness_dashboard(user_id="test_user", days=7)
        
        self.assertEqual(dashboard["days"], 7)
        self.assertIsNone(dashboard["wellness_score"]["score"])
        self.assertEqual(dashboard["wellness_score"]["label"], "Yetersiz Veri")
        self.assertIn("yeterli veri oluşmadığı", dashboard["wellness_score"]["description"])

    def test_normal_score_generation(self):
        """Verify that normal data calculates expected wellness score and populates dashboard sections."""
        # 4 events to meet threshold
        save_emotion_event("test_user", "msg_1", "Mutluluk", "düşük")
        save_emotion_event("test_user", "msg_2", "Sakin", "düşük")
        save_emotion_event("test_user", "msg_3", "Kaygı", "düşük")
        save_emotion_event("test_user", "msg_4", "Nötr", "düşük")

        save_mood_journal(user_id="test_user", mood="happy", intensity=4, note="Harika bir gün")

        dashboard = generate_wellness_dashboard(user_id="test_user", days=7)
        
        self.assertEqual(dashboard["days"], 7)
        self.assertIsNotNone(dashboard["wellness_score"]["score"])
        # Base: 70
        # Positive emotions: "Mutluluk", "Sakin" -> +10
        # Negative emotions: "Kaygı" -> -4
        # Journal positive: "happy" intensity 4 -> +8
        # stress_increase insight generated due to timeline -> -15
        # Expected score: 70 + 10 - 4 + 8 - 15 = 69
        self.assertEqual(dashboard["wellness_score"]["score"], 69)
        self.assertEqual(dashboard["overview"]["total_messages"], 4)
        self.assertEqual(dashboard["overview"]["journal_count"], 1)

    def test_crisis_score_cap(self):
        """Verify that any active crisis override caps the wellness score to 40."""
        # Need at least 4 data points
        for i in range(3):
            save_emotion_event("test_user", f"msg_pos_{i}", "Mutluluk", "düşük")
            
        # Add 1 crisis event
        save_emotion_event("test_user", "msg_crisis", "Kriz", "kriz")
        
        dashboard = generate_wellness_dashboard(user_id="test_user", days=7)
        
        self.assertEqual(dashboard["overview"]["crisis_count"], 1)
        self.assertIsNotNone(dashboard["wellness_score"]["score"])
        self.assertLessEqual(dashboard["wellness_score"]["score"], 40)
        self.assertEqual(dashboard["wellness_score"]["label"], "Yoğun Duygusal Dönem")

    def test_dashboard_api_endpoint(self):
        """Verify GET /analytics/dashboard endpoint with mocked current user."""
        # Add sufficient history
        for i in range(4):
            save_emotion_event("test_user", f"msg_api_{i}", "Sakin", "düşük")

        # Override dependency to mock authenticated user
        app.dependency_overrides[get_current_user] = lambda: "test_user"
        try:
            response = self.client.get("/analytics/dashboard?days=7")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["days"], 7)
            self.assertIsNotNone(data["wellness_score"]["score"])
            self.assertEqual(data["overview"]["total_messages"], 4)
        finally:
            app.dependency_overrides.clear()

    def test_dashboard_api_validation(self):
        """Verify endpoint validation for invalid days param."""
        app.dependency_overrides[get_current_user] = lambda: "test_user"
        try:
            response = self.client.get("/analytics/dashboard?days=15")
            self.assertEqual(response.status_code, 400)
            self.assertIn("Gün parametresi 7 veya 30 olmalıdır.", response.json()["message"])
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
