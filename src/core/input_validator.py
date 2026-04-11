import re
import logging
from typing import Optional, Dict
from src.core.security_config import security_config

logger = logging.getLogger(__name__)

class InputValidator:
    """
    Kötü niyetli injection (XSS/SQLi), command injection ve AI abuse (spam)
    girişimlerine karşı production seviyesinde bir koruma sağlar.
    """
    def __init__(self, max_length: int = None):
        self.max_length = max_length or security_config.INPUT_MAX_LENGTH

        
        # Basit bazlı koruma kalkanları (Regex kuralları)
        self.forbidden_patterns = [
            # 1. XSS (Cross-Site Scripting)
            r"<script.*?>", r"<\/script>",  # Script tags
            r"onerror\s*=", r"onload\s*=",   # Event handlers
            r"javascript:", r"<iframe>",     # JS URI and frames
            
            # 2. SQLi (SQL Injection)
            r"DROP\s+TABLE", r"SELECT\s+\*", r"DELETE\s+FROM", r"INSERT\s+INTO",
            r"\bUNION\b\s+\bSELECT\b", 
            r"--\s*$", r"OR\s+1\s*=\s*1", 
            r"SLEEP\(", r"BENCHMARK\(",

            
            # 3. Command Injection (Shell)
            r"[\&\#;\|\$\x00]\s*(ls|cat|rm|whoami|pwd|id|uname|sh|bash|python|php|perl|nc|curl|wget|ping)\b", 
            r"\$\(.*?\)", r"`.*?`", r"\|\s*sh\b", r"\|\s*bash\b",

            
            # 4. Prompt Injection / Jailbreak Basics
            r"ignore\s+previous\s+instructions", 
            r"system\s+prompt", 
            r"you\s+are\s+now\s+a",
            r"DAN\s+mode"
        ]
        self.compiled_rules = [re.compile(p, re.IGNORECASE) for p in self.forbidden_patterns]
        
        # AI Abuse Protection (Spam/Repetition) - In-memory simple cache
        self._user_last_messages: Dict[str, str] = {}

    def validate_and_sanitize(self, text: str, user_id: Optional[str] = None) -> str:
        """
        Girdiyi doğrular ve tehlikeli bulunursa ValueError fırlatır.
        Sınırları, formatları ve tekrarları denetler.
        """
        # 1. Aşama: Empty / Null Check
        if not text or not text.strip():
            logger.warning(f"Input rejected: Empty or whitespace only | User: {user_id or 'anonymous'}")
            raise ValueError("Mesaj alanı boş bırakılamaz.")
            
        clean_text = text.strip()
        
        # 2. Aşama: O(1) Length Limit Kontrolü (Memory Crash Blocking)
        if len(clean_text) > self.max_length:
            logger.warning(f"Input rejected: Too long ({len(clean_text)} chars) | User: {user_id or 'anonymous'}")
            raise ValueError(f"Mesajınız çok uzun. Lütfen {self.max_length} karakterin altında bir metin girin.")

        # 3. Aşama: AI Abuse / Repetition Check
        if user_id:
            if self._user_last_messages.get(user_id) == clean_text:
                logger.warning(f"Input rejected: Repeated identical message | User: {user_id}")
                raise ValueError("Aynı mesajı peş peşe gönderemezsiniz (Spam koruması).")
            self._user_last_messages[user_id] = clean_text

        # 4. Aşama: Pattern Abuse Detection (Regular Expression Match)
        for pattern in self.compiled_rules:
            if pattern.search(clean_text):
                logger.error(f"SECURITY BLOCK: Malicious pattern detected! | User: {user_id or 'anonymous'} | Pattern: {pattern.pattern} | Text: {clean_text[:50]}...")
                raise ValueError("Sistem güvenliği nedeniyle geçersiz veya şüpheli komutlar/karakterler engellendi.")
        
        return clean_text

# Global Singleton Nesnesi
input_validator_core = InputValidator()

