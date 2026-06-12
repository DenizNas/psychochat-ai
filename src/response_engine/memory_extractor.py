import re
from src.ai.preprocessing import turkish_lower
from src.response_engine.memory_profile import add_to_profile

_PRIVACY_BLOCK_PATTERNS = [
    # PII
    r"\d{10,11}",                             # phone numbers
    r"\b\d{2}[\s./]\d{2}[\s./]\d{4}\b",      # dates as identity
    r"tc\s*kimlik",
    r"kimlik\s*no",
    r"pasaport\s*no",
    r"adres[im]?[\s:]+\w",
    r"sokak|mahalle|ilçe|semt|posta\s*kodu|bulvar|apartman|daire",
    r"e.?posta\s*adresi",
    # Self-harm / crisis
    r"kendim[ie]\s*zarar",
    r"intihar\s*et",
    r"kendimi\s*öldür",
    r"hayatıma\s*son",
    r"yaşamak\s*istemiyorum",
    r"bıçak\s*kes",
    r"hap\s*iç",
    r"zehir\s*iç",
    r"kendime\s*zarar",
    # Secrets / credentials
    r"api\s*key",
    r"secret\s*key",
    r"password|şifre\s*şu",
    r"token\s*değerim|iban|kredi\s*kartı|kart\s*no|cvv",
    # Sensitive identity / Political / Religious / Sexual / Medical health details
    r"\b(siyasi|parti|oy\s*ver|akp|chp|mhp|dem\s*parti|politika|erdoğan|imamoğlu)\b",
    r"\b(müslüman|hristiyan|yahudi|musevi|ateist|deist|mezhep|inanç|dini|ibadet|namaz|kilise|cami)\b",
    r"\b(cinsel|yönelim|lgbt|lezbiyen|biseksüel|hetero|homoseksüel|transseksüel)\b",
    r"\b(hiv|aids|kanser|tedavi|ilaç|antidepresan|psikiyatri|tanı|tanısı|teşhis|klinik|hastalık|bipolar|bozukluk|şizofreni|anksiyete|depresyon)\b",
]

_PRIVACY_RE = re.compile(
    "|".join(_PRIVACY_BLOCK_PATTERNS),
    flags=re.IGNORECASE | re.UNICODE,
)

def _is_privacy_safe(text: str) -> bool:
    """Returns True if text contains no phone numbers, passwords, national IDs, or self-harm keywords."""
    return not bool(_PRIVACY_RE.search(turkish_lower(text)))

def _is_crisis(risk: str) -> bool:
    """Checks whether the turn has a crisis risk level."""
    return risk.strip().lower() in {"1", "crisis", "kriz"}

def extract_and_update_profile(user_id: str, text: str, emotion: str, risk: str) -> None:
    """
    Lightweight rule-based extraction to parse wellness profile points from chat text.
    Enforces privacy guards and skips extraction during crisis turns.
    """
    # Guard 0: Privacy safety check
    if not text or not _is_privacy_safe(text):
        return
        
    # Guard 1: Crisis check (no memory extraction during active crisis)
    if _is_crisis(risk):
        return
        
    text_lower = turkish_lower(text)
    
    # 1. Repeated Anxiety & Sadness Topics
    if any(k in text_lower for k in ["anksiyete", "kaygı", "endişe", "telaş", "panik", "sıkışma"]):
        add_to_profile(user_id, "recurring_emotions", "anxiety")
        if "sınav" in text_lower or "ders" in text_lower or "okul" in text_lower:
            add_to_profile(user_id, "stressors", "sınav kaygısı")
        elif "iş" in text_lower or "patron" in text_lower:
            add_to_profile(user_id, "stressors", "iş kaygısı")
        else:
            add_to_profile(user_id, "stressors", "kaygı")
            
    if any(k in text_lower for k in ["üzgün", "hüzün", "ağla", "mutsuz", "keder", "acı"]):
        add_to_profile(user_id, "recurring_emotions", "sadness")

    # 2. Relationship Context
    if any(k in text_lower for k in ["sevgili", "flört", "partner", "eşim", "kocam", "karım", "arkadaş", "dost"]):
        if any(k in text_lower for k in ["sevgili", "flört", "partner", "eşim", "kocam", "karım"]):
            add_to_profile(user_id, "relationship_context", "partner ilişkisi")
        if any(k in text_lower for k in ["arkadaş", "dost"]):
            add_to_profile(user_id, "relationship_context", "arkadaş ilişkisi")

    # 3. Academic / Exams Context
    if any(k in text_lower for k in ["sınav", "vize", "final", "yks", "kpss", "ders çalış", "okul", "ödev"]):
        add_to_profile(user_id, "work_or_school_context", "akademik süreç")
        add_to_profile(user_id, "stressors", "sınav stresi")

    # 4. Work Stress Context
    if any(k in text_lower for k in ["iş stresi", "patron", "ofis", "toplantı", "proje", "mesai", "terfi"]):
        add_to_profile(user_id, "work_or_school_context", "iş/kariyer")
        add_to_profile(user_id, "stressors", "iş stresi")

    # 5. Sleep Issues
    if any(k in text_lower for k in ["uyku", "uyuyam", "gece", "kabus", "uyandım", "insomnia"]):
        add_to_profile(user_id, "stressors", "uyku sorunları")

    # 6. Loneliness
    if any(k in text_lower for k in ["yalnız", "kimsem yok", "yapayalnız", "kimse yok"]):
        add_to_profile(user_id, "stressors", "yalnızlık")

    # 7. Motivation Problems
    if any(k in text_lower for k in ["motivasyon", "isteksiz", "hiçbir şey yapmak", "canım istemiyor", "üşen"]):
        add_to_profile(user_id, "stressors", "motivasyon kaybı")

    # 8. Coping Methods
    if any(k in text_lower for k in ["günlük", "yazmak", "günlük tut"]):
        add_to_profile(user_id, "coping_methods", "günlük tutmak")
    if any(k in text_lower for k in ["nefes egzersiz", "derin nefes", "nefes al"]):
        add_to_profile(user_id, "coping_methods", "nefes egzersizleri")

    # 9. Wellness Goal Tracking (anxiety reduction, sleep improvement, mood awareness, etc.)
    if any(k in text_lower for k in ["hedef", "istiyorum", "çalışıyorum", "çabalıyorum", "hedefliyorum"]):
        if any(k in text_lower for k in ["kaygı", "anksiyete", "sakin"]):
            add_to_profile(user_id, "goals", "anxiety reduction")
        if any(k in text_lower for k in ["uyku", "erken yat", "uyumak", "uyku düz"]):
            add_to_profile(user_id, "goals", "sleep improvement")
        if any(k in text_lower for k in ["mod", "duygu", "hiss", "fark"]):
            add_to_profile(user_id, "goals", "mood awareness")
        if any(k in text_lower for k in ["özgüven", "kendime güven", "değer"]):
            add_to_profile(user_id, "goals", "confidence building")
        if any(k in text_lower for k in ["arkadaş", "sosyal", "çevre", "insan"]):
            add_to_profile(user_id, "goals", "social connection")
        if any(k in text_lower for k in ["stres", "yönet", "başa çık"]):
            add_to_profile(user_id, "goals", "stress management")
