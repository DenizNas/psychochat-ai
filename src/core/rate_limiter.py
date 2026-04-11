import time
import threading
from src.core.security_config import security_config

class RateLimiter:
    """
    In-memory, thread-safe IP-based Rate Limiter.
    Hız limitlerini security_config.py üzerinden merkezi olarak yönetir.
    """
    def __init__(self):
        self._lock = threading.Lock()
        
        # Kural Seti: path -> (Max_istek, Saniye_penceresi)
        self.rules = {
            "/login": security_config.get_rate_limit_tuple("/login"),      
            "/predict": security_config.get_rate_limit_tuple("/predict"),   
            "default": security_config.get_rate_limit_tuple("default")    
        }

        
        # Hız kontrol kütüğü: { "ip": { "path": {"count": 1, "window_start": 169...} } }
        self.store = {}

    def is_allowed(self, ip: str, path: str) -> bool:
        rule = self.rules.get(path, self.rules["default"])
        max_requests, window_seconds = rule
        current_time = time.time()
        
        with self._lock:
            if ip not in self.store:
                self.store[ip] = {}
                
            if path not in self.store[ip]:
                self.store[ip][path] = {"count": 1, "window_start": current_time}
                return True
                
            record = self.store[ip][path]
            
            # Zaman aralığı dolduysa (örn. 60 sn) sayacı sıfırla
            if current_time - record["window_start"] >= window_seconds:
                record["count"] = 1
                record["window_start"] = current_time
                return True
                
            # Hala zaman aralığı içindeyse limiter asıl kontrolü
            if record["count"] < max_requests:
                record["count"] += 1
                return True
            
            # Kota aşıldı
            return False

# Global Limiter objesi
rate_limiter_core = RateLimiter()
