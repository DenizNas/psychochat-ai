import sys
import os
import json
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from src.core.config import settings
from src.services.database import (
    init_db, SessionLocal, User, UserProfile, UserMemory,
    MoodJournal, Analytics, EmotionEvent, SecurityAuditLog, UserConsent,
    RecommendationEvent
)
from src.services.compliance_service import compliance_service
from src.workers.tasks import cleanup_expired_audit_logs_task
from fastapi.testclient import TestClient
from src.api.main import app

class TestComplianceSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(RecommendationEvent).delete()
            db.query(SecurityAuditLog).delete()
            db.query(UserConsent).delete()
            db.query(UserMemory).delete()
            db.query(MoodJournal).delete()
            db.query(Analytics).delete()
            db.query(EmotionEvent).delete()
            db.query(UserProfile).delete()
            db.query(User).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_salted_cryptographic_hashing(self):
        """Verify that IP and User-Agent are cryptographically hashed using SHA-256 and salt."""
        ip = "192.168.1.100"
        ua = "Mozilla/5.0 Android Client"

        hashed_ip = compliance_service.hash_sensitive_value(ip)
        hashed_ua = compliance_service.hash_sensitive_value(ua)

        # Verification: hashes should be valid 64-character SHA-256 hex strings
        self.assertEqual(len(hashed_ip), 64)
        self.assertEqual(len(hashed_ua), 64)

        # Verification: raw PII strings must NOT be contained within the hashes
        self.assertNotIn(ip, hashed_ip)
        self.assertNotIn(ua, hashed_ua)

        # Verification: hashing must be deterministic
        self.assertEqual(hashed_ip, compliance_service.hash_sensitive_value(ip))

    def test_compliance_logging_integrity(self):
        """Verify that compliance logs are cleanly saved, metadata is sanitized, and metrics incremented."""
        db = SessionLocal()
        try:
            metadata = {
                "login_password": "raw_sensitive_password_123",
                "access_token": "bearer_jwt_auth_token_sig",
                "normal_field": "public_metadata_field"
            }

            compliance_service.log_security_event(
                db=db,
                user_id="test_compliance_user",
                event_type="profile_update",
                ip_address="127.0.0.1",
                user_agent="Mozilla/5.0",
                severity="INFO",
                metadata=metadata
            )

            # Query and verify
            log = db.query(SecurityAuditLog).filter(SecurityAuditLog.user_id == "test_compliance_user").first()
            self.assertIsNotNone(log)
            self.assertEqual(log.event_type, "profile_update")
            self.assertEqual(log.severity, "INFO")

            # Check that IP/UA are stored as hashes
            self.assertEqual(len(log.ip_address_hash), 64)
            self.assertEqual(len(log.user_agent_hash), 64)

            # Metadata sanitization validation: secrets must be redacted!
            meta_json = json.loads(log.metadata_json)
            self.assertEqual(meta_json["normal_field"], "public_metadata_field")
            self.assertEqual(meta_json["login_password"], "<redacted>")
            self.assertEqual(meta_json["access_token"], "<redacted>")
        finally:
            db.close()

    def test_gdpr_data_export_sanitization(self):
        """Verify that the GDPR export contains all relevant tables but completely excludes secrets."""
        db = SessionLocal()
        try:
            username = "export_user"
            
            # Setup DB records
            user = User(username=username, password_hash="highly_secure_bcrypt_hash")
            db.add(user)
            profile = UserProfile(username=username, display_name="Export User", bio="Testing GDPR Export.")
            db.add(profile)
            memory = UserMemory(user_id=username, memory_key="hobby", memory_value="yüzme", source_message="Bugün yüzmeye gittim.")
            db.add(memory)
            mood = MoodJournal(user_id=username, mood="happy", intensity=5, note="Harika bir gün.")
            db.add(mood)
            consent = UserConsent(user_id=username, analytics_consent=True, ai_processing_consent=True)
            db.add(consent)
            
            # Setup Recommendation record
            from src.services.database import RecommendationEvent
            rec = RecommendationEvent(
                id="rec_export_test_001",
                user_id=username,
                recommendation_type="breathing_break",
                title="Kısa bir nefes molası",
                description="Derin bir nefes alın.",
                priority="medium",
                confidence=0.8,
                reason="Kaygı örüntüleri öne çıktı.",
                status="active",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=48)
            )
            db.add(rec)
            db.commit()

            # Execute export
            payload = compliance_service.export_user_data(db, username)

            # Assertions
            self.assertIn("personal_profile", payload)
            self.assertIn("persistent_memories", payload)
            self.assertIn("manual_mood_journals", payload)
            self.assertIn("data_processing_consents", payload)
            self.assertIn("wellness_recommendations", payload)
            self.assertEqual(len(payload["wellness_recommendations"]), 1)
            self.assertEqual(payload["wellness_recommendations"][0]["id"], "rec_export_test_001")

            # Verify no sensitive password/token keys or raw system contexts are contained
            export_str = json.dumps(payload)
            self.assertNotIn("highly_secure_bcrypt_hash", export_str)
            self.assertNotIn("source_message", export_str)
            self.assertNotIn("Bugün yüzmeye gittim.", export_str)
        finally:
            db.close()

    def test_gdpr_irreversible_anonymization(self):
        """Verify that delete request purges auth credentials, soft-deletes memories, and masks logs irreversibly."""
        db = SessionLocal()
        try:
            username = "delete_user"
            
            # Setup DB records
            user = User(username=username, password_hash="dummy_hash")
            db.add(user)
            profile = UserProfile(username=username, display_name="Delete User", bio="PII info.", privacy_mode=False)
            db.add(profile)
            memory = UserMemory(user_id=username, memory_key="stress", memory_value="exams", is_active=True)
            db.add(memory)
            mood = MoodJournal(user_id=username, mood="anxious", intensity=4, note="Sınav stresi.")
            db.add(mood)
            analytics = Analytics(user_id=username, user_text="Sinavlar yaklasiyor.", emotion="anxious", risk="Normal")
            db.add(analytics)

            # Setup Recommendation record
            from src.services.database import RecommendationEvent
            rec = RecommendationEvent(
                id="rec_delete_test_001",
                user_id=username,
                recommendation_type="breathing_break",
                title="Kısa bir nefes molası",
                description="Derin bir nefes alın.",
                priority="medium",
                confidence=0.8,
                reason="Kaygı örüntüleri öne çıktı.",
                status="active",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=48)
            )
            db.add(rec)
            db.commit()

            # Execute Deletion
            success = compliance_service.delete_user_data(db, username)
            self.assertTrue(success)

            # Verify: User credential record deleted (logins permanently blocked)
            db_user = db.query(User).filter(User.username == username).first()
            self.assertIsNone(db_user)

            # Verify: Profile personal identifiers blanked out
            db_profile = db.query(UserProfile).filter(UserProfile.username == username).first()
            self.assertIsNotNone(db_profile)
            self.assertEqual(db_profile.display_name, "Anonymized User")
            self.assertEqual(db_profile.bio, "")
            self.assertTrue(db_profile.privacy_mode)

            # Verify: Memories are soft-deleted
            db_mem = db.query(UserMemory).filter(UserMemory.user_id == username).first()
            self.assertIsNotNone(db_mem)
            self.assertFalse(db_mem.is_active)

            # Verify: Mood notes masked
            db_mood = db.query(MoodJournal).filter(MoodJournal.user_id == username).first()
            self.assertEqual(db_mood.note, "<masked_by_user_deletion>")

            # Verify: Analytics anonymized (user_id re-mapped)
            db_anal = db.query(Analytics).filter(Analytics.user_id == "<anonymized>").first()
            self.assertIsNotNone(db_anal)
            self.assertEqual(db_anal.emotion, "anxious")  # keeps statistics

            # Verify: Recommendations are completely deleted
            db_rec = db.query(RecommendationEvent).filter(RecommendationEvent.user_id == username).first()
            self.assertIsNone(db_rec)
        finally:
            db.close()

    def test_compliance_api_endpoints(self):
        """Verify endpoints: /privacy/consent GET & POST, /privacy/export, and /privacy/delete."""
        # 1. Register & Login a fresh test user
        username = "api_privacy_user"
        password = "secure_password_123"
        self.client.post("/register", json={"username": username, "password": password})
        login_res = self.client.post("/login", json={"username": username, "password": password})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Test GET /privacy/consent (should return default all-false)
        get_consent = self.client.get("/privacy/consent", headers=headers)
        self.assertEqual(get_consent.status_code, 200)
        self.assertFalse(get_consent.json()["analytics_consent"])
        self.assertFalse(get_consent.json()["ai_processing_consent"])

        # 3. Test POST /privacy/consent (update consent and audit log it)
        update_body = {
            "analytics_consent": True,
            "wellness_insights_consent": True,
            "notifications_consent": False,
            "ai_processing_consent": True
        }
        post_consent = self.client.post("/privacy/consent", headers=headers, json=update_body)
        self.assertEqual(post_consent.status_code, 200)
        self.assertTrue(post_consent.json()["analytics_consent"])
        self.assertTrue(post_consent.json()["ai_processing_consent"])

        # Verify audit log was recorded for consent update
        db = SessionLocal()
        try:
            audit = db.query(SecurityAuditLog).filter(
                SecurityAuditLog.user_id == username,
                SecurityAuditLog.event_type == "consent_updated"
            ).first()
            self.assertIsNotNone(audit)
        finally:
            db.close()

        # 4. Test GET /privacy/export
        export_res = self.client.get("/privacy/export", headers=headers)
        self.assertEqual(export_res.status_code, 200)
        self.assertEqual(export_res.json()["personal_profile"]["username"], username)
        self.assertTrue(export_res.json()["data_processing_consents"]["analytics_consent"])

        # 5. Test DELETE /privacy/delete (without body - should fail)
        delete_fail = self.client.delete("/privacy/delete", headers=headers)
        self.assertEqual(delete_fail.status_code, 422)  # pydantic validation error

        # 6. Test DELETE /privacy/delete (incorrect confirmation - should fail)
        delete_fail2 = self.client.request("DELETE", "/privacy/delete", headers=headers, json={"confirm": "WRONG"})
        self.assertEqual(delete_fail2.status_code, 400)

        # 7. Test DELETE /privacy/delete (correct confirmation - should succeed)
        delete_success = self.client.request("DELETE", "/privacy/delete", headers=headers, json={"confirm": "DELETE_MY_DATA"})
        self.assertEqual(delete_success.status_code, 200)
        self.assertEqual(delete_success.json()["status"], "ok")

        # Verify subsequent login fails since credentials are deleted
        login_fail = self.client.post("/login", json={"username": username, "password": password})
        self.assertEqual(login_fail.status_code, 400)

    def test_celery_retention_cleanup(self):
        """Verify that the daily Celery task cleans up older logs successfully."""
        db = SessionLocal()
        try:
            # Create three logs: one fresh, two expired (older than 180 days)
            fresh_log = SecurityAuditLog(
                user_id="user_fresh",
                event_type="login_success",
                ip_address_hash="h1",
                user_agent_hash="h2",
                severity="INFO",
                created_at=datetime.now(timezone.utc)
            )
            expired_log1 = SecurityAuditLog(
                user_id="user_expired1",
                event_type="login_success",
                ip_address_hash="h1",
                user_agent_hash="h2",
                severity="INFO",
                created_at=datetime.now(timezone.utc) - timedelta(days=185)
            )
            expired_log2 = SecurityAuditLog(
                user_id="user_expired2",
                event_type="login_success",
                ip_address_hash="h1",
                user_agent_hash="h2",
                severity="INFO",
                created_at=datetime.now(timezone.utc) - timedelta(days=200)
            )
            db.add(fresh_log)
            db.add(expired_log1)
            db.add(expired_log2)
            db.commit()

            # Execute cleanup celery task
            cleanup_expired_audit_logs_task()

            # Verify that only the fresh log remains in DB
            remaining_logs = db.query(SecurityAuditLog).all()
            self.assertEqual(len(remaining_logs), 1)
            self.assertEqual(remaining_logs[0].user_id, "user_fresh")
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
