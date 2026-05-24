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
    SessionLocal, init_db, User, UserProfile, EmotionEvent, Analytics,
    get_user_emotion_timeline, get_user_emotion_summary, save_emotion_event
)
from src.services.auth import get_password_hash, create_access_token

class TestEmotionTimelineAnalytics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize DB (creates tables automatically if missing)
        init_db()
        cls.client_ctx = TestClient(app)
        cls.client = cls.client_ctx.__enter__()
        
        # Unique test username to avoid collision
        cls.username = f"test_analytics_user_{uuid.uuid4().hex[:6]}"
        cls.password = "Secr3tPa$$w0rd"
        
        # 1. Create and save test user
        db = SessionLocal()
        try:
            # Hash password and insert user
            hashed = get_password_hash(cls.password)
            user = User(username=cls.username, password_hash=hashed)
            db.add(user)
            db.commit()
            
            # Ensure Profile exists and privacy mode is False initially
            profile = db.query(UserProfile).filter(UserProfile.username == cls.username).first()
            if not profile:
                profile = UserProfile(
                    username=cls.username,
                    display_name="Test Analytics User",
                    privacy_mode=False
                )
                db.add(profile)
                db.commit()
        finally:
            db.close()

        # Generate JWT bearer token
        cls.token = create_access_token(data={"sub": cls.username})
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        cls.client_ctx.__exit__(None, None, None)

    def test_01_save_emotion_event_direct(self):
        """Verify that direct save of emotion events works and respects no-raw-text constraints."""
        msg_id = str(uuid.uuid4())
        success = save_emotion_event(
            user_id=self.username,
            message_id=msg_id,
            emotion="joy",
            risk="Normal",
            source="predict"
        )
        self.assertTrue(success)

        # Retrieve and assert
        timeline = get_user_emotion_timeline(self.username, days=1)
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["message_id"], msg_id)
        self.assertEqual(timeline[0]["emotion"], "joy")
        self.assertEqual(timeline[0]["risk"], "Normal")

    def test_02_predict_and_analytics_generation(self):
        """Verify that a /predict endpoint call logs emotion events successfully."""
        # 1. Hit /predict
        response = self.client.post(
            "/predict",
            json={"text": "Bugün kendimi harika ve mutlu hissediyorum!", "language": "tr"},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should have emotion and risk returned
        self.assertIn("emotion", data)
        self.assertIn("risk", data)
        self.assertIn("response", data)

        # 2. Check that the event was registered in the timeline
        timeline = get_user_emotion_timeline(self.username, days=1)
        # We had 1 from test_01, plus this new /predict call => total 2
        self.assertEqual(len(timeline), 2)
        
        # Verify summary endpoint via python service
        summary = get_user_emotion_summary(self.username, days=1)
        self.assertEqual(summary["total_messages"], 2)
        self.assertIn(data["emotion"], summary["emotion_distribution"])
        self.assertEqual(summary["crisis_count"], 0)

    def test_03_privacy_mode_scrubbing(self):
        """Verify that privacy mode masks raw text in general analytics logs."""
        # Activate privacy mode
        db = SessionLocal()
        try:
            profile = db.query(UserProfile).filter(UserProfile.username == self.username).first()
            self.assertIsNotNone(profile)
            profile.privacy_mode = True
            db.commit()
        finally:
            db.close()

        # Call /predict while privacy mode is active
        test_text = "Bu çok gizli bir test mesajıdır."
        response = self.client.post(
            "/predict",
            json={"text": test_text, "language": "tr"},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)

        # Query database directly to verify raw text was masked in Analytics table
        db = SessionLocal()
        try:
            records = db.query(Analytics).filter(Analytics.user_id == self.username).all()
            # Find the latest record
            latest_record = sorted(records, key=lambda r: r.timestamp, reverse=True)[0]
            self.assertEqual(latest_record.user_text, "<masked_by_privacy_mode>")
        finally:
            db.close()

    def test_04_crisis_masking(self):
        """Verify that crisis messages are strictly masked in general analytics log, even if privacy mode is deactivated."""
        # Deactivate privacy mode
        db = SessionLocal()
        try:
            profile = db.query(UserProfile).filter(UserProfile.username == self.username).first()
            profile.privacy_mode = False
            db.commit()
        finally:
            db.close()

        # Send a suicidal/crisis trigger message (which sets risk to crisis / kriz)
        # Note: Local predictor or immediate danger fallback rule will capture this.
        crisis_text = "Kendime zarar vermeyi düşünüyorum, artık dayanamıyorum."
        response = self.client.post(
            "/predict",
            json={"text": crisis_text, "language": "tr"},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check direct DB general analytics logs for crisis scrubbing
        db = SessionLocal()
        try:
            records = db.query(Analytics).filter(Analytics.user_id == self.username).all()
            latest_record = sorted(records, key=lambda r: r.timestamp, reverse=True)[0]
            
            # The general analytics MUST mask the raw text due to crisis rule
            self.assertEqual(latest_record.user_text, "<masked_due_to_crisis>")
        finally:
            db.close()

    def test_05_rest_endpoints(self):
        """Verify that the GET REST endpoints return correctly structured JWT-authorized responses."""
        # 1. Timeline Endpoint
        response = self.client.get("/analytics/emotions/timeline?days=7", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        timeline_data = response.json()
        self.assertTrue(isinstance(timeline_data, list))
        
        # Verify fields in each timeline item
        for item in timeline_data:
            self.assertIn("id", item)
            self.assertIn("message_id", item)
            self.assertIn("emotion", item)
            self.assertIn("risk", item)
            self.assertIn("created_at", item)
            self.assertIn("source", item)

        # 2. Summary Endpoint
        response = self.client.get("/analytics/emotions/summary?days=7", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        summary_data = response.json()
        self.assertIn("total_messages", summary_data)
        self.assertIn("emotion_distribution", summary_data)
        self.assertIn("dominant_emotion", summary_data)
        self.assertIn("crisis_count", summary_data)
        self.assertIn("daily_trend", summary_data)
        
        # Check daily trend structure
        for trend in summary_data["daily_trend"]:
            self.assertIn("date", trend)
            self.assertIn("emotions", trend)
            self.assertIn("total_count", trend)

    def test_06_unauthorized_isolation(self):
        """Verify that requests without JWT credentials get rejected."""
        response = self.client.get("/analytics/emotions/timeline")
        self.assertEqual(response.status_code, 401)
        
        response = self.client.get("/analytics/emotions/summary")
        self.assertEqual(response.status_code, 401)

if __name__ == "__main__":
    unittest.main()
