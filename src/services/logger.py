from src.services.database import save_analytics

def log_interaction(user_id: str, user_text: str, emotion: str, risk: str, language: str, latency_ms: float):
    # Log to SQLite DB instead of CSV
    save_analytics(
        user_id=user_id,
        user_text=user_text,
        emotion=emotion,
        risk=risk,
        language=language,
        latency_ms=latency_ms
    )
