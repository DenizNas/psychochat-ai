import logging
import redis
from src.core.config import settings
from src.core.metrics import REDIS_FALLBACK_TOTAL

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self._client = None
        self.url = settings.REDIS_URL

    @property
    def client(self):
        """
        Dynamically initializes and returns the Redis client instance.
        If connection cannot be established, returns None to execute graceful fallback.
        """
        if self._client is None:
            try:
                # Use from_url to parse connection protocols, database indices, and optional passwords safely
                self._client = redis.Redis.from_url(
                    self.url,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                    decode_responses=True
                )
                # Test connection immediately via Ping
                self._client.ping()
                logger.info("REDIS_CLIENT | Connected successfully to Redis database.")
            except Exception as e:
                logger.warning(
                    f"REDIS_CLIENT | Redis connection failed at URL {self.url}. "
                    f"Falling back to direct database retrieval. Details: {e}"
                )
                try:
                    REDIS_FALLBACK_TOTAL.labels(operation="connect").inc()
                except Exception:
                    pass
                self._client = None
        return self._client

    def ping(self) -> bool:
        """Utility to ping Redis to determine runtime health."""
        try:
            c = self.client
            if c:
                return bool(c.ping())
        except Exception:
            try:
                REDIS_FALLBACK_TOTAL.labels(operation="ping").inc()
            except Exception:
                pass
        return False

    def get(self, key: str) -> str:
        """Gets value from Redis with connection failure safety."""
        try:
            c = self.client
            if c:
                return c.get(key)
            else:
                try:
                    REDIS_FALLBACK_TOTAL.labels(operation="get").inc()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"REDIS_CLIENT | Get failed for key {key}. Details: {e}")
            try:
                REDIS_FALLBACK_TOTAL.labels(operation="get").inc()
            except Exception:
                pass
        return None

    def set(self, key: str, value: str, ex: int = None) -> bool:
        """Sets value in Redis with connection failure safety."""
        try:
            c = self.client
            if c:
                c.set(key, value, ex=ex)
                return True
            else:
                try:
                    REDIS_FALLBACK_TOTAL.labels(operation="set").inc()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"REDIS_CLIENT | Set failed for key {key}. Details: {e}")
            try:
                REDIS_FALLBACK_TOTAL.labels(operation="set").inc()
            except Exception:
                pass
        return False

    def delete(self, *keys) -> int:
        """Deletes one or more keys from Redis with connection failure safety."""
        try:
            c = self.client
            if c and keys:
                return c.delete(*keys)
            elif not c:
                try:
                    REDIS_FALLBACK_TOTAL.labels(operation="delete").inc()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"REDIS_CLIENT | Delete failed for keys {keys}. Details: {e}")
            try:
                REDIS_FALLBACK_TOTAL.labels(operation="delete").inc()
            except Exception:
                pass
        return 0

    def delete_pattern(self, pattern: str) -> int:
        """Deletes all keys matching a glob pattern from Redis with connection failure safety."""
        try:
            c = self.client
            if c:
                keys = c.keys(pattern)
                if keys:
                    return c.delete(*keys)
            else:
                try:
                    REDIS_FALLBACK_TOTAL.labels(operation="delete_pattern").inc()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"REDIS_CLIENT | Delete pattern {pattern} failed. Details: {e}")
            try:
                REDIS_FALLBACK_TOTAL.labels(operation="delete_pattern").inc()
            except Exception:
                pass
        return 0

# Global single instance
redis_client = RedisClient()
