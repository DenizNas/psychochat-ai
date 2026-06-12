"""
response_ranker.py — Faz 5 Prompt 7
Production-Grade Response Quality Scoring & Ranking

Responsibilities:
    - Score a GPT-generated response across multiple quality dimensions
    - Return deterministic, penalty-based scores (no randomness)
    - Signal whether retry or fallback is needed
    - Apply stricter thresholds in crisis turns
    - Preserve all emotion / memory / context signal (does not alter content)

Scoring model:
    Base score: 1.0
    Each penalty subtracts from the base.
    Final score clamped to [0.0, 1.0].

Thresholds:
    NORMAL_THRESHOLD = 0.55
    CRISIS_THRESHOLD = 0.85   ← much stricter; any doubt → safe template

Priority rule:
    crisis safety > ranker score > format quality
    (Crisis fallback is never overridden by the ranker.)

Design constraints:
    - Deterministic: same input → same score every time
    - O(n) in response length: no external calls, no model inference
    - UTF-8 safe throughout
    - No side effects (pure functions)
"""

import re
import unicodedata
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from src.ai.preprocessing import turkish_lower

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds & penalty weights
# ---------------------------------------------------------------------------

NORMAL_THRESHOLD: float = 0.45
CRISIS_THRESHOLD: float = 0.85

# Penalty definitions — (reason_tag, penalty_amount)
PENALTY_EMPTY: Tuple[str, float]            = ("empty_response",       1.0)
PENALTY_TOO_SHORT: Tuple[str, float]        = ("too_short",            0.5)
PENALTY_REPETITIVE: Tuple[str, float]       = ("repetitive",           0.3)
PENALTY_GENERIC: Tuple[str, float]          = ("generic_response",     0.1)
# PENALTY_UNSAFE is intentionally NOT applied by the ranker.
# Unsafe content detection is handled exclusively by safety.py (check_safety),
# which runs as a separate, independent pipeline stage after the ranker.
# Keeping unsafe filtering in one place avoids double-penalty and conflicting logic.
# PENALTY_UNSAFE: Tuple[str, float] = ("unsafe_content", 1.0)
PENALTY_CRISIS_UNSAFE: Tuple[str, float]    = ("crisis_unsafe",        1.0)
PENALTY_CONTEXT_MISMATCH: Tuple[str, float] = ("context_mismatch",     0.3)
PENALTY_ROBOTIC_MEMORY: Tuple[str, float]   = ("robotic_memory_phrase", 0.6)
PENALTY_TOO_MANY_QUESTIONS: Tuple[str, float] = ("too_many_questions", 0.6)
PENALTY_TOO_MANY_BULLETS: Tuple[str, float]   = ("too_many_bullets", 0.6)
PENALTY_UNNATURAL_TURKISH: Tuple[str, float]  = ("unnatural_turkish", 0.6)
PENALTY_REPEATED_ADVICE: Tuple[str, float]    = ("repeated_advice", 0.6)
PENALTY_OVERUSED_SUGGESTION: Tuple[str, float]= ("overused_suggestion", 0.15)
PENALTY_ENGLISH_LEAKAGE: Tuple[str, float]    = ("english_leakage", 0.6)

# Words that indicate a low-effort, generic response (TR + EN)
_GENERIC_PHRASES: List[str] = [
    "anlıyorum",            # "I understand" alone — no follow-up
    "tabii ki",             # "of course" opener with nothing else
    "elbette",
    "of course",
    "i understand",
    "i see",
    "that is correct",
    "you are right",
    "haklısınız",
    "kesinlikle",           # "absolutely" as a lone opener
]

# Minimum meaningful word count for a non-crisis response
_MIN_WORDS_NORMAL: int = 8

# Minimum word count in a crisis response (must be substantive)
_MIN_WORDS_CRISIS: int = 15

# Ratio threshold for repetition detection:
# if the most-frequent bigram appears in > X% of all bigrams → repetitive
_REPETITION_RATIO: float = 0.35

# Crisis-specific keywords that MUST appear in a crisis-mode response
_CRISIS_ANCHOR_KEYWORDS: List[str] = [
    "güvend", "yardım", "destek", "112", "uzman", "professional",
    "yalnız değil", "help", "safe", "support"
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def _word_count(text: str) -> int:
    return len(text.split())


def _bigrams(words: List[str]) -> List[Tuple[str, str]]:
    return [(words[i], words[i + 1]) for i in range(len(words) - 1)]


def _is_crisis(risk: str) -> bool:
    return risk.strip().lower() in {"1", "crisis", "kriz"}


# ---------------------------------------------------------------------------
# Score Result
# ---------------------------------------------------------------------------

@dataclass
class RankResult:
    """
    Output of score_response().

    Attributes:
        score           : Final quality score [0.0, 1.0]
        passes          : True if score >= threshold for the given risk level
        reasons         : List of penalty tags applied
        needs_retry     : True if score low enough to warrant a retry (non-crisis)
        needs_fallback  : True if score low enough to use safe template (crisis)
    """
    score: float
    passes: bool
    reasons: List[str] = field(default_factory=list)
    needs_retry: bool = False
    needs_fallback: bool = False

    def to_dict(self) -> dict:
        return {
            "quality_score": round(self.score, 4),
            "quality_reasons": self.reasons,
            "passes": self.passes,
            "needs_retry": self.needs_retry,
            "needs_fallback": self.needs_fallback,
        }


# ---------------------------------------------------------------------------
# Individual check functions (each independently testable)
# ---------------------------------------------------------------------------

def check_empty(text: str) -> Optional[Tuple[str, float]]:
    """Penalise completely empty or whitespace-only response."""
    if not text or not text.strip():
        return PENALTY_EMPTY
    return None


def check_too_short(text: str, is_crisis: bool) -> Optional[Tuple[str, float]]:
    """
    Penalise responses that are too brief to be meaningful.
    Crisis responses must be longer to ensure proper safety messaging.
    """
    min_words = _MIN_WORDS_CRISIS if is_crisis else _MIN_WORDS_NORMAL
    if _word_count(text) < min_words:
        return PENALTY_TOO_SHORT
    return None


def check_repetitive(text: str) -> Optional[Tuple[str, float]]:
    """
    Detect pathological repetition via bigram frequency.
    If any single bigram dominates > REPETITION_RATIO of all bigrams → flag.
    """
    words = turkish_lower(text).split()
    if len(words) < 6:
        return None  # too short to analyse bigram distribution
    bgs = _bigrams(words)
    if not bgs:
        return None
    freq: dict = {}
    for bg in bgs:
        freq[bg] = freq.get(bg, 0) + 1
    max_freq = max(freq.values())
    if max_freq / len(bgs) > _REPETITION_RATIO:
        return PENALTY_REPETITIVE
    return None


def check_generic(text: str) -> Optional[Tuple[str, float]]:
    """
    Flag responses that consist almost entirely of a generic opener with no
    substantive follow-up (< 12 words total AND starts with a generic phrase).
    """
    lower = turkish_lower(_nfc(text))
    if _word_count(text) >= 12:
        return None  # long enough — not generic even if it starts with filler
    for phrase in _GENERIC_PHRASES:
        if lower.startswith(phrase):
            return PENALTY_GENERIC
    return None


def check_context_mismatch(text: str, emotion: str) -> Optional[Tuple[str, float]]:
    """
    Heuristic: if emotion is clearly negative but response contains only
    positive/celebratory words with no empathy signal → mismatch.
    Keeps scoring fast (no embeddings).
    """
    negative_emotions = {"sadness", "sad", "anger", "angry", "anxiety", "fear",
                         "grief", "depressed", "frustrated", "üzgün", "öfkeli",
                         "kaygılı", "korkmuş", "üzüntü"}
    positive_only_signals = {
        "harika", "mükemmel", "süper", "wonderful", "amazing", "fantastic",
        "great news", "congratulations", "tebrikler"
    }
    empathy_signals = {
        "anlıyorum", "duyabiliyorum", "zor", "difficult", "hissediyorum",
        "yalnız değil", "destek", "yanındayım", "feel", "hear you"
    }

    if turkish_lower(emotion) not in negative_emotions:
        return None

    lower = turkish_lower(text)
    has_positive_only = any(sig in lower for sig in positive_only_signals)
    has_empathy = any(sig in lower for sig in empathy_signals)

    if has_positive_only and not has_empathy:
        return PENALTY_CONTEXT_MISMATCH
    return None


def check_crisis_unsafe(text: str, is_crisis: bool) -> Optional[Tuple[str, float]]:
    """
    In crisis sessions, the response MUST contain at least one crisis anchor
    keyword (e.g., güvend, 112, yardım, destek…).
    Missing all anchor words in a crisis context → heavy penalty.
    """
    if not is_crisis:
        return None
    lower = turkish_lower(text)
    for kw in _CRISIS_ANCHOR_KEYWORDS:
        if kw in lower:
            return None  # at least one anchor found → pass
    return PENALTY_CRISIS_UNSAFE


def check_robotic_memory(text: str) -> Optional[Tuple[str, float]]:
    """
    Penalise robotic memory phrases like 'hafızamda var', 'sistemde kayıtlı', 
    'daha önce kaydetmiştim', etc.
    """
    lower = turkish_lower(_nfc(text))
    robotic_patterns = [
        "hafızamda var", "hafızamda kayıtlı", "sistemde kayıtlı", "sistemde var", 
        "daha önce kaydettim", "kayıtlarıma göre", "daha önce kaydetmiştim", "veritabanımda"
    ]
    if any(p in lower for p in robotic_patterns):
        return PENALTY_ROBOTIC_MEMORY
    return None


def check_standalone_generic_phrases(text: str) -> Optional[Tuple[str, float]]:
    """Penalise standalone generic empathy/advice/greeting phrases that appear without context."""
    cleaned = turkish_lower(_nfc(text)).replace(".", "").replace(",", "").replace("!", "").strip()
    standalone_patterns = {
        "seni anlıyorum", "sizi anlıyorum", "bu zor olmalı", "zor olmalı",
        "kendine iyi bak", "nefes egzersizi yapabilirsin"
    }
    if cleaned in standalone_patterns:
        return PENALTY_GENERIC
    return None


def check_repeated_advice(
    text: str,
    user_id: Optional[str] = None,
    recent_responses: Optional[List[str]] = None
) -> Optional[Tuple[str, float]]:
    """Penalise advice repeated from memory profile or recent session history."""
    lower = turkish_lower(_nfc(text))
    
    last_topics = []
    if user_id:
        try:
            from src.response_engine.memory_profile import load_profile
            profile = load_profile(user_id)
            last_topics = profile.get("last_advice_topics", [])
        except Exception:
            pass
            
    topic_keywords = {
        "breathing exercise": ["nefes egzersiz", "derin nefes", "nefes al"],
        "journaling": ["günlük tut", "yazmayı dene", "günlüğe yaz", "günlük yaz"],
        "sleep routine": ["uyku düzen", "uyku saat", "uyku rutini"],
        "social connection": ["sosyal bağ", "arkadaşlarınla", "yakınlarınla", "sosyalleş"],
        "walking": ["yürüyüş", "yürümek", "yürüyüşe çık"]
    }
    
    # 1. Compare against memory profile
    for topic in last_topics:
        keywords = topic_keywords.get(topic, [])
        if any(kw in lower for kw in keywords):
            return PENALTY_REPEATED_ADVICE
            
    # 2. Compare against recent session responses
    if recent_responses:
        for resp in recent_responses:
            resp_lower = turkish_lower(resp)
            for topic, keywords in topic_keywords.items():
                if any(kw in lower for kw in keywords) and any(kw in resp_lower for kw in keywords):
                    return PENALTY_REPEATED_ADVICE
                    
    return None


def check_too_many_questions(text: str) -> Optional[Tuple[str, float]]:
    """Penalise response with 3 or more question marks."""
    if text.count("?") >= 3:
        return PENALTY_TOO_MANY_QUESTIONS
    return None


def check_too_many_bullets(text: str) -> Optional[Tuple[str, float]]:
    """Penalise response with 3 or more bullet points or numbered lists."""
    lines = text.split("\n")
    bullet_count = 0
    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith(("-", "*", "•", "◦", "▪", "▫")):
            bullet_count += 1
        elif re.match(r"^\d+[\s.)]", line_strip):
            bullet_count += 1
    if bullet_count >= 3:
        return PENALTY_TOO_MANY_BULLETS
    return None


def check_unnatural_turkish(text: str) -> Optional[Tuple[str, float]]:
    """Penalise unnatural/translated/clinical Turkish phrases."""
    lower = turkish_lower(_nfc(text))
    unnatural_phrases = [
        "hissettiğini duyabiliyorum",
        "öyle hissettiğini",
        "pişmanlık döngüsü",
        "sınır çizebilmek",
        "bardağı dolduran",
        "klinik olarak",
        "terapi sürecinde",
        "psikolojik tanı",
        "tıbbi teşhis"
    ]
    if any(p in lower for p in unnatural_phrases):
        return PENALTY_UNNATURAL_TURKISH
    return None


def check_overused_suggestions(text: str) -> Optional[Tuple[str, float]]:
    """Apply a minor penalty if any of the overused suggestions appear in normal turns."""
    lower = turkish_lower(_nfc(text))
    overused = ["nefes egzersiz", "günlük tut", "yürüyüş", "su iç", "uyku düzen"]
    if any(o in lower for o in overused):
        return PENALTY_OVERUSED_SUGGESTION
    return None


def check_english_leakage(text: str) -> Optional[Tuple[str, float]]:
    """
    Prevent English prompt leakage, system leakage, internal AI terminology,
    and developer-language leakage from appearing in user-visible responses.
    """
    if not text:
        return None

    lower_en = text.lower()
    lower_tr = turkish_lower(text)

    leakage_terms = [
        # A) Internal AI / Prompt Engineering Terms
        "validate", "validation", "response", "retry", "follow-up", "prompt", "system prompt",
        "assistant", "user profile", "memory injection", "context builder", "response ranking",
        "quality score", "temperature", "token", "hallucination", "reasoning", "chain of thought",
        "grounding", "fallback", "provider", "retry calibration", "instruction",
        
        # B) Therapy-English Terms
        "coping mechanism", "grounding technique", "emotional regulation", "self-compassion",
        "mindfulness", "reframing", "cognitive distortion", "validation exercise",
        
        # C) Technical Leakage
        "database", "veritabanı referansı", "system memory", "internal memory", "cache",
        "api", "openai", "anthropic", "gpt", "llm", "provider selection"
    ]

    boundary_chars = r"a-zçğıöşü"
    
    for term in leakage_terms:
        pattern = rf"(?<![{boundary_chars}]){re.escape(term)}(?![{boundary_chars}])"
        if re.search(pattern, lower_en) or re.search(pattern, lower_tr):
            return PENALTY_ENGLISH_LEAKAGE

    return None


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_response(
    text: str,
    emotion: str = "neutral",
    risk: str = "Normal",
    user_id: Optional[str] = None,
    recent_responses: Optional[List[str]] = None,
) -> RankResult:
    """
    Scores a GPT-generated response across all quality dimensions.

    Args:
        text            : Raw GPT response text (pre-format, post-strip)
        emotion         : Detected emotion label for context mismatch check
        risk            : Detected risk label (determines crisis threshold)
        user_id         : Optional user_id to look up memory profile advice topics
        recent_responses: Optional list of recent assistant responses in session

    Returns:
        RankResult with score, pass/fail, and penalty reasons
    """
    is_crisis = _is_crisis(risk)
    threshold = CRISIS_THRESHOLD if is_crisis else NORMAL_THRESHOLD

    score = 1.0
    reasons: List[str] = []

    # Run checks based on whether it is a crisis turn or normal turn
    if is_crisis:
        checks = [
            check_empty(text),
            check_too_short(text, is_crisis=True),
            check_repetitive(text),
            check_generic(text),
            check_crisis_unsafe(text, is_crisis=True),
            check_english_leakage(text),
        ]
    else:
        checks = [
            check_empty(text),
            check_too_short(text, is_crisis=False),
            check_repetitive(text),
            check_generic(text),
            check_context_mismatch(text, emotion),
            check_robotic_memory(text),
            check_standalone_generic_phrases(text),
            check_repeated_advice(text, user_id, recent_responses),
            check_too_many_questions(text),
            check_too_many_bullets(text),
            check_unnatural_turkish(text),
            check_overused_suggestions(text),
            check_english_leakage(text),
        ]

    for result in checks:
        if result is not None:
            tag, penalty = result
            score -= penalty
            reasons.append(tag)

    score = max(0.0, min(1.0, score))
    passes = score >= threshold

    needs_retry = (not passes) and (not is_crisis)
    needs_fallback = (not passes) and is_crisis

    return RankResult(
        score=score,
        passes=passes,
        reasons=reasons,
        needs_retry=needs_retry,
        needs_fallback=needs_fallback,
    )
