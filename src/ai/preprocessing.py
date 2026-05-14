import re
import unicodedata

def clean_text(text: str) -> str:
    if not text:
        return ""
    
    # URL'leri temizle
    text = re.sub(r'http[s]?://\S+', '', text)
    
    # HTML tag'lerini temizle
    text = re.sub(r'<[^>]+>', '', text)
    
    # Kontrol karakterlerini temizle (newline ve tab hariç)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\r", "\t"))
    
    return text

def normalize_turkish_text(text: str) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # Unicode normalization (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # Satır sonlarını boşluğa çevir ve fazla boşlukları temizle
    text = " ".join(text.split())

    return text.strip()

def validate_input_text(text: str) -> bool:
    if not text or not text.strip():
        return False
    
    # Sadece harf veya sayı içerip içermediğini kontrol et. 
    # (Sadece noktalama veya sadece emoji içeren girdileri engeller)
    has_alphanumeric = bool(re.search(r'[^\W_]', text, re.UNICODE))
    if not has_alphanumeric:
        return False
        
    return True

def prepare_model_input(text: str) -> str:
    if text is None:
        raise ValueError("Girdi boş olamaz.")
        
    # Temizle
    cleaned = clean_text(text)
    
    # Normalize et
    normalized = normalize_turkish_text(cleaned)
    
    # Doğrula
    if not validate_input_text(normalized):
        raise ValueError("Lütfen anlamlı bir metin girin. Sadece emoji veya noktalama işaretleri kabul edilmemektedir.")
        
    # Model limitleri için güvenli kırpma (1000 karakter)
    if len(normalized) > 1000:
        normalized = normalized[:1000].rsplit(' ', 1)[0]
        
    return normalized
