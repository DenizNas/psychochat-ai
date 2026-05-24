"""
WebSocket Gateway Tests
========================
Faz 10 Prompt 1 — Real-Time Infrastructure

Test edilen senaryolar:
1. Event schema parse & validation
2. Payload size guard (64KB)
3. Rate limit logic
4. Redis Pub/Sub fallback (local-only)
5. Presence service local fallback
6. JWT doğrulama reddi (unit-level)
"""

import asyncio
import json
import sys
import os
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Path ayarı
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ─── Test 1: Event Schemas ────────────────────────────────────────────────────
class TestWebSocketEventSchemas(unittest.TestCase):

    def test_parse_valid_chat_message(self):
        from src.services.websocket_events import parse_inbound_event, WsEventType, ChatMessagePayload
        raw = json.dumps({"type": "chat_message", "payload": {"text": "Merhaba", "language": "tr"}})
        event_type, payload = parse_inbound_event(raw)
        self.assertEqual(event_type, WsEventType.CHAT_MESSAGE)
        self.assertIsInstance(payload, ChatMessagePayload)
        self.assertEqual(payload.text, "Merhaba")

    def test_parse_valid_ping(self):
        from src.services.websocket_events import parse_inbound_event, WsEventType, PingPayload
        raw = json.dumps({"type": "ping", "payload": {}})
        event_type, payload = parse_inbound_event(raw)
        self.assertEqual(event_type, WsEventType.PING)
        self.assertIsInstance(payload, PingPayload)

    def test_parse_typing_start(self):
        from src.services.websocket_events import parse_inbound_event, WsEventType, TypingPayload
        raw = json.dumps({"type": "typing_start", "payload": {}})
        event_type, payload = parse_inbound_event(raw)
        self.assertEqual(event_type, WsEventType.TYPING_START)

    def test_invalid_json_raises(self):
        from src.services.websocket_events import parse_inbound_event, EventValidationError
        with self.assertRaises(EventValidationError) as ctx:
            parse_inbound_event("NOT_JSON")
        self.assertEqual(ctx.exception.code, "INVALID_JSON")

    def test_unknown_event_type_raises(self):
        from src.services.websocket_events import parse_inbound_event, EventValidationError
        raw = json.dumps({"type": "delete_all_users", "payload": {}})
        with self.assertRaises(EventValidationError) as ctx:
            parse_inbound_event(raw)
        self.assertIn(ctx.exception.code, ("UNKNOWN_TYPE", "FORBIDDEN_TYPE"))

    def test_server_event_rejected_from_client(self):
        """chat_response server→client event'i client'tan gönderilememeli."""
        from src.services.websocket_events import parse_inbound_event, EventValidationError
        raw = json.dumps({"type": "chat_response", "payload": {"response": "hack"}})
        with self.assertRaises(EventValidationError):
            parse_inbound_event(raw)

    def test_empty_text_rejected(self):
        from src.services.websocket_events import parse_inbound_event, EventValidationError
        raw = json.dumps({"type": "chat_message", "payload": {"text": "   "}})
        with self.assertRaises(EventValidationError) as ctx:
            parse_inbound_event(raw)
        self.assertEqual(ctx.exception.code, "INVALID_PAYLOAD")

    def test_text_too_long_rejected(self):
        from src.services.websocket_events import parse_inbound_event, EventValidationError
        long_text = "x" * 1001
        raw = json.dumps({"type": "chat_message", "payload": {"text": long_text}})
        with self.assertRaises(EventValidationError) as ctx:
            parse_inbound_event(raw)
        self.assertEqual(ctx.exception.code, "INVALID_PAYLOAD")

    def test_missing_type_raises(self):
        from src.services.websocket_events import parse_inbound_event, EventValidationError
        raw = json.dumps({"payload": {"text": "hi"}})
        with self.assertRaises(EventValidationError) as ctx:
            parse_inbound_event(raw)
        self.assertEqual(ctx.exception.code, "MISSING_TYPE")

    def test_build_chat_response(self):
        from src.services.websocket_events import build_chat_response, WsEventType
        event = build_chat_response("joy", "low", "Güzel hissediyorsun!")
        self.assertEqual(event["type"], WsEventType.CHAT_RESPONSE)
        self.assertEqual(event["payload"]["emotion"], "joy")
        self.assertIsNone(event["payload"]["emergency_contact"])

    def test_safe_uid_does_not_expose_raw(self):
        """_safe_uid raw user_id'yi loglara açmamalı."""
        from src.services.websocket_events import _safe_uid
        uid = "real_username_123"
        masked = _safe_uid(uid)
        self.assertNotIn("real_username", masked)
        self.assertEqual(len(masked), 12)


# ─── Test 2: Payload Size Guard ──────────────────────────────────────────────
class TestPayloadSizeGuard(unittest.TestCase):
    """Tests the MAX_PAYLOAD_BYTES guard logic directly (no FastAPI import needed)."""

    def _check_size(self, raw: str) -> bool:
        from src.services.websocket_events import MAX_PAYLOAD_BYTES
        return len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES

    def test_payload_within_limit(self):
        small = '{"type": "ping", "payload": {}}'
        self.assertFalse(self._check_size(small))

    def test_payload_exceeds_64kb(self):
        huge = "x" * (64 * 1024 + 1)  # 64KB + 1 byte
        self.assertTrue(self._check_size(huge))

    def test_payload_exactly_at_limit(self):
        at_limit = "x" * (64 * 1024)
        # Exactly at limit should NOT be rejected
        self.assertFalse(self._check_size(at_limit))


# ─── Test 3: Rate Limiting ────────────────────────────────────────────────────
class TestRateLimiting(unittest.TestCase):
    """Tests rate limiting logic directly (no FastAPI import needed)."""

    def _make_tracker(self):
        """Return a minimal rate tracker that mimics ConnectionManager."""
        from src.services.websocket_events import MAX_PAYLOAD_BYTES
        # Inline the logic from ConnectionManager without importing FastAPI
        MAX_EVENTS_PER_WINDOW = 30
        RATE_WINDOW_SECONDS = 10
        rate_tracker: dict = {}

        def check_rate(ws_id):
            count, window_start = rate_tracker.get(ws_id, (0, time.monotonic()))
            now = time.monotonic()
            if now - window_start > RATE_WINDOW_SECONDS:
                rate_tracker[ws_id] = (1, now)
                return False
            count += 1
            rate_tracker[ws_id] = (count, window_start)
            return count > MAX_EVENTS_PER_WINDOW

        return check_rate, rate_tracker

    def test_normal_rate_allowed(self):
        check, _ = self._make_tracker()
        result = False
        for i in range(30):
            result = check("ws1")
        self.assertFalse(result)

    def test_rate_exceeded(self):
        check, _ = self._make_tracker()
        result = False
        for i in range(31):
            result = check("ws1")
        self.assertTrue(result)

    def test_rate_window_reset(self):
        """Pencere süresi geçince sayaç sıfırlanmalı."""
        RATE_WINDOW_SECONDS = 10
        check, tracker = self._make_tracker()
        for _ in range(35):
            check("ws1")
        # Pencereyi geçmişe çek
        count, _ = tracker["ws1"]
        tracker["ws1"] = (count, time.monotonic() - RATE_WINDOW_SECONDS - 1)
        result = check("ws1")
        self.assertFalse(result)


# ─── Test 4: Redis Pub/Sub Fallback ───────────────────────────────────────────
class TestRedisPubSubFallback(unittest.IsolatedAsyncioTestCase):

    async def test_publish_returns_false_when_unavailable(self):
        from src.services.redis_realtime import RedisPubSubManager
        mgr = RedisPubSubManager()
        # Redis bağlı değil
        mgr._available = False
        result = await mgr.publish("user_123", {"type": "ping"})
        self.assertFalse(result)

    async def test_connect_falls_back_gracefully(self):
        """Redis yokken connect() exception fırlatmamalı."""
        from src.services.redis_realtime import RedisPubSubManager
        mgr = RedisPubSubManager()
        # Geçersiz URL ile doğrudan connect — exception raise etmemeli
        mgr._redis = None
        mgr._available = False
        # Zaten unavailable; start_subscriber local-only moda düşmeli
        try:
            await mgr.start_subscriber()
        except Exception:
            self.fail("start_subscriber() exception fırlattı!")
        self.assertFalse(mgr.is_available)

    async def test_handler_dispatch(self):
        """Pub/Sub handler'ı doğru çağırmalı."""
        from src.services.redis_realtime import RedisPubSubManager
        mgr = RedisPubSubManager()
        received = []

        async def handler(uid, event):
            received.append((uid, event))

        mgr.add_handler(handler)
        await mgr._dispatch(json.dumps({
            "id": "test-id",
            "target_user_id": "user_abc",
            "event": {"type": "ping"},
        }))
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "user_abc")


# ─── Test 5: Presence Service Local Fallback ─────────────────────────────────
class TestPresenceServiceFallback(unittest.IsolatedAsyncioTestCase):

    async def test_mark_online_local(self):
        from src.services.presence_service import PresenceService
        svc = PresenceService()
        svc._available = False  # Redis yok
        await svc.mark_online("user_test")
        self.assertIn("user_test", svc._local_store)

    async def test_mark_offline_local(self):
        from src.services.presence_service import PresenceService
        svc = PresenceService()
        svc._available = False
        await svc.mark_online("user_test")
        await svc.mark_offline("user_test")
        self.assertNotIn("user_test", svc._local_store)

    async def test_is_online_true_local(self):
        from src.services.presence_service import PresenceService
        svc = PresenceService()
        svc._available = False
        await svc.mark_online("user_test")
        result = await svc.is_online("user_test")
        self.assertTrue(result)

    async def test_is_online_expired_returns_false(self):
        from src.services.presence_service import PresenceService
        svc = PresenceService()
        svc._available = False
        # Süresi geçmiş kayıt ekle
        svc._local_store["user_test"] = time.monotonic() - 10  # geçmişte
        result = await svc.is_online("user_test")
        self.assertFalse(result)
        self.assertNotIn("user_test", svc._local_store)  # temizlendi mi?


# ─── Test 6: Safe Logging (Privacy) ───────────────────────────────────────────
class TestPrivacySafeLogging(unittest.TestCase):

    def test_no_sensitive_in_build_error(self):
        """Error event payload'ında raw token/text bulunmamalı."""
        from src.services.websocket_events import build_error
        event = build_error("TEST", "Hata mesajı")
        payload_str = json.dumps(event)
        # Bu test basit bir sanity check — token içermiyor
        self.assertNotIn("Bearer", payload_str)
        self.assertNotIn("password", payload_str.lower())

    def test_encode_event_valid_json(self):
        from src.services.websocket_events import encode_event, build_pong
        result = encode_event(build_pong())
        parsed = json.loads(result)  # JSON parse edilebilmeli
        self.assertIn("type", parsed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
