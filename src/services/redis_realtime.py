"""
Redis Pub/Sub Real-Time Event Synchronizer
==========================================
Birden fazla backend instance arasında WebSocket event'lerini
Redis Pub/Sub üzerinden senkronize eder.

Güvenlik & Dayanıklılık:
- Redis unavailable → local-only mode (crash yok)
- Channel adı sabittir: psychochat_realtime_events
- Loglarda token / raw metin YOKTUR
- Her event UUID ile izlenebilir
"""

import asyncio
import json
import logging
import uuid
from typing import Callable, Optional

logger = logging.getLogger(__name__)

PUBSUB_CHANNEL = "psychochat_realtime_events"


class RedisPubSubManager:
    """
    Redis Pub/Sub üzerinden real-time event dağıtımı.

    Örnek kullanım:
        manager = RedisPubSubManager()
        await manager.connect()
        await manager.publish("user_abc123", {"type": "chat_response", ...})
        await manager.subscribe(callback)
    """

    def __init__(self) -> None:
        self._redis: Optional[object] = None
        self._pubsub: Optional[object] = None
        self._subscriber_task: Optional[asyncio.Task] = None
        self._handlers: list[Callable] = []
        self._available: bool = False

    # ─── Lifecycle ────────────────────────────────────────────────────────────
    async def connect(self) -> None:
        """Redis bağlantısını kur. Başarısız olursa local-only moda düş."""
        try:
            import redis.asyncio as aioredis
            from src.core.config import settings

            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            # Bağlantıyı test et
            await self._redis.ping()
            self._available = True
            logger.info("Redis Pub/Sub bağlantısı kuruldu. Kanal: %s", PUBSUB_CHANNEL)
        except Exception as exc:
            # Token/URL log'a yazılmaz; sadece hata tipi
            logger.warning(
                "Redis Pub/Sub bağlantısı kurulamadı (%s). Local-only moda geçildi.",
                type(exc).__name__,
            )
            self._available = False

    async def start_subscriber(self) -> None:
        """Arka planda mesaj dinleme task'ını başlat (sadece Redis mevcutsa)."""
        if not self._available:
            logger.info("Redis unavailable — subscriber başlatılmadı.")
            return
        try:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(PUBSUB_CHANNEL)
            self._subscriber_task = asyncio.create_task(self._listen_loop())
            logger.info("Redis Pub/Sub subscriber başlatıldı.")
        except Exception as exc:
            logger.warning("Subscriber başlatma hatası (%s). Local-only moda geçildi.", type(exc).__name__)
            self._available = False

    async def disconnect(self) -> None:
        """Temiz kapatma."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe(PUBSUB_CHANNEL)
                await self._pubsub.close()
            except Exception:
                pass
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
        self._available = False
        logger.info("Redis Pub/Sub bağlantısı kapatıldı.")

    # ─── Publish ──────────────────────────────────────────────────────────────
    async def publish(self, target_user_id: str, event: dict) -> bool:
        """
        Bir event'i Redis kanalına publish et.
        Döner: True (gönderildi) / False (local-only, skip)

        NOT: target_user_id veya event içeriği (raw metin) loglanmaz.
        """
        if not self._available or not self._redis:
            return False  # local-only; çağıran local dağıtımı yapacak

        envelope = {
            "id": str(uuid.uuid4()),
            "target_user_id": target_user_id,
            "event": event,
        }
        try:
            await self._redis.publish(PUBSUB_CHANNEL, json.dumps(envelope, ensure_ascii=False))
            return True
        except Exception as exc:
            logger.warning("Redis publish hatası (%s). Local delivery devrede.", type(exc).__name__)
            self._available = False
            return False

    # ─── Subscribe ────────────────────────────────────────────────────────────
    def add_handler(self, handler: Callable) -> None:
        """
        Pub/Sub'dan gelen mesajları işleyecek callback ekle.
        handler(target_user_id: str, event: dict) → Awaitable
        """
        self._handlers.append(handler)

    async def _listen_loop(self) -> None:
        """Redis mesajlarını dinle; her mesajda handler'ları çağır."""
        while True:
            try:
                msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    await self._dispatch(msg["data"])
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Redis Pub/Sub listen hatası (%s). Yeniden bağlanılıyor...", type(exc).__name__)
                await asyncio.sleep(2)
                await self._reconnect()

    async def _dispatch(self, raw: str) -> None:
        try:
            envelope = json.loads(raw)
            target_user_id = envelope.get("target_user_id", "")
            event = envelope.get("event", {})
        except (json.JSONDecodeError, KeyError):
            logger.debug("Pub/Sub'dan parse edilemeyen mesaj alındı.")
            return

        for handler in self._handlers:
            try:
                await handler(target_user_id, event)
            except Exception as exc:
                logger.error("Pub/Sub handler hatası: %s", type(exc).__name__)

    async def _reconnect(self) -> None:
        """Bağlantı kopunca yeniden bağlanmayı dene."""
        try:
            await self._pubsub.close()
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(PUBSUB_CHANNEL)
            logger.info("Redis Pub/Sub yeniden bağlandı.")
        except Exception as exc:
            logger.warning("Redis Pub/Sub reconnect başarısız (%s). Local-only devam.", type(exc).__name__)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available


# Singleton instance — startup'ta başlatılır
pubsub_manager = RedisPubSubManager()
