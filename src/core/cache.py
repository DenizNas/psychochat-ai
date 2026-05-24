import json
import logging
from typing import Any, Optional
from src.core.redis_client import redis_client

logger = logging.getLogger(__name__)

# TTL (Time-To-Live) configurations in seconds
TTL_DASHBOARD = 600      # 10 Minutes
TTL_SUMMARY = 900        # 15 Minutes
TTL_REPORTS = 1800       # 30 Minutes

def get_cache_key(username: str, cache_type: str, *args) -> str:
    """
    Constructs a uniform, fully-isolated, privacy-safe cache key namespace.
    Format: cache:{username}:{cache_type}:{suffix}
    """
    suffix = ":".join(str(a) for a in args)
    return f"cache:{username}:{cache_type}:{suffix}"

from src.core.metrics import CACHE_HIT_TOTAL, CACHE_MISS_TOTAL

def cache_get(username: str, cache_type: str, *args) -> Optional[Any]:
    """
    Retrieves data from the cache.
    Automatically returns None (acting as a cache-miss) if any serialization or connection error occurs.
    """
    key = get_cache_key(username, cache_type, *args)
    data = redis_client.get(key)
    if data:
        try:
            val = json.loads(data)
            try:
                CACHE_HIT_TOTAL.labels(cache_type=cache_type).inc()
            except Exception:
                pass
            return val
        except Exception as e:
            logger.error(f"CACHE_SYSTEM | Failed to deserialize cached JSON for key {key}. Details: {e}")
            try:
                CACHE_MISS_TOTAL.labels(cache_type=cache_type).inc()
            except Exception:
                pass
            return None
    try:
        CACHE_MISS_TOTAL.labels(cache_type=cache_type).inc()
    except Exception:
        pass
    return None

def cache_set(username: str, cache_type: str, data: Any, ttl: int, *args) -> bool:
    """
    Saves serializable data in the cache with the given TTL.
    """
    key = get_cache_key(username, cache_type, *args)
    try:
        serialized = json.dumps(data)
        success = redis_client.set(key, serialized, ex=ttl)
        if success:
            logger.info(f"CACHE_SYSTEM | Cache populated for key: {key} (TTL: {ttl}s)")
        return bool(success)
    except Exception as e:
        logger.error(f"CACHE_SYSTEM | Failed to serialize/store data for key {key}. Details: {e}")
        return False

def invalidate_user_caches(username: str) -> int:
    """
    Flushes all cache namespaces matching the user to guarantee immediate data consistency.
    Fires on: new chat predictions, new mood journals, mark notification delivered, and profile setting changes.
    """
    pattern = f"cache:{username}:*"
    try:
        deleted = redis_client.delete_pattern(pattern)
        if deleted > 0:
            logger.info(f"CACHE_INVALIDATION | UserID: {username} | Evicted {deleted} cache keys due to data mutation.")
        return deleted
    except Exception as e:
        logger.warning(f"CACHE_INVALIDATION | Error during invalidation pattern {pattern}. Details: {e}")
        return 0
