from typing import Optional
from src.ai.preprocessing import turkish_lower

def detect_conversation_strategy(text: str, primary_emotion: str, subtype: Optional[str] = None) -> str:
    """
    Selects one primary response strategy deterministically:
    1. validation
    2. exploration
    3. reflection
    4. psychoeducation
    5. action_planning
    6. strengths_focused

    Inputs:
      - text: User input text
      - primary_emotion: Mapped counseling category (e.g. sadness, anxiety, fear, uncertainty)
      - subtype: Detected emotion subtype (e.g. exam_anxiety, failure_fear, anhedonia)
    """
    clean_text = turkish_lower(text or "").strip()
    primary = primary_emotion.strip().lower()
    sub = (subtype or "").strip().lower()

    # Rule 1: exam/performance anxiety -> psychoeducation or action_planning
    # Sınav kaygısı ve sunum kaygısı durumunda psikoeğitim (psychoeducation) stratejisini seçiyoruz
    if sub in ("exam_anxiety", "performance_anxiety") or any(k in clean_text for k in ["sınav", "sinav", "vize", "final", "test", "lgs", "yks", "sunum", "mülakat"]):
        return "psychoeducation"

    # Rule 2: uncertainty / "what should I do" intents -> action_planning
    if primary == "uncertainty" or sub == "decision_uncertainty" or any(k in clean_text for k in ["ne yapacağımı", "ne yapacagimi", "ne yapsam", "bilmiyorum", "kararsız", "arada kaldım", "hangisi"]):
        return "action_planning"

    # Rule 3: reflection -> mirrored thought (e.g. failure fear, rejection fear)
    if sub in ("failure_fear", "rejection_fear", "future_fear") or any(k in clean_text for k in ["başarısız", "hata yap", "yanlış yap", "reddedil", "istenme", "sevilme"]):
        return "reflection"

    # Rule 4: strengths_focused -> effort, coping, progress, resilience
    if any(k in clean_text for k in ["denedim", "çabalıyorum", "başardım", "yaptım", "iyi geldi", "iyiyim", "atladım"]):
        return "strengths_focused"

    # Rule 5: high-intensity sadness/fear/anger/loneliness -> validation
    if primary in ("sadness", "fear", "anger", "loneliness", "guilt_shame") or sub in ("anhedonia", "burnout", "grief", "hopelessness", "disappointment", "guilt", "shame"):
        return "validation"

    # Rule 6: neutral/mild unclear messages -> exploration
    return "exploration"
