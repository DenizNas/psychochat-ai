import time
import threading
from typing import Dict
from src.core.security_config import security_config

class TokenBlacklist:
    """
    In-memory, thread-safe mantığında çalışan JWT Token Blacklist (Revocation) katmanı.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Yapı: { "token_string": expires_at_timestamp }
        self.store: Dict[str, float] = {}

    def add(self, token: str, expires_at: float = None):
        """Token'ı kara listeye ekler."""
        if not security_config.TOKEN_BLACKLIST_ENABLED:
            return
            
        if expires_at is None:

            # Token'ın geçerlilik süresi (exp) okunamıyorsa bile varsayılan 7 gün kara lisede tut
            expires_at = time.time() + (7 * 24 * 60 * 60)
            
        with self._lock:
            self.store[token] = float(expires_at)
            
        # Her yeni blacklist olayında süresi zaten (naturally) dolmuş geçmişleri temizler (Memory leak önler)
        self._cleanup()

    def is_blacklisted(self, token: str) -> bool:
        """Token'ın listede engelli olup olmadığını denetler (O(1) Karmaşıklık)"""
        with self._lock:
            if token in self.store:
                if time.time() > self.store[token]:
                    # Kara listeye eklenmiş ama aslında Token'ın ömrü de (exp) zaten yasal olarak bitmiş
                    # Bu noktada memory tasarrufu için engellenenler listesinden kaldır. (Artık geçersiz bir token)
                    del self.store[token]
                    return False
                return True
        return False

    def _cleanup(self):
        """TTL kontrolü yaparak gereksiz (doğal expired olan) tokenleri Memory'den siler"""
        current_time = time.time()
        expired_tokens = [k for k, v in self.store.items() if current_time > v]
        for k in expired_tokens:
            del self.store[k]

# Global singleton
token_blacklist_core = TokenBlacklist()
