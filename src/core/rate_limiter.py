import time
import logging
import threading
from src.core.config import settings
from src.core.redis_client import redis_client

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Production-grade, Redis-backed Rate Limiter with a thread-safe local in-memory fallback.
    Supports strict rule configurations and dynamic key identification (IP or username).
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Local fallback store: { (limit_type, key): {"count": int, "window_start": float} }
        self.in_memory_store = {}

    def _parse_rate_limit(self, limit_str: str) -> tuple[int, int]:
        """
        Parses a rate limit string (e.g., '5/minute', '30/minute') into a (max_requests, window_seconds) tuple.
        """
        try:
            count, period = limit_str.split("/")
            count = int(count)
            seconds = 60
            if "minute" in period:
                seconds = 60
            elif "hour" in period:
                seconds = 3600
            elif "second" in period:
                seconds = 1
            elif "day" in period:
                seconds = 86400
            return count, seconds
        except Exception:
            return 100, 60  # Safe default fallback limit

    def get_rules(self) -> dict[str, tuple[int, int]]:
        """Dynamically loads limit rules based on settings."""
        return {
            "login": self._parse_rate_limit(settings.LOGIN_RATE_LIMIT),
            "register": self._parse_rate_limit(settings.REGISTER_RATE_LIMIT),
            "predict": self._parse_rate_limit(settings.PREDICT_RATE_LIMIT),
            "journal": (30, 60),  # 30 per minute as specified
            "analytics": self._parse_rate_limit(settings.ANALYTICS_RATE_LIMIT),
            "default": (100, 60)
        }

    def is_allowed(self, key: str, limit_type: str) -> bool:
        """
        Determines if the request under the specified key (IP or user ID) is allowed.
        Fails open/safely by returning True in case of settings bypass.
        """
        if not settings.RATE_LIMIT_ENABLED:
            return True

        rules = self.get_rules()
        rule = rules.get(limit_type, rules["default"])
        max_requests, window_seconds = rule

        # 1. Attempt Redis Atomic Counter Rate Limiting
        try:
            r = redis_client.client
            if r:
                redis_key = f"rate_limit:{limit_type}:{key}"
                
                # Retrieve current counter in one trip
                current = r.get(redis_key)
                if current and int(current) >= max_requests:
                    return False
                
                # Increment atomic counter and fetch TTL
                pipe = r.pipeline()
                pipe.incr(redis_key)
                pipe.ttl(redis_key)
                res = pipe.execute()
                new_val, ttl = res[0], res[1]
                
                # If key was just created (no TTL / TTL is -1), set the expiration
                if ttl == -1:
                    r.expire(redis_key, window_seconds)
                
                return new_val <= max_requests
        except Exception as e:
            logger.warning(
                f"RATE_LIMITER | Redis offline. Falling back to thread-safe local in-memory store. Details: {e}"
            )

        # 2. In-Memory Thread-Safe Fallback
        with self._lock:
            current_time = time.time()
            record_key = (limit_type, key)
            record = self.in_memory_store.get(record_key)

            # If new window or first request, initialize
            if not record or (current_time - record["window_start"] >= window_seconds):
                self.in_memory_store[record_key] = {"count": 1, "window_start": current_time}
                return True

            # If quota exceeded
            if record["count"] >= max_requests:
                return False

            # Increment count
            record["count"] += 1
            return True

# Global Limiter Core instance
rate_limiter_core = RateLimiter()
