import unittest
from decimal import Decimal
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from src.api.main import app
from src.core.config import settings
from src.services.auth import create_access_token, decode_access_token
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    UserProfile,
    PsychologistProfile
)

class TestPsychologistAuthAndRoleExposure(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        from src.core.redis_client import redis_client
        type(redis_client).client = property(lambda self: None)
        cls.original_rate_limit = settings.RATE_LIMIT_ENABLED
        settings.RATE_LIMIT_ENABLED = False

    @classmethod
    def tearDownClass(cls):
        settings.RATE_LIMIT_ENABLED = cls.original_rate_limit

    def setUp(self):
        db = SessionLocal()
        try:
            # Clear tables
            db.query(PsychologistProfile).delete()
            db.query(UserProfile).delete()
            db.query(User).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_normal_user_registration_defaults_to_user(self):
        client = TestClient(app)
        
        # Register a normal user without explicit role
        payload = {
            "username": "normal_test_user",
            "password": "password123",
            "email": "normal@example.com",
            "full_name": "Normal Test User"
        }
        res = client.post("/register", json=payload)
        self.assertEqual(res.status_code, 201)
        
        # Verify role in DB
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == "normal_test_user").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "user")
        finally:
            db.close()

    def test_login_returns_role_and_exposes_in_token_and_profile(self):
        client = TestClient(app)
        
        # Register user
        payload = {
            "username": "normal_login_user",
            "password": "password123",
            "email": "normal_login@example.com",
            "full_name": "Normal Login User",
            "role": "user"
        }
        client.post("/register", json=payload)
        
        # Login
        login_payload = {
            "email": "normal_login@example.com",
            "password": "password123"
        }
        res = client.post("/login", json=login_payload)
        self.assertEqual(res.status_code, 200)
        
        data = res.json()
        self.assertEqual(data["role"], "user")
        self.assertIn("access_token", data)
        
        # Verify role encoded in JWT payload
        token = data["access_token"]
        payload_decoded = decode_access_token(token)
        self.assertIsNotNone(payload_decoded)
        self.assertEqual(payload_decoded.get("role"), "user")
        
        # Verify profile endpoint returns role
        headers = {"Authorization": f"Bearer {token}"}
        profile_res = client.get("/profile", headers=headers)
        self.assertEqual(profile_res.status_code, 200)
        self.assertEqual(profile_res.json().get("role"), "user")

    def test_psychologist_registration_requires_fields(self):
        client = TestClient(app)
        
        # 1. Registration fails if fields are missing
        payload = {
            "username": "failed_psy",
            "password": "password123",
            "email": "failed_psy@example.com",
            "full_name": "Failed Psychologist",
            "role": "psychologist"
        }
        res = client.post("/register", json=payload)
        self.assertEqual(res.status_code, 400)
        
        # 2. Registration succeeds if professional fields are provided
        payload_success = {
            "username": "success_psy",
            "password": "password123",
            "email": "success_psy@example.com",
            "full_name": "Success Psychologist",
            "role": "psychologist",
            "title": "Uzm. Psk.",
            "specialty": "Depresyon",
            "bio": "Merhaba, ben uzman klinik psikoloğum."
        }
        res_success = client.post("/register", json=payload_success)
        self.assertEqual(res_success.status_code, 201)
        
        # Verify DB entry
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == "success_psy").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "psychologist")
            
            profile = db.query(PsychologistProfile).filter(PsychologistProfile.user_id == user.id).first()
            self.assertIsNotNone(profile)
            self.assertEqual(profile.status, "pending")
            self.assertEqual(profile.title, "Uzm. Psk.")
            self.assertEqual(profile.specialty, "Depresyon")
            self.assertEqual(profile.bio, "Merhaba, ben uzman klinik psikoloğum.")
        finally:
            db.close()

    def test_list_psychologists_returns_only_approved_and_admin_can_approve(self):
        client = TestClient(app)
        
        # 1. Register psychologist
        payload = {
            "username": "test_psy_list",
            "password": "password123",
            "email": "psy_list@example.com",
            "full_name": "List Psychologist",
            "role": "psychologist",
            "title": "Dr. Psk.",
            "specialty": "Bilişsel Terapi",
            "bio": "Bilişsel terapi uzmanı."
        }
        client.post("/register", json=payload)
        
        # 2. Verify list is empty initially (since status=pending)
        res_list = client.get("/psychologists")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.json()), 0)
        
        # 3. Approve psychologist using admin credentials (basic auth admin/psiko_secret123)
        # Auth base64 for admin:psiko_secret123
        import base64
        auth_str = base64.b64encode(b"admin:psiko_secret123").decode("utf-8")
        admin_headers = {"Authorization": f"Basic {auth_str}"}
        
        res_approve = client.post("/admin/psychologists/test_psy_list/approve", headers=admin_headers)
        self.assertEqual(res_approve.status_code, 200)
        self.assertEqual(res_approve.json().get("status"), "success")
        
        # 4. Verify list now contains the approved psychologist
        res_list_after = client.get("/psychologists")
        self.assertEqual(res_list_after.status_code, 200)
        self.assertEqual(len(res_list_after.json()), 1)
        psy_item = res_list_after.json()[0]
        self.assertEqual(psy_item["username"], "test_psy_list")
        self.assertEqual(psy_item["title"], "Dr. Psk.")
        self.assertEqual(psy_item["specialty"], "Bilişsel Terapi")
        self.assertEqual(psy_item["status"], "approved")

    def test_admin_psychologists_pending_reject_and_all_endpoints(self):
        client = TestClient(app)
        import base64
        auth_str = base64.b64encode(b"admin:psiko_secret123").decode("utf-8")
        admin_headers = {"Authorization": f"Basic {auth_str}"}

        # 1. Register a psychologist
        payload = {
            "username": "psy_pending_test",
            "password": "password123",
            "email": "pending_test@example.com",
            "full_name": "Pending Psychologist",
            "role": "psychologist",
            "title": "Dr. Psk.",
            "specialty": "Kaygı",
            "bio": "Kaygı uzmanıyım."
        }
        res_reg = client.post("/register", json=payload)
        self.assertEqual(res_reg.status_code, 201)

        # 2. Get pending psychologists list - verify psy is in list
        res_pending = client.get("/admin/psychologists/pending", headers=admin_headers)
        self.assertEqual(res_pending.status_code, 200)
        pending_list = res_pending.json()
        self.assertTrue(len(pending_list) >= 1)
        psy_item = next((p for p in pending_list if p["username"] == "psy_pending_test"), None)
        self.assertIsNotNone(psy_item)
        self.assertEqual(psy_item["status"], "pending")
        self.assertEqual(psy_item["full_name"], "Pending Psychologist")
        self.assertEqual(psy_item["email"], "pending_test@example.com")
        self.assertEqual(psy_item["specialty"], "Kaygı")
        self.assertIn("created_at", psy_item)

        # 3. Get all psychologists list - verify psy is in list
        res_all = client.get("/admin/psychologists/all", headers=admin_headers)
        self.assertEqual(res_all.status_code, 200)
        all_list = res_all.json()
        self.assertTrue(len(all_list) >= 1)
        psy_all_item = next((p for p in all_list if p["username"] == "psy_pending_test"), None)
        self.assertIsNotNone(psy_all_item)

        # 4. Reject psychologist
        res_reject = client.post("/admin/psychologists/psy_pending_test/reject", headers=admin_headers)
        self.assertEqual(res_reject.status_code, 200)
        self.assertEqual(res_reject.json().get("status"), "success")

        # 5. Verify no longer in pending list
        res_pending_after = client.get("/admin/psychologists/pending", headers=admin_headers)
        self.assertEqual(res_pending_after.status_code, 200)
        pending_list_after = res_pending_after.json()
        psy_item_after = next((p for p in pending_list_after if p["username"] == "psy_pending_test"), None)
        self.assertIsNone(psy_item_after)

        # 6. Verify status in all list is "rejected"
        res_all_after = client.get("/admin/psychologists/all", headers=admin_headers)
        self.assertEqual(res_all_after.status_code, 200)
        all_list_after = res_all_after.json()
        psy_all_item_after = next((p for p in all_list_after if p["username"] == "psy_pending_test"), None)
        self.assertIsNotNone(psy_all_item_after)
        self.assertEqual(psy_all_item_after["status"], "rejected")

    def test_unauthorized_access_blocked(self):
        client = TestClient(app)

        # Accessing admin endpoints without credentials should fail with 401
        res1 = client.get("/admin/psychologists/pending")
        self.assertEqual(res1.status_code, 401)

        res2 = client.get("/admin/psychologists/all")
        self.assertEqual(res2.status_code, 401)

        res3 = client.post("/admin/psychologists/psy_pending_test/approve")
        self.assertEqual(res3.status_code, 401)

        res4 = client.post("/admin/psychologists/psy_pending_test/reject")
        self.assertEqual(res4.status_code, 401)

