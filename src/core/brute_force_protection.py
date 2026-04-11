import time
import threading
from src.core.security_config import security_config

class BruteForceProtection:
    """
    In-memory dict tabanlı thread-safe Login Brute-force Koruması.
    Değerleri security_config.py üzerinden merkezi olarak alır.
    """
    def __init__(self, max_failures: int = None, lock_duration_sec: int = None):
        self.max_failures = max_failures or security_config.BRUTE_FORCE_MAX_ATTEMPTS
        self.lock_duration_sec = lock_duration_sec or security_config.BRUTE_FORCE_BLOCK_TIME
        self._lock = threading.Lock()
        
        # IP tabanlı kayıt tutar: { ip: {"failures": int, "locked_until": float/None} }
        self.store = {}


    def is_blocked(self, ip: str) -> bool:
        current_time = time.time()
        with self._lock:
            record = self.store.get(ip)
            if not record:
                return False
                
            if record["locked_until"]:
                if current_time < record["locked_until"]:
                    return True
                else:
                    # Kilit süresi tamamen dolmuşsa sayacı güvenli alana çek
                    self.store[ip] = {"failures": 0, "locked_until": None}
                    return False
            
            return record["failures"] >= self.max_failures

    def register_failure(self, ip: str) -> bool:
        """Başarısız girişleri toplar. True dönerse IP artık bloke olmuş demektir."""
        current_time = time.time()
        with self._lock:
            if ip not in self.store:
                self.store[ip] = {"failures": 0, "locked_until": None}
            
            record = self.store[ip]
            
            # Halihazırda blokluysa zaman süresi yenilenmez ama counter arttırılmaz
            if record["locked_until"] and current_time < record["locked_until"]:
                return True 

            record["failures"] += 1
            if record["failures"] >= self.max_failures:
                record["locked_until"] = current_time + self.lock_duration_sec
                return True
            
            return False

    def register_success(self, ip: str) -> bool:
        """Doğru giriş yapıldığında listeyi temizler, True dönerse önceden bir şüphe listesinden çıkmış demektir."""
        with self._lock:
            if ip in self.store and self.store[ip]["failures"] > 0:
                self.store[ip] = {"failures": 0, "locked_until": None}
                return True
        return False

# Tekli Global Obje
brute_force_protector = BruteForceProtection()
