import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from src.services.database import (
    init_db,
    SessionLocal,
    UserMemory,
    UserProfile,
    User,
    get_active_memories_for_user
)
from src.response_engine.personal_context_engine import (
    PersonalContextEngine,
    consolidate_memories,
    process_turn,
    SENSITIVITY_LOW,
    SENSITIVITY_HIGH
)

class TestPersonalContextEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        db = SessionLocal()
        try:
            # Clear existing tables for consistent tests
            db.query(UserMemory).delete()
            db.query(UserProfile).delete()
            db.query(User).delete()
            
            # Setup a test user
            user = User(username="test_pce_user", password_hash="dummy")
            db.add(user)
            
            profile = UserProfile(
                username="test_pce_user",
                display_name="PCE User",
                privacy_mode=False
            )
            db.add(profile)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_memory_extraction_rules(self):
        """Verify that PCE extracts preference, routine, boundary, goal and coping strategy correctly."""
        pce = PersonalContextEngine()
        
        # Test routine & coping strategy extraction
        res = pce.extract(
            user_id="test_pce_user",
            text="Yürüyüş bana iyi geliyor.",
            emotion="calm",
            risk="Normal"
        )
        self.assertGreater(res["extracted_count"], 0)
        
        memories = get_active_memories_for_user("test_pce_user")
        self.assertTrue(any("yürüyüş" in m["memory_value"].lower() for m in memories))
        
        # Test routine extraction
        res_routine = pce.extract(
            user_id="test_pce_user",
            text="Her sabah spor yapıyorum.",
            emotion="calm",
            risk="Normal"
        )
        self.assertGreater(res_routine["extracted_count"], 0)
        
        # Test goal extraction
        res_goal = pce.extract(
            user_id="test_pce_user",
            text="Hedefim gelecekte mutlu olmak.",
            emotion="neutral",
            risk="Normal"
        )
        memories = get_active_memories_for_user("test_pce_user")
        self.assertTrue(any("hedef" in m["memory_value"].lower() or "istek" in m["memory_value"].lower() for m in memories))

    def test_privacy_and_sensitive_filters(self):
        """Verify that PII, credentials, health diagnosis, and crisis indicators get blocked/masked."""
        pce = PersonalContextEngine()
        
        # Phone numbers PII test
        pce.extract(
            user_id="test_pce_user",
            text="Telefon numaram 05551234567, yürüyüş bana iyi geliyor.",
            emotion="calm",
            risk="Normal"
        )
        memories = get_active_memories_for_user("test_pce_user")
        self.assertEqual(len(memories), 0, "PII phone run should block the entire memory")
        
        # API Keys PII test
        pce.extract(
            user_id="test_pce_user",
            text="Yürüyüş bana iyi geliyor. Gizli api key değerim: sk-proj1234.",
            emotion="calm",
            risk="Normal"
        )
        memories = get_active_memories_for_user("test_pce_user")
        self.assertEqual(len(memories), 0, "API key leak should block the memory")
        
        # Medical diagnosis test
        pce.extract(
            user_id="test_pce_user",
            text="Bana bipolar bozukluk tanısı kondu.",
            emotion="sadness",
            risk="Normal"
        )
        memories = get_active_memories_for_user("test_pce_user")
        self.assertEqual(len(memories), 0, "Clinical medical diagnosis should be completely rejected")

    def test_privacy_mode_active_blocks_everything(self):
        """Verify that when privacy_mode is active, no extraction, injection or retrieval occurs."""
        pce = PersonalContextEngine()
        
        # 1. Block Extraction
        res = pce.extract(
            user_id="test_pce_user",
            text="Her sabah yürüyüş yapmak bana iyi geliyor.",
            emotion="calm",
            risk="Normal",
            privacy_mode=True
        )
        self.assertEqual(res["extracted_count"], 0)
        self.assertEqual(res["skipped_reason"], "privacy_mode")
        
        # Seed memory manually for retrieval tests
        from src.services.database import create_memory
        create_memory("test_pce_user", "preference", "Kullanıcı kısa cevaplar tercih ediyor.", confidence=0.9)
        
        # 2. Block Retrieval
        selected, candidates, filtered = pce.retrieve(
            user_id="test_pce_user",
            emotion="neutral",
            risk="Normal",
            privacy_mode=True
        )
        self.assertEqual(len(selected), 0)
        
        # 3. Block Injection
        turn_res = pce.process_turn(
            user_id="test_pce_user",
            text="Merhaba",
            emotion="neutral",
            risk="Normal",
            privacy_mode=True
        )
        self.assertEqual(turn_res["injection_text"], "")
        self.assertFalse(turn_res["memory_injected"])

    def test_crisis_mode_blocks_extraction_and_injection(self):
        """Verify that PCE blocks memory write and injection during active crisis turns."""
        pce = PersonalContextEngine()
        
        # 1. Extraction blocked in crisis
        res = pce.extract(
            user_id="test_pce_user",
            text="Her sabah yürüyüş yapmak bana iyi geliyor.",
            emotion="sadness",
            risk="1" # crisis
        )
        self.assertEqual(res["extracted_count"], 0)
        self.assertEqual(res["skipped_reason"], "crisis_turn")
        
        # Seed memory manually
        from src.services.database import create_memory
        create_memory("test_pce_user", "preference", "Kullanıcı kısa cevaplar tercih ediyor.", confidence=0.9)
        
        # 2. Injection blocked in crisis
        selected, candidates, filtered = pce.retrieve(
            user_id="test_pce_user",
            emotion="sadness",
            risk="kriz" # crisis
        )
        self.assertEqual(len(selected), 0)

    def test_memory_scoring_and_retrieval(self):
        """Verify multi-factor hybrid scoring prioritises high relevance, confidence and recency."""
        pce = PersonalContextEngine()
        
        from src.services.database import SessionLocal, UserMemory
        db = SessionLocal()
        try:
            # Seed multiple memories with distinct priority
            m1 = UserMemory(
                user_id="test_pce_user",
                memory_key="preference",
                memory_value="Kullanıcı kısa ve net yanıtlar istiyor.",
                confidence=0.9,
                sensitivity=SENSITIVITY_LOW,
                is_active=True
            )
            m2 = UserMemory(
                user_id="test_pce_user",
                memory_key="coping_strategy",
                memory_value="Nefes egzersizleri sakinleşmesine yardımcı oluyor.",
                confidence=0.8,
                sensitivity=SENSITIVITY_LOW,
                is_active=True
            )
            # High sensitivity memory -> should never retrieve
            m3 = UserMemory(
                user_id="test_pce_user",
                memory_key="routine",
                memory_value="Kullanıcı gizli sırlar paylaştı.",
                confidence=0.95,
                sensitivity=SENSITIVITY_HIGH,
                is_active=True
            )
            db.add_all([m1, m2, m3])
            db.commit()
        finally:
            db.close()
            
        selected, candidates, filtered = pce.retrieve(
            user_id="test_pce_user",
            emotion="anxiety",
            risk="Normal",
            text="Çok kaygılıyım nefes almakta zorlanıyorum."
        )
        
        # High sensitivity should be filtered out
        self.assertTrue(all(m["sensitivity"] != SENSITIVITY_HIGH for m in selected))
        
        # Coping strategy matching 'nefes' should rank high due to keyword relevance boost
        self.assertTrue(len(selected) > 0)
        self.assertEqual(selected[0]["memory_key"], "coping_strategy")

    def test_memory_consolidation_decay_and_de_duplication(self):
        """Verify decay score updates, soft deletes low confidence, merges duplicates, and handles contradictions."""
        pce = PersonalContextEngine()
        
        from src.services.database import SessionLocal, UserMemory
        db = SessionLocal()
        try:
            # Duplicate memories
            m1 = UserMemory(
                user_id="test_pce_user",
                memory_key="preference",
                memory_value="Kullanıcı kısa yanıtları tercih ediyor.",
                confidence=0.8,
                created_at=datetime.now(timezone.utc) - timedelta(days=5),
                is_active=True
            )
            m2 = UserMemory(
                user_id="test_pce_user",
                memory_key="preference",
                memory_value="Kullanıcı kısa yanıtları tercih ediyor.",
                confidence=0.7,
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
                is_active=True
            )
            # Low confidence memory to trigger decay clean-up
            m3 = UserMemory(
                user_id="test_pce_user",
                memory_key="routine",
                memory_value="Kullanıcı her gün yürüyüş yapıyor.",
                confidence=0.1,  # below threshold
                is_active=True
            )
            # Contradictory memories
            m4 = UserMemory(
                user_id="test_pce_user",
                memory_key="preference",
                memory_value="Kullanıcı kısa yanıt istiyor.",
                confidence=0.8,
                is_active=True
            )
            m5 = UserMemory(
                user_id="test_pce_user",
                memory_key="preference",
                memory_value="Kullanıcı uzun yanıt istiyor.",
                confidence=0.8,
                is_active=True
            )
            
            db.add_all([m1, m2, m3, m4, m5])
            db.commit()
        finally:
            db.close()
            
        stats = pce.consolidate_memories("test_pce_user")
        self.assertEqual(stats["status"], "success")
        self.assertGreaterEqual(stats["decayed"], 1) # m3 should be soft-deleted
        self.assertGreaterEqual(stats["merged"], 1)  # m1 and m2 duplicates merged
        self.assertGreaterEqual(stats["contradicted"], 1) # m4 and m5 contradictions penalized

if __name__ == "__main__":
    unittest.main()
