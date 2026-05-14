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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds & penalty weights
# ---------------------------------------------------------------------------

NORMAL_THRESHOLD: float = 0.55
CRISIS_THRESHOLD: float = 0.85

# Penalty definitions — (reason_tag, penalty_amount)
PENALTY_EMPTY: Tuple[str, float]            = ("empty_response",       1.0)
PENALTY_TOO_SHORT: Tuple[str, float]        = ("too_short",            0.4)
PENALTY_REPETITIVE: Tuple[str, float]       = ("repetitive",           0.3)
PENALTY_GENERIC: Tuple[str, float]          = ("generic_response",     0.2)
# PENALTY_UNSAFE is intentionally NOT applied by the ranker.
# Unsafe content detection is handled exclusively by safety.py (check_safety),
# which runs as a separate, independent pipeline stage after the ranker.
# Keeping unsafe filtering in one place avoids double-penalty and conflicting logic.
# PENALTY_UNSAFE: Tuple[str, float] = ("unsafe_content", 1.0)
PENALTY_CRISIS_UNSAFE: Tuple[str, float]    = ("crisis_unsafe",        1.0)
PENALTY_CONTEXT_MISMATCH: Tuple[str, float] = ("context_mismatch",     0.3)

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
    words = text.lower().split()
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
    lower = _nfc(text).lower()
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

    if emotion.lower() not in negative_emotions:
        return None

    lower = text.lower()
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
    lower = text.lower()
    for kw in _CRISIS_ANCHOR_KEYWORDS:
        if kw in lower:
            return None  # at least one anchor found → pass
    return PENALTY_CRISIS_UNSAFE


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_response(
    text: str,
    emotion: str = "neutral",
    risk: str = "Normal",
) -> RankResult:
    """
    Scores a GPT-generated response across all quality dimensions.

    Args:
        text    : Raw GPT response text (pre-format, post-strip)
        emotion : Detected emotion label for context mismatch check
        risk    : Detected risk label (determines crisis threshold)

    Returns:
        RankResult with score, pass/fail, and penalty reasons
    """
    is_crisis = _is_crisis(risk)
    threshold = CRISIS_THRESHOLD if is_crisis else NORMAL_THRESHOLD

    score = 1.0
    reasons: List[str] = []

    # Run all checks in priority order
    checks = [
        check_empty(text),
        check_too_short(text, is_crisis),
        check_repetitive(text),
        check_generic(text),
        check_context_mismatch(text, emotion),
        check_crisis_unsafe(text, is_crisis),
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
