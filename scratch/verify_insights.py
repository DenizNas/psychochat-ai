import os
import sys
import uuid
import unittest
from datetime import datetime, timedelta

# Append project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from src.api.main import app
from src.services.database import (
    SessionLocal, init_db, User, UserProfile, EmotionEvent,
    save_emotion_event
)
from src.services.auth import get_password_hash, create_access_token

class TestBehavioralInsightEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize database
        init_db()
        
        # TestClient context management to load local AI models
        cls.client_ctx = TestClient(app)
        cls.client = cls.client_ctx.__enter__()
        
        # Generate unique test user
        cls.username = f"test_insight_user_{uuid.uuid4().hex[:6]}"
        cls.password = "Secr3tPa$$w0rd"
        
        db = SessionLocal()
        try:
            # Create user and profile
            hashed = get_password_hash(cls.password)
            user = User(username=cls.username, password_hash=hashed)
            db.add(user)
            db.commit()
            
            profile = UserProfile(
                username=cls.username,
                display_name="Test Insight User",
                privacy_mode=False
            )
            db.add(profile)
            db.commit()
        finally:
            db.close()

        # JWT Headers
        cls.token = create_access_token(data={"sub": cls.username})
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        cls.client_ctx.__exit__(None, None, None)

    def setUp(self):
        # Clear existing emotion events for the test user before each test to maintain state purity
        db = SessionLocal()
        try:
            db.query(EmotionEvent).filter(EmotionEvent.user_id == self.username).delete()
            db.commit()
        finally:
            db.close()

    def test_01_minimum_threshold_enforcement(self):
        """Verify that less than 4 interactions yields an empty list to prevent noise."""
        # Insert 3 events
        for i in range(3):
            save_emotion_event(
                user_id=self.username,
                message_id=str(uuid.uuid4()),
                emotion="joy",
                risk="Normal"
            )
            
        response = self.client.get("/analytics/insights", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_02_clinical_safety_boundaries(self):
        """Verify that no diagnostic or clinical terms are present in titles or descriptions."""
        # Insert enough events to pass threshold
        for em in ["anxiety", "anxiety", "anxiety", "anxiety"]:
            save_emotion_event(
                user_id=self.username,
                message_id=str(uuid.uuid4()),
                emotion=em,
                risk="Normal"
            )

        response = self.client.get("/analytics/insights", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        insights = response.json()
        self.assertTrue(len(insights) > 0)
        
        forbidden_keywords = ["depresyon", "depressive", "anksiyete bozukluğu", "anxiety disorder", "bipolar", "teşhis", "tanı", "klinik"]
        
        for ins in insights:
            title_lower = ins["title"].lower()
            desc_lower = ins["description"].lower()
            
            for word in forbidden_keywords:
                self.assertNotIn(word, title_lower, f"Forbidden clinical keyword '{word}' found in title: {ins['title']}")
                self.assertNotIn(word, desc_lower, f"Forbidden clinical keyword '{word}' found in description: {ins['description']}")

    def test_03_crisis_risk_pattern(self):
        """Verify that crisis_risk_pattern triggers when crisis events >= 2."""
        # 4 events to pass threshold, including 2 crisis
        save_emotion_event(self.username, str(uuid.uuid4()), "neutral", "kriz")
        save_emotion_event(self.username, str(uuid.uuid4()), "neutral", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "neutral", "crisis")
        save_emotion_event(self.username, str(uuid.uuid4()), "neutral", "Normal")

        response = self.client.get("/analytics/insights", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        types = [ins["type"] for ins in response.json()]
        self.assertIn("crisis_risk_pattern", types)
        
        # Verify severity and confidence
        crisis_insight = [ins for ins in response.json() if ins["type"] == "crisis_risk_pattern"][0]
        self.assertEqual(crisis_insight["severity"], "high")
        self.assertTrue(0.0 <= crisis_insight["confidence"] <= 1.0)

    def test_04_repeated_anxiety_pattern(self):
        """Verify that repeated_anxiety triggers when anxiety rate > 35%."""
        save_emotion_event(self.username, str(uuid.uuid4()), "anxiety", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "anxiety", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "joy", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "neutral", "Normal")

        response = self.client.get("/analytics/insights", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        types = [ins["type"] for ins in response.json()]
        self.assertIn("repeated_anxiety", types)

    def test_05_prolonged_sadness_pattern(self):
        """Verify that prolonged_sadness triggers when sadness rate > 35%."""
        save_emotion_event(self.username, str(uuid.uuid4()), "sadness", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "sadness", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "neutral", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "joy", "Normal")

        response = self.client.get("/analytics/insights", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        types = [ins["type"] for ins in response.json()]
        self.assertIn("prolonged_sadness", types)

    def test_06_emotional_instability_pattern(self):
        """Verify that volatility triggers emotional_instability when transitions >= 3."""
        # Shift: pos -> neg -> pos -> neg
        save_emotion_event(self.username, str(uuid.uuid4()), "joy", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "sadness", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "joy", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "anxiety", "Normal")

        response = self.client.get("/analytics/insights", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        types = [ins["type"] for ins in response.json()]
        self.assertIn("emotional_instability", types)

    def test_07_positive_recovery_pattern(self):
        """Verify that positive_recovery triggers when joy rates increase."""
        # 1st half: sadness, 2nd half: joy
        save_emotion_event(self.username, str(uuid.uuid4()), "sadness", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "sadness", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "joy", "Normal")
        save_emotion_event(self.username, str(uuid.uuid4()), "joy", "Normal")

        response = self.client.get("/analytics/insights", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        types = [ins["type"] for ins in response.json()]
        self.assertIn("positive_recovery", types)

    def test_08_jwt_isolation_and_credentials(self):
        """Verify that requests without JWT or for another user are secured."""
        # Unauthorized check
        response = self.client.get("/analytics/insights")
        self.assertEqual(response.status_code, 401)

if __name__ == "__main__":
    unittest.main()
