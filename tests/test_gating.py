import unittest
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from src.api.main import app
from src.core.config import settings
from src.services.auth import create_access_token, get_password_hash
from src.services.database import (
    init_db,
    SessionLocal,
    User,
    UserProfile,
    SubscriptionPlan,
    UserSubscription,
    SubscriptionStatus
)

class TestPremiumAccessGating(unittest.TestCase):

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
            db.query(UserSubscription).delete()
            db.query(UserProfile).delete()
            db.query(User).delete()
            db.query(SubscriptionPlan).delete()

            # Seed subscription plans
            self.free_plan = SubscriptionPlan(id=1, name="free", price_lira=Decimal("0.00"), billing_interval="monthly", description="Free", is_active=True)
            self.premium_plan = SubscriptionPlan(id=2, name="premium", price_lira=Decimal("199.99"), billing_interval="monthly", description="Premium", is_active=True)
            self.pro_plan = SubscriptionPlan(id=3, name="professional_support", price_lira=Decimal("499.99"), billing_interval="monthly", description="Professional Support", is_active=True)
            db.add_all([self.free_plan, self.premium_plan, self.pro_plan])

            # Seed users
            self.free_username = "free_user"
            self.premium_username = "premium_user"
            self.pro_username = "pro_user"

            hashed_pw = get_password_hash("testpassword")
            db.add(User(username=self.free_username, password_hash=hashed_pw))
            db.add(User(username=self.premium_username, password_hash=hashed_pw))
            db.add(User(username=self.pro_username, password_hash=hashed_pw))
            db.commit()

            # Seed subscriptions
            # Premium User subscription
            premium_sub = UserSubscription(user_id=self.premium_username, plan_id=2, status=SubscriptionStatus.ACTIVE)
            db.add(premium_sub)
            # Professional Support subscription
            pro_sub = UserSubscription(user_id=self.pro_username, plan_id=3, status=SubscriptionStatus.ACTIVE)
            db.add(pro_sub)
            db.commit()

            # Generate tokens
            self.free_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': self.free_username})}"}
            self.premium_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': self.premium_username})}"}
            self.pro_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': self.pro_username})}"}

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_free_user_blocked_from_gated_endpoint(self):
        """Verify free user is blocked from premium analytics dashboard with 403 and correct error structure."""
        client = TestClient(app)
        res = client.get("/analytics/dashboard?days=7", headers=self.free_headers)
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "PREMIUM_MEMBER_REQUIRED")
        self.assertEqual(data["required_tier"], "premium")
        self.assertIn("yalnızca Premium", data["message"])

    def test_premium_user_allowed_on_gated_endpoint(self):
        """Verify premium user is allowed to access gated analytics dashboard."""
        client = TestClient(app)
        res = client.get("/analytics/dashboard?days=7", headers=self.premium_headers)
        # Should bypass 403. Even if database/redis returns 500 or 200, status must not be 403.
        self.assertNotEqual(res.status_code, 403)

    def test_pro_support_user_allowed_on_gated_endpoint(self):
        """Verify professional support user is allowed to access gated analytics dashboard."""
        client = TestClient(app)
        res = client.get("/analytics/dashboard?days=7", headers=self.pro_headers)
        # Should bypass 403.
        self.assertNotEqual(res.status_code, 403)

    def test_free_user_can_access_profile(self):
        """Verify free user is allowed to access profile endpoint."""
        client = TestClient(app)
        res = client.get("/profile", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)

    def test_free_user_can_access_privacy_export(self):
        """Verify free user is allowed to export their privacy logs (GDPR compliance)."""
        client = TestClient(app)
        res = client.get("/privacy/export", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)

    def test_free_user_can_access_mood_journal(self):
        """Verify free user is allowed to access mood journal list."""
        client = TestClient(app)
        res = client.get("/journal/mood", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)

    def test_payment_history_requires_premium(self):
        """Verify payment history endpoint is blocked for free user but allowed for premium."""
        client = TestClient(app)
        res_free = client.get("/payments/history", headers=self.free_headers)
        self.assertEqual(res_free.status_code, 403)

        res_premium = client.get("/payments/history", headers=self.premium_headers)
        self.assertNotEqual(res_premium.status_code, 403)

    def test_subscription_endpoints_accessible_to_free_user(self):
        """Verify subscriptions checkout and plan status remain accessible to free user."""
        client = TestClient(app)
        
        # plans check
        res_plans = client.get("/subscriptions/plans")
        self.assertEqual(res_plans.status_code, 200)

        # /subscriptions/me check
        res_me = client.get("/subscriptions/me", headers=self.free_headers)
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.json()["has_premium"], False)

    def test_free_user_can_access_wellness_plan(self):
        """Verify free user is allowed to access and refresh wellness plan."""
        client = TestClient(app)
        res = client.get("/analytics/wellness-plan", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("today_focus", data)
        self.assertIn("ai_wellness_summary", data)

        res_ref = client.post("/analytics/wellness-plan/refresh", headers=self.free_headers)
        self.assertEqual(res_ref.status_code, 200)

    def test_free_user_can_access_recommendations(self):
        """Verify free user is allowed to access and refresh recommendations."""
        client = TestClient(app)
        res = client.get("/analytics/recommendations", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)

        res_ref = client.post("/analytics/recommendations/refresh", headers=self.free_headers)
        self.assertEqual(res_ref.status_code, 200)

    def test_free_user_can_access_scheduled_interventions(self):
        """Verify free user is allowed to access and refresh scheduled interventions."""
        client = TestClient(app)
        res = client.get("/analytics/scheduled-interventions", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)

        res_ref = client.post("/analytics/scheduled-interventions/refresh", headers=self.free_headers)
        self.assertEqual(res_ref.status_code, 200)
