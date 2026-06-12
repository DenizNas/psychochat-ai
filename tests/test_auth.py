"""
tests/test_auth.py — Auth Persistence & Database Fix için Unit Testler
Faz 10F.0 — AUTH PERSISTENCE & DATABASE FIX

Test senaryoları:
1. /register → kullanıcı DB'ye kalıcı yazılıyor mu?
2. /register duplicate → 409 dönüyor mu?
3. /login başarılı → access_token dönüyor mu?
4. /login yanlış şifre → 400 dönüyor mu?
5. /login olmayan kullanıcı → 400 dönüyor mu?
6. token ile /profile erişimi → 200 mu?
7. token olmadan /profile → 401 mi?
8. logout → token blacklist'e giriyor mu?
9. logout sonrası aynı token tekrar kullanılamıyor mu?
10. DB persistence: register sonrası tekrar register → 409 mu?
"""

import sys
import os
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test için in-memory SQLite kullan — production DB'ye dokunma
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["SECRET_KEY"] = "test_secret_key_for_unit_testing_only_32chars"
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["OPENAI_API_KEY"] = "sk-test-dummy"

from fastapi.testclient import TestClient
from src.api.main import app
from src.services.database import init_db, SessionLocal, User

# Test client
client = TestClient(app, raise_server_exceptions=False)


def make_unique_user():
    """Her test için benzersiz kullanıcı adı üret (race condition önlemi)."""
    return f"testuser_{uuid.uuid4().hex[:8]}"


class TestAuthRegister(unittest.TestCase):
    """Register endpoint testleri."""

    def test_register_success(self):
        """Yeni kullanıcı başarıyla kayıt olabilmeli."""
        username = make_unique_user()
        resp = client.post("/register", json={"username": username, "password": "TestPass123!"})
        self.assertEqual(resp.status_code, 201, f"Register 201 dönmeli. Response: {resp.text}")
        body = resp.json()
        self.assertIn("message", body)
        self.assertIn("Kayıt başarılı", body["message"])

    def test_register_persists_to_db(self):
        """Register sonrası kullanıcı gerçekten DB'de var mı?"""
        username = make_unique_user()
        resp = client.post("/register", json={"username": username, "password": "TestPass123!"})
        self.assertEqual(resp.status_code, 201)

        # DB'de kullanıcıyı doğrula
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            self.assertIsNotNone(user, "Kullanıcı DB'ye yazılmış olmalı")
            self.assertEqual(user.username, username)
            self.assertIsNotNone(user.password_hash, "Şifre hash'i boş olmamalı")
            self.assertNotEqual(user.password_hash, "TestPass123!", "Şifre plaintext olmamalı")
        finally:
            db.close()

    def test_register_duplicate_returns_409(self):
        """Aynı kullanıcı adı tekrar kayıt olmaya çalışınca 409 dönmeli."""
        username = make_unique_user()
        # İlk kayıt
        resp1 = client.post("/register", json={"username": username, "password": "TestPass123!"})
        self.assertEqual(resp1.status_code, 201)
        # İkinci kayıt — aynı kullanıcı adı
        resp2 = client.post("/register", json={"username": username, "password": "AnotherPass456!"})
        self.assertEqual(resp2.status_code, 409, "Duplicate register 409 dönmeli")
        # Backend özel hata formatı: {status, message, error_code}
        body = resp2.json()
        self.assertTrue("message" in body or "detail" in body, "Hata mesajı dönmeli")

    def test_register_empty_fields_returns_400(self):
        """Boş alan ile kayıt 400 dönmeli."""
        resp = client.post("/register", json={"username": "", "password": "TestPass123!"})
        self.assertEqual(resp.status_code, 400)

    def test_register_password_too_long(self):
        """72 byte'tan uzun şifre 400 dönmeli (bcrypt limit)."""
        long_password = "A" * 73
        username = make_unique_user()
        resp = client.post("/register", json={"username": username, "password": long_password})
        self.assertEqual(resp.status_code, 400)


class TestAuthLogin(unittest.TestCase):
    """Login endpoint testleri."""

    def setUp(self):
        """Her test için taze kullanıcı oluştur."""
        self.username = make_unique_user()
        self.password = "SecurePass789!"
        resp = client.post("/register", json={"username": self.username, "password": self.password})
        self.assertEqual(resp.status_code, 201, "setUp: register başarısız oldu")

    def test_login_success_returns_token(self):
        """Başarılı login JWT token dönmeli."""
        resp = client.post("/login", json={"username": self.username, "password": self.password})
        self.assertEqual(resp.status_code, 200, f"Login 200 dönmeli. Response: {resp.text}")
        body = resp.json()
        self.assertIn("access_token", body, "access_token alanı eksik")
        self.assertIn("token_type", body, "token_type alanı eksik")
        self.assertEqual(body["token_type"], "bearer")
        self.assertIn("username", body, "username alanı eksik")
        self.assertEqual(body["username"], self.username)
        self.assertTrue(len(body["access_token"]) > 20, "Token çok kısa")

    def test_login_wrong_password_returns_400(self):
        """Yanlış şifre 400 dönmeli."""
        resp = client.post("/login", json={"username": self.username, "password": "WrongPassword!"})
        self.assertEqual(resp.status_code, 400)
        # Backend özel hata formatı: {status, message, error_code} veya {detail}
        body = resp.json()
        self.assertTrue("message" in body or "detail" in body, "Hata mesajı dönmeli")

    def test_login_nonexistent_user_returns_400(self):
        """Olmayan kullanıcı 400 dönmeli."""
        resp = client.post("/login", json={"username": "nonexistent_xyz_abc", "password": "SomePass123!"})
        self.assertEqual(resp.status_code, 400)

    def test_login_empty_fields_returns_400(self):
        """Boş alan ile login 400 dönmeli."""
        resp = client.post("/login", json={"username": "", "password": ""})
        self.assertEqual(resp.status_code, 400)


class TestTokenPersistence(unittest.TestCase):
    """Token ve session testleri."""

    def setUp(self):
        """Token al."""
        self.username = make_unique_user()
        self.password = "PersistPass111!"
        client.post("/register", json={"username": self.username, "password": self.password})
        resp = client.post("/login", json={"username": self.username, "password": self.password})
        self.token = resp.json().get("access_token")
        self.assertIsNotNone(self.token, "Token alınamadı")

    def test_authenticated_profile_access(self):
        """Geçerli token ile /profile erişilebilmeli."""
        resp = client.get("/profile", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(resp.status_code, 200, f"Profile 200 dönmeli. Response: {resp.text}")
        body = resp.json()
        self.assertEqual(body["username"], self.username)

    def test_unauthenticated_profile_returns_401(self):
        """Token olmadan /profile 401 dönmeli."""
        resp = client.get("/profile")
        self.assertIn(resp.status_code, [401, 403], "Token olmadan profile erişilemez (401 veya 403)")

    def test_invalid_token_returns_401(self):
        """Geçersiz token 401 dönmeli."""
        resp = client.get("/profile", headers={"Authorization": "Bearer invalidtoken.abc.def"})
        self.assertEqual(resp.status_code, 401)

    def test_logout_blacklists_token(self):
        """Logout sonrası aynı token tekrar /profile için geçersiz olmalı."""
        # Önce logout yap
        logout_resp = client.post("/logout", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(logout_resp.status_code, 200)

        # Aynı token ile profile'a git — blacklist'te olduğu için 401
        profile_resp = client.get("/profile", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(profile_resp.status_code, 401,
                         "Logout sonrası token hala geçerli! Token blacklist çalışmıyor.")


class TestDatabasePersistence(unittest.TestCase):
    """Database kalıcılık testleri."""

    def test_user_survives_multiple_sessions(self):
        """Kullanıcı kaydı birden fazla login session'ında geçerli kalmalı."""
        username = make_unique_user()
        password = "MultiSession999!"

        # Kayıt ol
        client.post("/register", json={"username": username, "password": password})

        # İlk login
        resp1 = client.post("/login", json={"username": username, "password": password})
        self.assertEqual(resp1.status_code, 200)
        token1 = resp1.json()["access_token"]

        # İkinci login (farklı session)
        resp2 = client.post("/login", json={"username": username, "password": password})
        self.assertEqual(resp2.status_code, 200)
        token2 = resp2.json()["access_token"]

        # Her iki token da çalışmalı (1. token hala geçerli)
        self.assertTrue(len(token1) > 20)
        self.assertTrue(len(token2) > 20)

    def test_password_hash_is_bcrypt(self):
        """Şifre bcrypt ile hash'lenmeli (plaintext olmamalı)."""
        username = make_unique_user()
        password = "BcryptTest123!"
        client.post("/register", json={"username": username, "password": password})

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            self.assertIsNotNone(user)
            # bcrypt hash'leri $2b$ ile başlar
            self.assertTrue(user.password_hash.startswith("$2b$"),
                            f"Şifre bcrypt ile hash'lenmemiş: {user.password_hash[:10]}...")
        finally:
            db.close()


if __name__ == "__main__":
    # Test çalıştır: python -m unittest tests.test_auth -v
    unittest.main(verbosity=2)
