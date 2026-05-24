import unittest
from datetime import datetime, timedelta, timezone
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    UserProfile,
    NotificationEvent,
    save_notification_event,
    get_notification_events_for_user
)
from src.services.notification_service import refresh_user_notifications


class TestNotificationSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(NotificationEvent).delete()
            db.query(UserProfile).delete()
            db.query(User).delete()
            
            # Setup a test user with profile
            user = User(username="test_user", password_hash="dummy")
            db.add(user)
            db.commit()
            
            profile = UserProfile(
                username="test_user",
                display_name="Test User",
                notifications_enabled=True,
                privacy_mode=False
            )
            db.add(profile)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_preferences_block_notifications(self):
        """Verify that when notifications_enabled is set to False, all pending entries are cancelled and no new ones are planned."""
        db = SessionLocal()
        try:
            profile = db.query(UserProfile).filter(UserProfile.username == "test_user").first()
            profile.notifications_enabled = False
            db.commit()
        finally:
            db.close()

        # Add a dummy pending notification event
        save_notification_event(
            user_id="test_user",
            notification_type="mood_journal_reminder",
            title="Remind",
            body="Text",
            scheduled_for=datetime.utcnow() + timedelta(hours=2)
        )

        refresh_user_notifications("test_user")

        events = get_notification_events_for_user("test_user")
        # The previous pending should be marked cancelled, and no new ones generated
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["status"], "cancelled")

    def test_daily_capping_limit(self):
        """Verify that notification scheduling is strictly capped at a maximum of 3 items per day."""
        db = SessionLocal()
        try:
            # Re-enable notifications
            profile = db.query(UserProfile).filter(UserProfile.username == "test_user").first()
            profile.notifications_enabled = True
            db.commit()
        finally:
            db.close()

        # Call refresh
        refresh_user_notifications("test_user")

        events = get_notification_events_for_user("test_user")
        # Should contain at least the tomorrow's mood_journal_reminder, but no more than 3
        self.assertLessEqual(len([e for e in events if e["status"] == "pending"]), 3)


if __name__ == "__main__":
    unittest.main()
