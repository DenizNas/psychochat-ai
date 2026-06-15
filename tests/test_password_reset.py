import sys
import os
import unittest
import uuid
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["SECRET_KEY"] = "test_secret_key_for_unit_testing_only_32chars"
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["OPENAI_API_KEY"] = "sk-test-dummy"

from fastapi.testclient import TestClient
from src.api.main import app
from src.services.database import init_db, SessionLocal, User, PasswordResetCode
from src.services.auth import verify_password

client = TestClient(app, raise_server_exceptions=False)

class TestPasswordResetSystem(unittest.TestCase):
    def setUp(self):
        """Initialize database and create test user."""
        init_db()
        self.username = f"reset_user_{uuid.uuid4().hex[:8]}"
        self.email = f"{self.username}@example.com"
        self.password = "OriginalPass123!"
        
        # Register user
        resp = client.post("/register", json={
            "username": self.username,
            "email": self.email,
            "password": self.password,
            "full_name": "Reset Test User"
        })
        self.assertEqual(resp.status_code, 201)

    def test_request_code_success_and_cooldown(self):
        # Request code
        resp = client.post("/auth/password-reset/request", json={"email": self.email})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("message", resp.json())
        
        # Verify code was saved in DB
        db = SessionLocal()
        try:
            codes = db.query(PasswordResetCode).filter(PasswordResetCode.email == self.email).all()
            self.assertEqual(len(codes), 1)
            self.assertEqual(codes[0].used, False)
            self.assertEqual(len(codes[0].verification_code), 6)
        finally:
            db.close()

        # Cooldown check (requesting again within 60s should return 429)
        resp_cooldown = client.post("/auth/password-reset/request", json={"email": self.email})
        self.assertEqual(resp_cooldown.status_code, 429)
        self.assertIn("60 saniye", resp_cooldown.json()["message"])

    def test_request_code_non_existent_email_non_exposure(self):
        # Request for non-existent email must still return success (200) to prevent enumeration
        fake_email = "fake_nonexistent_email@example.com"
        resp = client.post("/auth/password-reset/request", json={"email": fake_email})
        self.assertEqual(resp.status_code, 200)
        
        # Verify no code was created in DB for fake email
        db = SessionLocal()
        try:
            code = db.query(PasswordResetCode).filter(PasswordResetCode.email == fake_email).first()
            self.assertIsNone(code)
        finally:
            db.close()

    def test_verify_code_incorrect_code_lockout(self):
        # Generate code
        client.post("/auth/password-reset/request", json={"email": self.email})
        
        # Verify incorrect code returns 400
        resp = client.post("/auth/password-reset/verify", json={
            "email": self.email,
            "code": "000000"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Geçersiz e-posta veya doğrulama kodu", resp.json()["message"])

        # Try multiple times to trigger lockout (3 fails total)
        client.post("/auth/password-reset/verify", json={"email": self.email, "code": "000000"})
        client.post("/auth/password-reset/verify", json={"email": self.email, "code": "000000"})
        
        # DB check: verify code is now marked used/invalid
        db = SessionLocal()
        try:
            code_rec = db.query(PasswordResetCode).filter(PasswordResetCode.email == self.email).first()
            self.assertTrue(code_rec.used)
            self.assertEqual(code_rec.failed_attempts, 3)
        finally:
            db.close()

    def test_complete_reset_flow(self):
        # 1. Request Code
        client.post("/auth/password-reset/request", json={"email": self.email})
        
        # Retrieve code from DB
        db = SessionLocal()
        try:
            code_rec = db.query(PasswordResetCode).filter(PasswordResetCode.email == self.email).first()
            code = code_rec.verification_code
        finally:
            db.close()
            
        # 2. Verify Code
        verify_resp = client.post("/auth/password-reset/verify", json={
            "email": self.email,
            "code": code
        })
        self.assertEqual(verify_resp.status_code, 200)
        reset_token = verify_resp.json()["reset_token"]
        self.assertIsNotNone(reset_token)
        
        # 3. Complete Reset
        new_pass = "NewAwesomePass77!"
        complete_resp = client.post("/auth/password-reset/complete", json={
            "reset_token": reset_token,
            "new_password": new_pass
        })
        self.assertEqual(complete_resp.status_code, 200)
        
        # 4. Verify password updated and code invalidated
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == self.email).first()
            self.assertTrue(verify_password(new_pass, user.password_hash))
            
            code_rec_after = db.query(PasswordResetCode).filter(PasswordResetCode.email == self.email).first()
            self.assertTrue(code_rec_after.used)
        finally:
            db.close()

        # 5. Reuse token must fail
        complete_reuse = client.post("/auth/password-reset/complete", json={
            "reset_token": reset_token,
            "new_password": "YetAnotherPass99!"
        })
        self.assertEqual(complete_reuse.status_code, 400)

    def test_complete_reset_invalidates_old_codes(self):
        # 1. Generate first code, wait cooldown (we'll manually manipulate DB timestamps or add another user to mock)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == self.email).first()
            
            # Manually insert an old code
            old_code = PasswordResetCode(
                user_id=user.id,
                email=self.email,
                verification_code="111111",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                used=False,
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5)
            )
            db.add(old_code)
            db.commit()
            
            # Manually insert a second code (the active one)
            active_code = PasswordResetCode(
                user_id=user.id,
                email=self.email,
                verification_code="222222",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                used=False,
                created_at=datetime.now(timezone.utc)
            )
            db.add(active_code)
            db.commit()
            
            active_code_id = active_code.id
            old_code_id = old_code.id
        finally:
            db.close()

        # Verify the active code to get token
        verify_resp = client.post("/auth/password-reset/verify", json={
            "email": self.email,
            "code": "222222"
        })
        self.assertEqual(verify_resp.status_code, 200)
        reset_token = verify_resp.json()["reset_token"]

        # Complete reset
        complete_resp = client.post("/auth/password-reset/complete", json={
            "reset_token": reset_token,
            "new_password": "NewSecurePass88!"
        })
        self.assertEqual(complete_resp.status_code, 200)

        # Verify BOTH codes are now marked used = True
        db = SessionLocal()
        try:
            c1 = db.query(PasswordResetCode).filter(PasswordResetCode.id == old_code_id).first()
            c2 = db.query(PasswordResetCode).filter(PasswordResetCode.id == active_code_id).first()
            self.assertTrue(c1.used)
            self.assertTrue(c2.used)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
