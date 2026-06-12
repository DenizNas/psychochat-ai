import unittest
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

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
    PaymentTransaction,
    SubscriptionStatus,
    PaymentStatus
)

class TestSubscriptionSystem(unittest.TestCase):

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
        self.original_api_key = settings.IYZICO_API_KEY
        self.original_secret_key = settings.IYZICO_SECRET_KEY
        self.original_base = settings.IYZICO_BASE_URL
        self.original_callback = settings.IYZICO_CALLBACK_URL
        self.original_mode = settings.PAYMENT_MODE

        settings.IYZICO_API_KEY = "test_api_key"
        settings.IYZICO_SECRET_KEY = "test_secret_key"
        settings.IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
        settings.IYZICO_CALLBACK_URL = "http://localhost:8000/payments/webhook/iyzico"
        settings.PAYMENT_MODE = "sandbox"

        db = SessionLocal()
        try:
            # Clear transactions and subscriptions first to avoid FK constraints
            db.query(PaymentTransaction).delete()
            db.query(UserSubscription).delete()
            db.query(UserProfile).delete()
            db.query(User).delete()

            # Ensure default plans are seeded for these tests
            db.query(SubscriptionPlan).delete()
            plans = [
                SubscriptionPlan(
                    id=1,
                    name="free",
                    price_lira=Decimal("0.00"),
                    billing_interval="monthly",
                    description="Free plan",
                    is_active=True
                ),
                SubscriptionPlan(
                    id=2,
                    name="premium",
                    price_lira=Decimal("199.99"),
                    billing_interval="monthly",
                    description="Premium plan",
                    is_active=True
                ),
                SubscriptionPlan(
                    id=3,
                    name="professional_support",
                    price_lira=Decimal("499.99"),
                    billing_interval="monthly",
                    description="Professional plan",
                    is_active=True
                )
            ]
            db.add_all(plans)

            # Setup test user
            self.test_username = "test_billing_user"
            hashed_pw = get_password_hash("testpassword")
            user = User(username=self.test_username, password_hash=hashed_pw)
            db.add(user)
            db.commit()

            # Generate authorization token
            self.auth_token = create_access_token(data={"sub": self.test_username})
            self.auth_headers = {"Authorization": f"Bearer {self.auth_token}"}
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def tearDown(self):
        settings.IYZICO_API_KEY = self.original_api_key
        settings.IYZICO_SECRET_KEY = self.original_secret_key
        settings.IYZICO_BASE_URL = self.original_base
        settings.IYZICO_CALLBACK_URL = self.original_callback
        settings.PAYMENT_MODE = self.original_mode

    def test_get_plans(self):
        """Verify that plans endpoint returns list of seeded active plans and correct prices."""
        client = TestClient(app)
        res = client.get("/subscriptions/plans")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 3)
        names = [item["name"] for item in data]
        self.assertIn("free", names)
        self.assertIn("premium", names)
        self.assertIn("professional_support", names)
        # Ensure Decimal numeric formatting works correctly on the JSON serialization
        premium_plan = next(item for item in data if item["name"] == "premium")
        self.assertEqual(premium_plan["price_lira"], "199.99")

    def test_get_my_subscription_default_free(self):
        """Verify that a user without active subscription returns inactive status on free plan."""
        client = TestClient(app)
        res = client.get("/subscriptions/me", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["has_premium"], False)
        self.assertEqual(data["plan_name"], "free")
        self.assertEqual(data["status"], "inactive")

    def test_checkout_requires_auth(self):
        """Verify that checkout endpoint returns 401 when no authorization headers are provided."""
        client = TestClient(app)
        res = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers={"X-Idempotency-Key": str(uuid.uuid4())})
        self.assertEqual(res.status_code, 401)

    def test_checkout_requires_idempotency_key(self):
        """Verify that checkout endpoint returns 400 if X-Idempotency-Key header is missing."""
        client = TestClient(app)
        res = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=self.auth_headers)
        # FastAPI returns 422 Unprocessable Entity for missing header aliased to X-Idempotency-Key or 400
        self.assertTrue(res.status_code in [400, 422])

    def test_checkout_missing_config_returns_error(self):
        """Verify that checkout returns a clear 503 configuration error if credentials are empty."""
        # Mock configure empty credentials
        original_api_key = settings.IYZICO_API_KEY
        original_secret_key = settings.IYZICO_SECRET_KEY
        
        settings.IYZICO_API_KEY = ""
        settings.IYZICO_SECRET_KEY = ""

        try:
            client = TestClient(app)
            headers = {**self.auth_headers, "X-Idempotency-Key": str(uuid.uuid4())}
            res = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers)
            self.assertEqual(res.status_code, 503)
            self.assertIn("yapılandırılmamış", res.json()["message"])
        finally:
            # Restore settings
            settings.IYZICO_API_KEY = original_api_key
            settings.IYZICO_SECRET_KEY = original_secret_key

    def test_webhook_rejects_invalid_signature(self):
        """Verify that the webhook endpoint rejects calls with invalid signatures."""
        client = TestClient(app)
        headers = {"X-Iyzico-Signature": "invalid_signature"}
        res = client.post("/payments/webhook/iyzico", json={"status": "success"}, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Geçersiz imza", res.json()["message"])

    def test_webhook_success_activates_subscription(self):
        """Verify that verified success webhook changes statuses and activates subscription."""
        # 1. Create a pending transaction
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,  # Premium
                status=SubscriptionStatus.PENDING
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)

            tx = PaymentTransaction(
                user_id=self.test_username,
                subscription_id=user_sub.id,
                provider_transaction_id="mock_prov_id_123",
                amount=Decimal("199.99"),
                currency="TRY",
                status=PaymentStatus.PENDING,
                idempotency_key=idempotency
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        # 2. Trigger webhook success with valid test signature
        client = TestClient(app)
        webhook_payload = {
            "status": "success",
            "paymentId": "mock_prov_id_123",
            "conversationId": idempotency,
            "price": "199.99",
            "paymentMethod": "card"
        }
        headers = {"X-Iyzico-Signature": "valid_signature_for_test"}
        res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        # 3. Verify status updates in db
        db = SessionLocal()
        try:
            db_tx = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == idempotency).first()
            self.assertEqual(db_tx.status, PaymentStatus.SUCCESS)

            db_sub = db.query(UserSubscription).filter(UserSubscription.id == db_tx.subscription_id).first()
            self.assertEqual(db_sub.status, SubscriptionStatus.ACTIVE)
            self.assertIsNotNone(db_sub.current_period_end)
        finally:
            db.close()

    def test_no_card_fields_exist_in_request_models(self):
        """PCI-DSS Compliance verify: ensure no card, CVV, expiry details exist in the request schemas."""
        from src.api.main import CheckoutRequest
        fields = CheckoutRequest.__fields__.keys() if hasattr(CheckoutRequest, "__fields__") else CheckoutRequest.model_fields.keys()
        
        forbidden = ["card", "cvv", "expiry", "pan", "card_number", "iban"]
        for f in fields:
            for bad in forbidden:
                self.assertNotIn(bad, f.lower())

    def test_checkout_mode_not_sandbox_returns_error(self):
        """Verify that checkout returns a clear 503 configuration error if PAYMENT_MODE is not sandbox."""
        original_mode = settings.PAYMENT_MODE
        settings.PAYMENT_MODE = "live"
        try:
            client = TestClient(app)
            headers = {**self.auth_headers, "X-Idempotency-Key": str(uuid.uuid4())}
            res = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers)
            self.assertEqual(res.status_code, 503)
            self.assertIn("yapılandırılmamış", res.json()["message"])
        finally:
            settings.PAYMENT_MODE = original_mode

    def test_webhook_duplicate_is_idempotent(self):
        """Verify that receiving the same webhook twice returns already_processed and does not duplicate status change."""
        # 1. Create a pending transaction
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,
                status=SubscriptionStatus.PENDING
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)

            tx = PaymentTransaction(
                user_id=self.test_username,
                subscription_id=user_sub.id,
                provider_transaction_id="mock_prov_id_dup",
                amount=Decimal("199.99"),
                currency="TRY",
                status=PaymentStatus.PENDING,
                idempotency_key=idempotency
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        # 2. Trigger webhook success first time
        client = TestClient(app)
        webhook_payload = {
            "status": "success",
            "paymentId": "mock_prov_id_dup",
            "conversationId": idempotency,
            "price": "199.99",
            "paymentMethod": "card"
        }
        headers = {"X-Iyzico-Signature": "valid_signature_for_test"}
        res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "processed")

        # 3. Trigger webhook duplicate second time
        res_dup = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res_dup.status_code, 200)
        self.assertEqual(res_dup.json()["status"], "already_processed")

    def test_webhook_failure_does_not_activate_subscription(self):
        """Verify that a failed webhook payload marks transaction failed and leaves subscription inactive."""
        # 1. Create a pending transaction
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,
                status=SubscriptionStatus.PENDING
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)

            tx = PaymentTransaction(
                user_id=self.test_username,
                subscription_id=user_sub.id,
                provider_transaction_id="mock_prov_id_fail",
                amount=Decimal("199.99"),
                currency="TRY",
                status=PaymentStatus.PENDING,
                idempotency_key=idempotency
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        # 2. Trigger webhook failure
        client = TestClient(app)
        webhook_payload = {
            "status": "failure",
            "paymentId": "mock_prov_id_fail",
            "conversationId": idempotency,
            "price": "199.99",
            "paymentMethod": "card"
        }
        headers = {"X-Iyzico-Signature": "valid_signature_for_test"}
        res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        # 3. Verify status in DB is FAILED
        db = SessionLocal()
        try:
            db_tx = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == idempotency).first()
            self.assertEqual(db_tx.status, PaymentStatus.FAILED)

            db_sub = db.query(UserSubscription).filter(UserSubscription.id == db_tx.subscription_id).first()
            self.assertNotEqual(db_sub.status, SubscriptionStatus.ACTIVE)
        finally:
            db.close()

    def test_webhook_rejects_mock_in_production(self):
        """Verify that a mock token webhook is rejected in non-dev environment configurations."""
        import os
        original_env = settings.APP_ENV
        original_os_env = os.environ.get("APP_ENV")
        
        # We manually change APP_ENV to mock staging/production validation rules
        settings.APP_ENV = "production"
        os.environ["APP_ENV"] = "production"
        
        client = TestClient(app)
        webhook_payload = {
            "status": "success",
            "paymentId": "mock_token_123",
            "conversationId": "mock_token_123",
            "price": "199.99",
            "paymentMethod": "card"
        }
        headers = {"X-Iyzico-Signature": "valid_signature_for_test"}
        
        try:
            # Under production environment, mock token is prohibited
            res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("Geçersiz işlem", res.json()["message"])
        finally:
            settings.APP_ENV = original_env
            if original_os_env is not None:
                os.environ["APP_ENV"] = original_os_env
            elif "APP_ENV" in os.environ:
                del os.environ["APP_ENV"]

    def test_checkout_with_sandbox_config_returns_structured_response(self):
        """Verify checkout endpoint returns structured response under correct sandbox configuration."""
        original_api_key = settings.IYZICO_API_KEY
        original_secret_key = settings.IYZICO_SECRET_KEY
        original_base = settings.IYZICO_BASE_URL
        original_callback = settings.IYZICO_CALLBACK_URL
        original_mode = settings.PAYMENT_MODE

        settings.IYZICO_API_KEY = "test_api_key"
        settings.IYZICO_SECRET_KEY = "test_secret_key"
        settings.IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
        settings.IYZICO_CALLBACK_URL = "http://localhost:8000/payments/webhook/iyzico"
        settings.PAYMENT_MODE = "sandbox"

        try:
            client = TestClient(app)
            headers = {**self.auth_headers, "X-Idempotency-Key": str(uuid.uuid4())}
            res = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "pending")
            self.assertIn("checkout_url", data)
            self.assertIn("transaction_id", data)
        finally:
            settings.IYZICO_API_KEY = original_api_key
            settings.IYZICO_SECRET_KEY = original_secret_key
            settings.IYZICO_BASE_URL = original_base
            settings.IYZICO_CALLBACK_URL = original_callback
            settings.PAYMENT_MODE = original_mode

    def test_production_mode_rejects_localhost_callback(self):
        """Verify that production mode rejects localhost callback URL."""
        from src.services.payment_provider import IyzicoProvider, ProviderNotConfigured
        original_mode = settings.PAYMENT_MODE
        original_callback = settings.IYZICO_CALLBACK_URL
        original_api_key = settings.IYZICO_API_KEY
        original_secret_key = settings.IYZICO_SECRET_KEY
        original_base = settings.IYZICO_BASE_URL

        settings.PAYMENT_MODE = "production"
        settings.IYZICO_CALLBACK_URL = "https://localhost:8000/payments/webhook/iyzico"
        settings.IYZICO_API_KEY = "prod_api_key"
        settings.IYZICO_SECRET_KEY = "prod_secret_key"
        settings.IYZICO_BASE_URL = "https://api.iyzipay.com"

        provider = IyzicoProvider()
        try:
            with self.assertRaises(ProviderNotConfigured):
                provider._check_configuration()
        finally:
            settings.PAYMENT_MODE = original_mode
            settings.IYZICO_CALLBACK_URL = original_callback
            settings.IYZICO_API_KEY = original_api_key
            settings.IYZICO_SECRET_KEY = original_secret_key
            settings.IYZICO_BASE_URL = original_base

    def test_production_mode_rejects_sandbox_base_url(self):
        """Verify that production mode rejects sandbox base URL."""
        from src.services.payment_provider import IyzicoProvider, ProviderNotConfigured
        original_mode = settings.PAYMENT_MODE
        original_base = settings.IYZICO_BASE_URL
        original_api_key = settings.IYZICO_API_KEY
        original_secret_key = settings.IYZICO_SECRET_KEY
        original_callback = settings.IYZICO_CALLBACK_URL

        settings.PAYMENT_MODE = "production"
        settings.IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
        settings.IYZICO_API_KEY = "prod_api_key"
        settings.IYZICO_SECRET_KEY = "prod_secret_key"
        settings.IYZICO_CALLBACK_URL = "https://myprodapp.com/callback"

        provider = IyzicoProvider()
        try:
            with self.assertRaises(ProviderNotConfigured):
                provider._check_configuration()
        finally:
            settings.PAYMENT_MODE = original_mode
            settings.IYZICO_BASE_URL = original_base
            settings.IYZICO_API_KEY = original_api_key
            settings.IYZICO_SECRET_KEY = original_secret_key
            settings.IYZICO_CALLBACK_URL = original_callback

    def test_production_mode_disables_mocked_checkout(self):
        """Verify that production mode disables fallback mocked checkout responses."""
        from src.services.payment_provider import IyzicoProvider
        original_mode = settings.PAYMENT_MODE
        original_base = settings.IYZICO_BASE_URL
        original_api_key = settings.IYZICO_API_KEY
        original_secret_key = settings.IYZICO_SECRET_KEY
        original_callback = settings.IYZICO_CALLBACK_URL

        settings.PAYMENT_MODE = "production"
        settings.IYZICO_BASE_URL = "https://api.iyzipay.com"  # Must not contain sandbox
        settings.IYZICO_API_KEY = "prod_api_key"
        settings.IYZICO_SECRET_KEY = "prod_secret_key"
        settings.IYZICO_CALLBACK_URL = "https://myprodapp.com/callback"

        provider = IyzicoProvider()
        try:
            # Running checkout session initialize should fail and raise an exception directly instead of falling back to mock
            with self.assertRaises(Exception) as ctx:
                provider.create_checkout_session(
                    username="test_user",
                    plan_name="premium",
                    price=199.99,
                    transaction_id="TX_TEST123"
                )
            self.assertNotIn("mock_token_", str(ctx.exception))
        finally:
            settings.PAYMENT_MODE = original_mode
            settings.IYZICO_BASE_URL = original_base
            settings.IYZICO_API_KEY = original_api_key
            settings.IYZICO_SECRET_KEY = original_secret_key
            settings.IYZICO_CALLBACK_URL = original_callback

    def test_checkout_idempotency_duplicate_returns_existing(self):
        """Verify that checkout idempotency returns existing pending transaction for same user."""
        client = TestClient(app)
        idempotency_key = str(uuid.uuid4())
        headers = {**self.auth_headers, "X-Idempotency-Key": idempotency_key}

        # First request
        res1 = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        tx_id1 = data1["transaction_id"]

        # Second request with same key should return the exact same transaction ID
        res2 = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["transaction_id"], tx_id1)

        # Database should only contain 1 transaction for this key
        db = SessionLocal()
        try:
            count = db.query(PaymentTransaction).filter(
                PaymentTransaction.idempotency_key == idempotency_key
            ).count()
            self.assertEqual(count, 1)
        finally:
            db.close()

    def test_checkout_idempotency_key_uuid_validation(self):
        """Verify that invalid UUID format for X-Idempotency-Key is rejected."""
        client = TestClient(app)
        headers = {**self.auth_headers, "X-Idempotency-Key": "invalid-uuid-format"}
        res = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("valid UUID", res.json()["message"])

    def test_same_idempotency_key_across_users_rejected(self):
        """Verify that same idempotency key used by a different user is rejected with HTTP 403."""
        client = TestClient(app)
        idempotency_key = str(uuid.uuid4())
        
        # User A requests
        headers_a = {**self.auth_headers, "X-Idempotency-Key": idempotency_key}
        res_a = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers_a)
        self.assertEqual(res_a.status_code, 200)

        # User B requests with same key
        token_b = create_access_token(data={"sub": "user_b_test"})
        # Seed user B in DB
        db = SessionLocal()
        try:
            hashed_pw = get_password_hash("testpassword")
            user_b = User(username="user_b_test", password_hash=hashed_pw)
            db.add(user_b)
            db.commit()
        finally:
            db.close()

        headers_b = {"Authorization": f"Bearer {token_b}", "X-Idempotency-Key": idempotency_key}
        res_b = client.post("/subscriptions/checkout", json={"plan_id": 2}, headers=headers_b)
        self.assertEqual(res_b.status_code, 403)
        self.assertIn("kullanıcıya ait", res_b.json()["message"])

    def test_webhook_unsigned_event_requires_retrieve_validation(self):
        """Verify that unsigned webhook requires and executes retrieve API validation."""
        from unittest.mock import patch, Mock
        
        # Create a pending transaction
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,
                status=SubscriptionStatus.PENDING
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)

            tx = PaymentTransaction(
                user_id=self.test_username,
                subscription_id=user_sub.id,
                provider_transaction_id="prov_id_retrieve_test",
                amount=Decimal("199.99"),
                currency="TRY",
                status=PaymentStatus.PENDING,
                idempotency_key=idempotency
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        # Webhook payload with NO signature header
        client = TestClient(app)
        webhook_payload = {
            "token": "real_token_for_retrieve_test",
            "status": "success",
            "conversationId": idempotency
        }

        # Mock the requests.post to simulate successful retrieve API validation
        mock_response_data = {
            "status": "success",
            "paymentStatus": "SUCCESS",
            "paymentId": "prov_id_retrieve_test",
            "conversationId": idempotency,
            "price": "199.99"
        }

        with patch("requests.post") as mock_post:
            mock_res = Mock()
            mock_res.status_code = 200
            mock_res.json.return_value = mock_response_data
            mock_post.return_value = mock_res

            res = client.post("/payments/webhook/iyzico", json=webhook_payload)
            self.assertEqual(res.status_code, 200)

        # Verify transaction status is updated to SUCCESS in local DB
        db = SessionLocal()
        try:
            db_tx = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == idempotency).first()
            self.assertEqual(db_tx.status, PaymentStatus.SUCCESS)
        finally:
            db.close()

    def test_webhook_retrieve_validation_fails_rejects_webhook(self):
        """Verify that if retrieve API validation fails for unsigned event, the webhook is rejected."""
        from unittest.mock import patch

        # Webhook payload with NO signature header
        client = TestClient(app)
        webhook_payload = {
            "token": "failing_retrieve_token",
            "conversationId": str(uuid.uuid4())
        }

        # Mock requests.post to raise exception (API fail)
        with patch("requests.post", side_effect=Exception("API connection failed")):
            res = client.post("/payments/webhook/iyzico", json=webhook_payload)
            self.assertEqual(res.status_code, 400)
            self.assertIn("Geçersiz veya doğrulanamayan işlem", res.json()["message"])

    def test_invalid_webhook_does_not_change_subscription(self):
        """Verify that invalid signature webhook does not update subscription status."""
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,
                status=SubscriptionStatus.PENDING
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)
            user_sub_id = user_sub.id
        finally:
            db.close()

        client = TestClient(app)
        webhook_payload = {
            "status": "success",
            "paymentId": "mock_id_xyz",
            "conversationId": idempotency
        }
        # Webhook signature header exists but is invalid
        headers = {"X-Iyzico-Signature": "invalid_sig"}
        res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res.status_code, 400)

        # Verify subscription is still pending
        db = SessionLocal()
        try:
            db_sub = db.query(UserSubscription).filter(UserSubscription.id == user_sub_id).first()
            self.assertEqual(db_sub.status, SubscriptionStatus.PENDING)
        finally:
            db.close()

    def test_invalid_state_transition_rejected(self):
        """Verify that invalid state transitions (e.g. success -> failed) are rejected with 400."""
        # Create a SUCCESS transaction
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,
                status=SubscriptionStatus.ACTIVE
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)
            user_sub_id = user_sub.id

            tx = PaymentTransaction(
                user_id=self.test_username,
                subscription_id=user_sub_id,
                provider_transaction_id="mock_prov_id_trans_test",
                amount=Decimal("199.99"),
                currency="TRY",
                status=PaymentStatus.SUCCESS,
                idempotency_key=idempotency
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        # Try to update transaction status to FAILED via webhook
        client = TestClient(app)
        webhook_payload = {
            "status": "failed",
            "paymentId": "mock_prov_id_trans_test",
            "conversationId": idempotency,
            "price": "199.99",
            "paymentMethod": "card"
        }
        headers = {"X-Iyzico-Signature": "valid_signature_for_test"}
        res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Geçersiz işlem durum geçişi", res.json()["message"])

        # Check in DB that status is still SUCCESS
        db = SessionLocal()
        try:
            db_tx = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == idempotency).first()
            self.assertEqual(db_tx.status, PaymentStatus.SUCCESS)
        finally:
            db.close()

    def test_refund_updates_subscription_safely(self):
        """Verify that a refunded payment transaction sets subscription status to INACTIVE."""
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,
                status=SubscriptionStatus.ACTIVE
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)
            user_sub_id = user_sub.id

            tx = PaymentTransaction(
                user_id=self.test_username,
                subscription_id=user_sub_id,
                provider_transaction_id="mock_prov_id_refund_test",
                amount=Decimal("199.99"),
                currency="TRY",
                status=PaymentStatus.SUCCESS,
                idempotency_key=idempotency
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        # Trigger refunded webhook
        client = TestClient(app)
        webhook_payload = {
            "status": "refunded",
            "paymentId": "mock_prov_id_refund_test",
            "conversationId": idempotency,
            "price": "199.99",
            "paymentMethod": "card"
        }
        headers = {"X-Iyzico-Signature": "valid_signature_for_test"}
        res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        # Verify transaction status is REFUNDED, subscription status is INACTIVE
        db = SessionLocal()
        try:
            db_tx = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == idempotency).first()
            self.assertEqual(db_tx.status, PaymentStatus.REFUNDED)

            db_sub = db.query(UserSubscription).filter(UserSubscription.id == user_sub_id).first()
            self.assertEqual(db_sub.status, SubscriptionStatus.INACTIVE)
        finally:
            db.close()

    def test_cancel_updates_subscription_safely(self):
        """Verify that a canceled payment transaction updates subscription status to CANCELED."""
        db = SessionLocal()
        idempotency = str(uuid.uuid4())
        try:
            # Active subscription with end date in the future
            user_sub = UserSubscription(
                user_id=self.test_username,
                plan_id=2,
                status=SubscriptionStatus.ACTIVE,
                current_period_end=datetime.now(timezone.utc) + timedelta(days=15)
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)
            user_sub_id = user_sub.id

            tx = PaymentTransaction(
                user_id=self.test_username,
                subscription_id=user_sub_id,
                provider_transaction_id="mock_prov_id_cancel_test",
                amount=Decimal("199.99"),
                currency="TRY",
                status=PaymentStatus.SUCCESS,
                idempotency_key=idempotency
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        # Trigger canceled webhook
        client = TestClient(app)
        webhook_payload = {
            "status": "canceled",
            "paymentId": "mock_prov_id_cancel_test",
            "conversationId": idempotency,
            "price": "199.99",
            "paymentMethod": "card"
        }
        headers = {"X-Iyzico-Signature": "valid_signature_for_test"}
        res = client.post("/payments/webhook/iyzico", json=webhook_payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        # Verify transaction status is CANCELED, subscription cancel_at_period_end is True and status is CANCELED
        db = SessionLocal()
        try:
            db_tx = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == idempotency).first()
            self.assertEqual(db_tx.status, PaymentStatus.CANCELED)

            db_sub = db.query(UserSubscription).filter(UserSubscription.id == user_sub_id).first()
            self.assertEqual(db_sub.status, SubscriptionStatus.CANCELED)
            self.assertTrue(db_sub.cancel_at_period_end)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
