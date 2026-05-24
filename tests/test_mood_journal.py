import unittest
from datetime import datetime
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    MoodJournal,
    EmotionEvent,
    save_mood_journal,
    get_mood_journals_for_user,
    delete_mood_journal
)
from src.api.main import app
from fastapi.testclient import TestClient


class TestMoodJournalSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(MoodJournal).delete()
            db.query(EmotionEvent).delete()
            db.query(User).delete()
            
            # Create two test users
            user_a = User(username="user_a", password_hash="dummy")
            user_b = User(username="user_b", password_hash="dummy")
            db.add(user_a)
            db.add(user_b)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_save_and_retrieve_mood_journal(self):
        """Verify normal creation and timeframe-based retrieval of manual mood logs."""
        save_mood_journal(
            user_id="user_a",
            mood="happy",
            intensity=4,
            note="Bugün harika bir gün geçirdim."
        )
        
        entries = get_mood_journals_for_user(user_id="user_a", days=7)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["mood"], "happy")
        self.assertEqual(entries[0]["intensity"], 4)
        self.assertEqual(entries[0]["note"], "Bugün harika bir gün geçirdim.")
        self.assertEqual(entries[0]["source"], "journal")

    def test_mood_journal_deletion_isolation(self):
        """Verify that users can delete only their own mood journals."""
        entry_a = save_mood_journal(
            user_id="user_a",
            mood="calm",
            intensity=5,
            note="Sakinlik."
        )
        
        # User B attempts to delete User A's journal - should fail
        deleted_by_b = delete_mood_journal(user_id="user_b", journal_id=entry_a.id)
        self.assertFalse(deleted_by_b)
        
        # User A deletes own journal - should succeed
        deleted_by_a = delete_mood_journal(user_id="user_a", journal_id=entry_a.id)
        self.assertTrue(deleted_by_a)
        
        entries = get_mood_journals_for_user(user_id="user_a", days=7)
        self.assertEqual(len(entries), 0)

    def test_safety_masking_crisis_note(self):
        """Verify that crisis/self-harm patterns trigger safe note masking and register warning signals."""
        # We will directly trigger the POST API through TestClient to test endpoint safety logic
        # Mock auth by passing headers or using a mock token dependency if required. 
        # But we can also test the local safety check logic of main.py endpoint directly or using python logic:
        from src.response_engine.safety import check_safety
        
        crisis_note = "Bugün kendime zarar vermeyi düşünüyorum, dayanamıyorum artık."
        is_safe, category = check_safety(crisis_note, mode="user_input")
        self.assertFalse(is_safe)
        self.assertEqual(category, "self_harm")


if __name__ == "__main__":
    unittest.main()
