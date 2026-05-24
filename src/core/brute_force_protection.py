import time
import logging
import threading
from src.core.redis_client import redis_client

logger = logging.getLogger(__name__)

class BruteForceProtection:
    """
    Highly-hardened IP + Username combined Login Brute-force protection.
    Attempts and lockout states are stored in Redis, falling back gracefully
    to a thread-safe local in-memory store if Redis is down.
    
    Policy: 5 failed attempts -> 10 minutes (600 seconds) lockout.
    """
    def __init__(self, max_failures: int = 5, lock_duration_sec: int = 600):
        self.max_failures = max_failures
        self.lock_duration_sec = lock_duration_sec
        self._lock = threading.Lock()
        
        # Local fallback store: { (ip, username): {"failures": int, "locked_until": float/None} }
        self.in_memory_store = {}

    def get_keys(self, ip: str, username: str) -> tuple[str, str]:
        """Utility to get unified Redis key strings."""
        attempts_key = f"brute_force:attempts:{ip}:{username}"
        lockout_key = f"brute_force:lockout:{ip}:{username}"
        return attempts_key, lockout_key

    def is_blocked(self, ip: str, username: str) -> bool:
        """Checks if the combined IP + Username auth path is locked out."""
        # 1. Check using Redis
        try:
            r = redis_client.client
            if r:
                _, lockout_key = self.get_keys(ip, username)
                locked_until_str = r.get(lockout_key)
                if locked_until_str:
                    locked_until = float(locked_until_str)
                    if time.time() < locked_until:
                        return True
                    else:
                        # Lock expired, safely delete the lockout key and clear attempts
                        r.delete(lockout_key)
                        attempts_key, _ = self.get_keys(ip, username)
                        r.delete(attempts_key)
                return False
        except Exception as e:
            logger.warning(
                f"BRUTE_FORCE | Redis offline during check. Falling back to local in-memory lockout. Details: {e}"
            )

        # 2. Local fallback check
        current_time = time.time()
        with self._lock:
            record_key = (ip, username)
            record = self.in_memory_store.get(record_key)
            if not record:
                return False
            if record["locked_until"]:
                if current_time < record["locked_until"]:
                    return True
                else:
                    # Lock expired, reset
                    self.in_memory_store[record_key] = {"failures": 0, "locked_until": None}
                    return False
            return record["failures"] >= self.max_failures

    def register_failure(self, ip: str, username: str) -> bool:
        """Registers a failed authentication attempt. Returns True if combination is now locked."""
        # 1. Register failure in Redis
        try:
            r = redis_client.client
            if r:
                attempts_key, lockout_key = self.get_keys(ip, username)
                
                # Increment attempts (and keep expire of 24h to avoid orphan keys)
                attempts = r.incr(attempts_key)
                if attempts == 1:
                    r.expire(attempts_key, 86400) # 24h window
                
                if attempts >= self.max_failures:
                    locked_until = time.time() + self.lock_duration_sec
                    r.set(lockout_key, str(locked_until), ex=self.lock_duration_sec)
                    logger.warning(f"SECURITY_AUDIT | Auth Lockout active | IP: {ip} | User: {username} | Duration: 10 mins")
                    return True
                return False
        except Exception as e:
            logger.warning(
                f"BRUTE_FORCE | Redis offline during register failure. Falling back to in-memory store. Details: {e}"
            )

        # 2. Local fallback registration
        current_time = time.time()
        with self._lock:
            record_key = (ip, username)
            if record_key not in self.in_memory_store:
                self.in_memory_store[record_key] = {"failures": 0, "locked_until": None}
            
            record = self.in_memory_store[record_key]
            
            # If already locked, ignore subsequent attempts
            if record["locked_until"] and current_time < record["locked_until"]:
                return True

            record["failures"] += 1
            if record["failures"] >= self.max_failures:
                record["locked_until"] = current_time + self.lock_duration_sec
                logger.warning(f"SECURITY_AUDIT | Auth Lockout active (Local) | IP: {ip} | User: {username} | Duration: 10 mins")
                return True
            return False

    def register_success(self, ip: str, username: str) -> bool:
        """Registers a successful authentication, resetting lockout/attempts immediately."""
        # 1. Reset in Redis
        try:
            r = redis_client.client
            if r:
                attempts_key, lockout_key = self.get_keys(ip, username)
                deleted = r.delete(attempts_key, lockout_key)
                return deleted > 0
        except Exception as e:
            logger.warning(
                f"BRUTE_FORCE | Redis offline during register success. Falling back to in-memory store. Details: {e}"
            )

        # 2. Local fallback success reset
        with self._lock:
            record_key = (ip, username)
            if record_key in self.in_memory_store:
                self.in_memory_store.pop(record_key)
                return True
        return False

# Global single instance
brute_force_protector = BruteForceProtection()
