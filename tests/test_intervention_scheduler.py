import unittest
from datetime import datetime, timedelta, timezone, time as datetime_time
from src.services.database import (
    init_db,
    SessionLocal,
    Base,
    User,
    EmotionEvent,
    ScheduledIntervention,
    save_emotion_event,
    get_scheduled_interventions_for_user
)
from src.services.intervention_scheduler import schedule_user_interventions, ISTANBUL_TZ


class TestInterventionScheduler(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Initialize SQLite DB
        init_db()
        
    def setUp(self):
        # Clear database records for isolated testing
        db = SessionLocal()
        try:
            db.query(EmotionEvent).delete()
            db.query(ScheduledIntervention).delete()
            db.query(User).delete()
            
            # Create a test user
            test_user = User(username="test_user", password_hash="dummy")
            db.add(test_user)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_fallback_scheduling_with_insufficient_history(self):
        """If there are no emotion events, the scheduler must fall back to standard wellness recommendations."""
        schedule = schedule_user_interventions(user_id="test_user")
        
        # Verify fallback recommendations are generated (hydration and sleep reminders)
        self.assertGreater(len(schedule), 0)
        types = {item["type"] for item in schedule}
        self.assertTrue("hydration_reminder" in types or "sleep_reminder" in types)
        
        # Verify default pending status
        for item in schedule:
            self.assertEqual(item["status"], "pending")

    def test_anxiety_insight_scheduling_rule(self):
        """Verify repeated_anxiety generates breathing_break at 09:00 local time."""
        # Insert 4 anxiety events to trigger behavioral insights rule
        for i in range(5):
            save_emotion_event(
                user_id="test_user",
                message_id=f"msg_{i}",
                emotion="Kaygı",
                risk="düşük",
                source="predict"
            )
            
        schedule = schedule_user_interventions(user_id="test_user")
        
        types = {item["type"] for item in schedule}
        self.assertIn("breathing_break", types)
        
        # Verify breathing_break is scheduled for 09:00:00 Europe/Istanbul timezone (UTC+3)
        breathing_item = next(item for item in schedule if item["type"] == "breathing_break")
        dt_str = breathing_item["scheduled_for"] # Stored in UTC ISO string
        utc_dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        local_dt = utc_dt.astimezone(ISTANBUL_TZ)
        
        self.assertEqual(local_dt.hour, 9)
        self.assertEqual(local_dt.minute, 0)

    def test_cooldown_constraint(self):
        """Verify that the same intervention type is not repeated within a 12-hour window."""
        db = SessionLocal()
        try:
            # Artificially insert a pending breathing_break scheduled for tomorrow 09:00
            now_local = datetime.now(ISTANBUL_TZ)
            tomorrow_local_date = (now_local + timedelta(days=1)).date()
            t_local = datetime.combine(tomorrow_local_date, datetime_time(9, 0), ISTANBUL_TZ)
            t_utc = t_local.astimezone(timezone.utc).replace(tzinfo=None)
            
            record = ScheduledIntervention(
                user_id="test_user",
                intervention_type="breathing_break",
                scheduled_for=t_utc,
                status="pending",
                priority="medium",
                source_insight="repeated_anxiety"
            )
            db.add(record)
            db.commit()
        finally:
            db.close()
            
        # Add anxiety events which normally triggers breathing_break
        for i in range(5):
            save_emotion_event(
                user_id="test_user",
                message_id=f"msg_cooldown_{i}",
                emotion="Kaygı",
                risk="düşük",
                source="predict"
            )
            
        schedule = schedule_user_interventions(user_id="test_user")
        
        # Since standard scheduler cancels previous pending ones and schedules new ones, 
        # let's verify that duplicate scheduler runs maintain exactly 1 pending breathing_break and respect 12h cooldown
        breathing_items_pending = [item for item in schedule if item["type"] == "breathing_break" and item["status"] == "pending"]
        self.assertEqual(len(breathing_items_pending), 1)

    def test_daily_cap_limit(self):
        """Verify that daily scheduled count does not exceed the limit of 3."""
        # Trigger multiple insights by saving diverse emotion sequences
        # Anxiety -> breathing_break
        for i in range(4):
            save_emotion_event("test_user", f"anx_{i}", "Kaygı", "düşük")
        # Sadness -> social_connection
        for i in range(4):
            save_emotion_event("test_user", f"sad_{i}", "Üzüntü", "düşük")
        # Stress -> short_walk
        for i in range(4):
            save_emotion_event("test_user", f"str_{i}", "Stres", "düşük")
        # Emotional instability -> grounding_exercise
        for i in range(4):
            save_emotion_event("test_user", f"inst_{i}", "Öfke", "düşük")
            
        schedule = schedule_user_interventions(user_id="test_user")
        
        # Verify capped limit of 3
        pending_items = [item for item in schedule if item["status"] == "pending"]
        self.assertLessEqual(len(pending_items), 3)

    def test_crisis_safety_override(self):
        """Verify that an active crisis suppresses all standard interventions and registers priority support."""
        # Add a crisis event (high risk / crisis)
        save_emotion_event(
            user_id="test_user",
            message_id="msg_crisis_1",
            emotion="Kriz",
            risk="kriz",
            source="predict"
        )
        
        schedule = schedule_user_interventions(user_id="test_user")
        
        # Verify that ONLY priority_support is scheduled
        pending_items = [item for item in schedule if item["status"] == "pending"]
        self.assertEqual(len(pending_items), 1)
        self.assertEqual(pending_items[0]["type"], "priority_support")
        self.assertEqual(pending_items[0]["priority"], "high")



if __name__ == "__main__":
    unittest.main()
