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
