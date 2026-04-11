import os
from typing import Dict, Any

class SecurityConfig:
    """
    Tüm güvenlik ayarlarını merkezi hale getiren konfigürasyon sınıfı.
    Değerler Environment Variable üzerinden override edilebilir.
    """
    
    # --- RATE LIMITS ---
    RATE_LIMIT_LOGIN: str = os.getenv("SECURITY_RATE_LIMIT_LOGIN", "5/minute")
    RATE_LIMIT_PREDICT: str = os.getenv("SECURITY_RATE_LIMIT_PREDICT", "30/minute")
    RATE_LIMIT_DEFAULT: str = os.getenv("SECURITY_RATE_LIMIT_DEFAULT", "100/minute")

    # --- BRUTE FORCE PROTECTION ---
    BRUTE_FORCE_MAX_ATTEMPTS: int = int(os.getenv("SECURITY_BRUTE_FORCE_MAX_ATTEMPTS", 5))
    BRUTE_FORCE_BLOCK_TIME: int = int(os.getenv("SECURITY_BRUTE_FORCE_BLOCK_TIME", 900)) # 15 Dakika (Tuned)

    # --- INPUT VALIDATION ---
    INPUT_MAX_LENGTH: int = int(os.getenv("SECURITY_INPUT_MAX_LENGTH", 2500)) # Esnetildi (Tuned)

    
    # --- AI ABUSE / SPAM ---
    # Kaç mesajın tekrarını kontrol edeceğimiz (Şu anlık son 1 mesaj)
    SPAM_DUPLICATE_WINDOW: int = int(os.getenv("SECURITY_SPAM_DUPLICATE_WINDOW", 1))

    # --- JWT TOKEN ---
    TOKEN_BLACKLIST_ENABLED: bool = os.getenv("SECURITY_TOKEN_BLACKLIST_ENABLED", "true").lower() == "true"

    @classmethod
    def get_rate_limit_tuple(cls, path: str) -> tuple:
        """RateLimiter.py kural yapısına (limit, saniye) dönüştürür."""
        limit_str = cls.RATE_LIMIT_DEFAULT
        if path == "/login":
            limit_str = cls.RATE_LIMIT_LOGIN
        elif path == "/predict":
            limit_str = cls.RATE_LIMIT_PREDICT
        
        try:
            count, period = limit_str.split("/")
            seconds = 60
            if "minute" in period:
                seconds = 60
            elif "hour" in period:
                seconds = 3600
            elif "second" in period:
                seconds = 1
            return int(count), seconds
        except:
            return 10, 60 # Fail-safe default

# Global singleton
security_config = SecurityConfig()
