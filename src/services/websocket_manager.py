"""
WebSocket Connection Manager
==============================
WebSocket bağlantı yaşam döngüsünü yönetir:
- Bağlantı ekle/kaldır
- Kullanıcıya mesaj gönder
- Rate limiting (anti-spam)
- Redis Pub/Sub ile çoklu instance desteği
- Tüm loglama privacy-safe (token/metin loglanmaz)

Rate Limit: MAX_EVENTS_PER_WINDOW mesaj / RATE_WINDOW_SECONDS pencere
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from src.services.websocket_events import (
    WsEventType,
    EventValidationError,
    MAX_PAYLOAD_BYTES,
    build_error,
    build_pong,
    build_connected,
    build_typing_indicator,
    encode_event,
    parse_inbound_event,
)
from src.services.presence_service import presence_service
from src.services.redis_realtime import pubsub_manager
from src.core.metrics import (
    WEBSOCKET_ACTIVE_CONNECTIONS,
    WEBSOCKET_RECONNECTS_TOTAL,
    WEBSOCKET_DISCONNECTS_TOTAL
)

logger = logging.getLogger(__name__)

# ─── Rate Limiting Config ─────────────────────────────────────────────────────
MAX_EVENTS_PER_WINDOW = 30    # 30 event
RATE_WINDOW_SECONDS   = 10    # 10 saniyelik pencere

# ─── Typing Debounce ──────────────────────────────────────────────────────────
TYPING_DEBOUNCE_SECONDS = 2.0  # typing_stop gönderilmeden önce bekleme süresi


class ConnectionManager:
    """
    WebSocket bağlantı havuzu.

    • active_connections: user_id → WebSocket listesi (aynı user birden fazla bağlı olabilir)
    • rate_tracker: client rate limiting için event sayaçları
    """

    def __init__(self) -> None:
        # user_id → list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        # WebSocket → (event_count, window_start_ts)
        self._rate_tracker: dict[int, tuple[int, float]] = {}
        # user_id → asyncio.TimerHandle for typing debounce
        self._typing_timers: dict[str, Optional[asyncio.TimerHandle]] = {}

    # ─── Connection Lifecycle ─────────────────────────────────────────────────
    async def connect(self, ws: WebSocket, user_id: str) -> None:
        """Yeni bağlantıyı kabul et ve presence'ı güncelle."""
        await ws.accept()
        # Eğer bu kullanıcının zaten aktif bir bağlantısı varsa reconnect say
        if user_id in self._connections and len(self._connections[user_id]) > 0:
            WEBSOCKET_RECONNECTS_TOTAL.inc()

        self._connections[user_id].append(ws)
        self._rate_tracker[id(ws)] = (0, time.monotonic())
        await presence_service.mark_online(user_id)
        WEBSOCKET_ACTIVE_CONNECTIONS.inc()
        logger.info("WS bağlantı kuruldu. user_id=[masked] total_connections=%d",
                    sum(len(v) for v in self._connections.values()))
        # connected event gönder
        await self._send_to_ws(ws, build_connected(user_id))

    async def disconnect(self, ws: WebSocket, user_id: str, reason: str = "client_close") -> None:
        """Bağlantıyı havuzdan çıkar; presence'ı güncelle."""
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
            WEBSOCKET_ACTIVE_CONNECTIONS.dec()
            WEBSOCKET_DISCONNECTS_TOTAL.labels(reason=reason).inc()
        if not conns:
            self._connections.pop(user_id, None)
            await presence_service.mark_offline(user_id)
        self._rate_tracker.pop(id(ws), None)
        self._cancel_typing_timer(user_id)
        logger.info("WS bağlantı kapatıldı. Remaining_users=%d reason=%s", len(self._connections), reason)

    # ─── Send Helpers ─────────────────────────────────────────────────────────
    async def send_to_user(self, user_id: str, event: dict) -> None:
        """
        Kullanıcıya ait tüm bağlantılara event gönder.
        Önce local bağlantıları dene; Redis Pub/Sub varsa diğer instance'lara ilet.
        """
        await self._local_broadcast(user_id, event)
        # Diğer instance'lara ilet (Redis mevcutsa)
        await pubsub_manager.publish(user_id, event)

    async def _local_broadcast(self, user_id: str, event: dict) -> None:
        """Sadece bu instance'daki bağlantılara gönder."""
        conns = list(self._connections.get(user_id, []))
        dead: list[WebSocket] = []
        payload = encode_event(event)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws, user_id, reason="broken_pipe")

    async def broadcast_from_pubsub(self, target_user_id: str, event: dict) -> None:
        """Redis Pub/Sub'dan gelen event'leri local bağlantılara ilet."""
        await self._local_broadcast(target_user_id, event)

    @staticmethod
    async def _send_to_ws(ws: WebSocket, event: dict) -> None:
        """Tek bir WebSocket'e event gönder."""
        try:
            await ws.send_text(encode_event(event))
        except Exception:
            pass  # Bağlantı zaten kapanmış

    # ─── Rate Limiting ────────────────────────────────────────────────────────
    def check_rate_limit(self, ws: WebSocket) -> bool:
        """
        True  → rate limit aşıldı, bağlantı kapatılmalı
        False → izin verildi
        """
        ws_id = id(ws)
        count, window_start = self._rate_tracker.get(ws_id, (0, time.monotonic()))
        now = time.monotonic()

        if now - window_start > RATE_WINDOW_SECONDS:
            # Pencere sıfırla
            self._rate_tracker[ws_id] = (1, now)
            return False

        count += 1
        self._rate_tracker[ws_id] = (count, window_start)

        if count > MAX_EVENTS_PER_WINDOW:
            logger.warning("WS rate limit aşıldı. Bağlantı kapatılıyor.")
            return True
        return False

    # ─── Typing Debounce ─────────────────────────────────────────────────────
    async def handle_typing_start(self, user_id: str) -> None:
        """Typing start — raw mesaj taşımaz; sadece indicator yayınla."""
        self._cancel_typing_timer(user_id)
        # Assistant typing indicator (bot cevap verirken de kullanılır)
        # Burada user typing → başka kullanıcılara bildiri (gerekirse)
        # Şimdilik sadece debounce timer'ı kur
        loop = asyncio.get_event_loop()
        self._typing_timers[user_id] = loop.call_later(
            TYPING_DEBOUNCE_SECONDS,
            asyncio.ensure_future,
            self._typing_stop_after_debounce(user_id),
        )
        await presence_service.refresh(user_id)

    async def handle_typing_stop(self, user_id: str) -> None:
        """Explicit typing stop."""
        self._cancel_typing_timer(user_id)

    async def _typing_stop_after_debounce(self, user_id: str) -> None:
        """Debounce süresi dolunca typing stop event gönder."""
        self._typing_timers.pop(user_id, None)

    def _cancel_typing_timer(self, user_id: str) -> None:
        timer = self._typing_timers.pop(user_id, None)
        if timer:
            timer.cancel()

    # ─── Payload Size Guard ───────────────────────────────────────────────────
    @staticmethod
    def check_payload_size(raw: str) -> bool:
        """True → limit aşıldı (64KB)."""
        return len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES

    # ─── Stats ────────────────────────────────────────────────────────────────
    @property
    def total_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())

    @property
    def connected_users(self) -> int:
        return len(self._connections)


# Singleton instance
connection_manager = ConnectionManager()


# ─── Pub/Sub Handler Bootstrap ────────────────────────────────────────────────
def register_pubsub_handler() -> None:
    """
    startup sırasında çağrılır.
    Redis'ten gelen event'leri local bağlantılara iletir.
    """
    pubsub_manager.add_handler(connection_manager.broadcast_from_pubsub)
