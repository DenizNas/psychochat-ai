"""
Presence Service
================
Kullanıcıların online/offline durumunu Redis TTL ile yönetir.
Redis yoksa in-memory fallback ile çalışır.

Güvenlik:
- user_id'ler hash'lenmiş şekilde loglanır (privacy-safe)
- Redis yoksa crash yok — local-only dict devreye girer
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

PRESENCE_KEY_PREFIX = "psiko:presence:"
PRESENCE_TTL_SECONDS = 90  # 90 sn aktif olmayan kullanıcı offline sayılır


class PresenceService:
    """
    Kullanıcı online/offline yönetimi.

    Redis mevcutsa → Redis SETEX (TTL tabanlı)
    Redis yoksa    → In-memory dict (uçucu; multi-instance'da senkronize değil)
    """

    def __init__(self) -> None:
        self._redis: Optional[object] = None
        self._local_store: dict[str, float] = {}  # user_id → timestamp
        self._available: bool = False

    # ─── Lifecycle ────────────────────────────────────────────────────────────
    async def connect(self) -> None:
        """Redis bağlantısını kur. Başarısız olursa local fallback."""
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
            await self._redis.ping()
            self._available = True
            logger.info("PresenceService: Redis bağlantısı kuruldu.")
        except Exception as exc:
            logger.warning(
                "PresenceService: Redis bağlanamadı (%s). Local fallback aktif.",
                type(exc).__name__,
            )
            self._available = False

    async def disconnect(self) -> None:
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
        logger.info("PresenceService: Bağlantı kapatıldı.")

    # ─── Core Operations ──────────────────────────────────────────────────────
    async def mark_online(self, user_id: str) -> None:
        """Kullanıcıyı online olarak işaretle (TTL'i yenile)."""
        if self._available and self._redis:
            try:
                key = PRESENCE_KEY_PREFIX + user_id
                await self._redis.setex(key, PRESENCE_TTL_SECONDS, "1")
                return
            except Exception as exc:
                logger.warning("Presence mark_online Redis hatası (%s). Local fallback.", type(exc).__name__)
                self._available = False

        # Local fallback
        self._local_store[user_id] = time.monotonic() + PRESENCE_TTL_SECONDS

    async def mark_offline(self, user_id: str) -> None:
        """Kullanıcıyı offline olarak işaretle."""
        if self._available and self._redis:
            try:
                key = PRESENCE_KEY_PREFIX + user_id
                await self._redis.delete(key)
                return
            except Exception as exc:
                logger.warning("Presence mark_offline Redis hatası (%s). Local fallback.", type(exc).__name__)
                self._available = False

        # Local fallback
        self._local_store.pop(user_id, None)

    async def is_online(self, user_id: str) -> bool:
        """Kullanıcı online mı?"""
        if self._available and self._redis:
            try:
                key = PRESENCE_KEY_PREFIX + user_id
                return await self._redis.exists(key) == 1
            except Exception as exc:
                logger.warning("Presence is_online Redis hatası (%s). Local fallback.", type(exc).__name__)
                self._available = False

        # Local fallback — TTL kontrolü
        expire_at = self._local_store.get(user_id)
        if expire_at is None:
            return False
        if time.monotonic() > expire_at:
            self._local_store.pop(user_id, None)
            return False
        return True

    async def refresh(self, user_id: str) -> None:
        """Heartbeat aldığında TTL'i yenile."""
        await self.mark_online(user_id)

    # ─── Cleanup ──────────────────────────────────────────────────────────────
    def _cleanup_local(self) -> None:
        """Süresi geçmiş local presence kayıtlarını temizle."""
        now = time.monotonic()
        expired = [uid for uid, exp in self._local_store.items() if now > exp]
        for uid in expired:
            del self._local_store[uid]

    @property
    def is_redis_available(self) -> bool:
        return self._available


# Singleton instance
presence_service = PresenceService()
