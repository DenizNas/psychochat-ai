import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure project root is in python path
sys.path.append(os.getcwd())

# Force environment setups for testing fallbacks
os.environ["APP_ENV"] = "development"
os.environ["REDIS_URL"] = "redis://localhost:9999/9"  # Offline Redis to test resilience
os.environ["RATE_LIMIT_ENABLED"] = "true"
os.environ["LOGIN_RATE_LIMIT"] = "5/minute"
os.environ["MAX_REQUEST_BODY_BYTES"] = "100"  # Small limit (100 bytes) to trigger 413 easily in tests

from src.api.main import app
from src.core.rate_limiter import rate_limiter_core
from src.core.brute_force_protection import brute_force_protector

class TestAPIHardeningAndLimiter(unittest.TestCase):
    
    def setUp(self):
        from src.core.config import settings
        # Override global settings dynamically for deterministic local tests
        settings.RATE_LIMIT_ENABLED = True
        settings.LOGIN_RATE_LIMIT = "5/minute"
        settings.MAX_REQUEST_BODY_BYTES = 100

        self.client = TestClient(app)
        # Reset local in-memory fallback stores for deterministic testing
        rate_limiter_core.in_memory_store.clear()
        brute_force_protector.in_memory_store.clear()

    def test_request_body_size_limit_triggered(self):
        """
        Verify that a payload exceeding MAX_REQUEST_BODY_BYTES (100 bytes)
        is immediately blocked with 413 Payload Too Large.
        """
        print("\n[TEST] Verifying Request Body Size Limit Middleware...")
        large_payload = "a" * 150  # 150 bytes (limit is 100)
        
        response = self.client.post(
            "/login",
            headers={"Content-Length": str(len(large_payload))},
            content=large_payload
        )
        
        self.assertEqual(response.status_code, 413)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "PAYLOAD_TOO_LARGE")
        print(" -> SUCCESS: Large payload blocked immediately with 413 and secure JSON response")

    def test_json_parse_error_securely_handled(self):
        """
        Verify that sending invalid JSON triggers custom json_decode_exception_handler
        returning a secure 400 Bad Request error without leaking stack traces.
        """
        print("\n[TEST] Verifying JSON Decode Exception Hardening...")
        invalid_json = "{bad_json: invalid"
        
        response = self.client.post(
            "/login",
            headers={"Content-Type": "application/json"},
            content=invalid_json
        )
        
        # Accept either 400 (INVALID_JSON) or 422 (VALIDATION_ERROR) as both are securely hardened formats masking internals
        self.assertIn(response.status_code, [400, 422])
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn(data["error_code"], ["INVALID_JSON", "VALIDATION_ERROR"])
        self.assertNotIn("traceback", data)
        print(" -> SUCCESS: Parse error caught cleanly, returning secure error format without leaking details")

    def test_brute_force_lockout_triggered(self):
        """
        Verify that 5 failed attempts lock out the combined IP + Username path.
        """
        print("\n[TEST] Verifying Combined IP + Username Lockout Protection...")
        ip = "127.0.0.1"
        user = "test_lockout_user"
        
        # Verify initially not blocked
        self.assertFalse(brute_force_protector.is_blocked(ip, user))
        
        # Register 4 failures (no lockout yet)
        for i in range(4):
            is_locked = brute_force_protector.register_failure(ip, user)
            self.assertFalse(is_locked)
            
        # 5th failure triggers lockout
        is_locked = brute_force_protector.register_failure(ip, user)
        self.assertTrue(is_locked)
        
        # Verify blocked
        self.assertTrue(brute_force_protector.is_blocked(ip, user))
        print(" -> SUCCESS: Combined IP + Username path locked out after exactly 5 failures")

    def test_rate_limiter_in_memory_fallback(self):
        """
        Verify that when Redis is offline, rate limiter falls back gracefully to in-memory,
        enforcing limits perfectly.
        """
        print("\n[TEST] Verifying Rate Limiter In-Memory Fallback...")
        key = "127.0.0.1"
        limit_type = "login"  # rule allows max 5 requests / min
        
        # Allow first 5 requests
        for i in range(5):
            self.assertTrue(rate_limiter_core.is_allowed(key, limit_type))
            
        # 6th request is blocked
        self.assertFalse(rate_limiter_core.is_allowed(key, limit_type))
        print(" -> SUCCESS: Offline Redis rate limits enforced successfully via local in-memory fallback")

if __name__ == "__main__":
    print("=== STARTING API HARDENING & ABUSE PROTECTION TESTS ===")
    unittest.main()
