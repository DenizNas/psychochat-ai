"""
conversation_pattern_engine.py — Phase 4.1 Sprint 7.5

Multi-Turn Emotional Pattern Reasoning Layer

Runs AFTER:  theme/need/intent extraction (single-turn)
and BEFORE:  intent enforcement, prompt construction

Purpose:
    Detect short-term repeating emotional patterns across the last 3–5
    user messages WITHOUT heavy memory systems, ML models, or DB changes.

Design:
    - Fully deterministic (no ML, no randomness).
    - Pure function, no side effects.
    - Only reads `recent_user_messages` (plain text list) + current theme/need.
    - Returns: {pattern_name, confidence}

Pattern Taxonomy (Sprint 7.5):
    withdrawal_pattern          — anhedonia + social withdrawal + loneliness
    anxiety_spiral              — exam fear + failure fear + repetitive worry
    uncertainty_cycle           — direction loss + decision paralysis
    self_worth_loop             — self-esteem + self-criticism + failure sensitivity
    social_disconnection_pattern — loneliness + rejection fear + isolation
    none                        — default when no pattern is detected
"""

from typing import Optional, List, Dict
from src.ai.preprocessing import turkish_lower

# ---------------------------------------------------------------------------
# Pattern Taxonomy
# ---------------------------------------------------------------------------

PATTERN_TAXONOMY = frozenset({
    "withdrawal_pattern",
    "anxiety_spiral",
    "uncertainty_cycle",
    "self_worth_loop",
    "social_disconnection_pattern",
    "none",
})

# ---------------------------------------------------------------------------
# Keyword signals for each pattern
# Each pattern entry defines:
#   "signals": list of Turkish keyword fragments that indicate the pattern
#   "theme_signals": list of theme names that strengthen confidence
#   "min_hits": minimum keyword matches needed (across all messages)
#   "confidence_base": base confidence level when min_hits is met
#   "confidence_high": elevated confidence when many matches
# ---------------------------------------------------------------------------

_PATTERN_RULES: List[Dict] = [
    {
        "name": "withdrawal_pattern",
        "signals": [
            # Anhedonia / loss of pleasure
            "keyif alamıyorum", "zevk alamıyorum", "hiçbir şeyden keyif", "tadı yok",
            "keyif al", "zevk al", "isteksiz", "canım istemiy", "hiçbir şey heyecan",
            # Withdrawal / isolation
            "kimseyle konuşmak istemiyorum", "insanlardan uzaklaş", "yalnız kalmak istiyorum",
            "kapanmak istiyorum", "içime kapandım", "dışarı çıkmak istemiyorum",
            "sosyal", "kaçmak istiyorum",
            # Sadness/depression cluster
            "mutsuz", "hüzün", "üzgün", "keder", "ağla", "depresyon",
        ],
        "theme_signals": ["loss_of_pleasure", "social_disconnection", "general_distress"],
        "min_hits": 2,
        "confidence_base": 0.65,
        "confidence_high": 0.85,
    },
    {
        "name": "anxiety_spiral",
        "signals": [
            # Exam / performance anxiety
            "sınav", "sınava", "sınavım", "başarısız", "başarısızlık", "başaramazsam",
            "başaramayacağım", "kaybetmek", "hata yapmak",
            # Repetitive worry
            "sürekli düşünüyorum", "tekrar tekrar", "kafamı durduramıyorum",
            "duramıyorum", "kaygı", "endişe", "panik", "korku", "korkuyorum",
            "aklımdan çıkmıyor", "düşünüyorum",
            # Spiral / rumination
            "ne olacak", "ya olmazsa", "ya başaramazsam",
        ],
        "theme_signals": ["exam_pressure", "fear_of_failure"],
        "min_hits": 2,
        "confidence_base": 0.65,
        "confidence_high": 0.85,
    },
    {
        "name": "uncertainty_cycle",
        "signals": [
            # Direction loss
            "yönünü kaybettim", "yolumu kaybettim", "ne yapacağımı bilmiyorum",
            "nereye gideceğimi", "hayatımın yönünü", "ne yapacağımı",
            # Uncertainty
            "belirsiz", "kararsız", "kararsızım", "emin değilim", "bilmiyorum",
            # Decision paralysis
            "arada kaldım", "karar veremiyorum", "ne yapmalıyım", "seçemiyorum",
        ],
        "theme_signals": ["life_direction_uncertainty"],
        "min_hits": 2,
        "confidence_base": 0.65,
        "confidence_high": 0.85,
    },
    {
        "name": "self_worth_loop",
        "signals": [
            # Self-criticism
            "yetersiz", "yetersizim", "yeterli değilim", "kendimi yetersiz",
            "başarısızım", "hep başarısız", "bir işe yaramıyorum",
            "hiçbir şeyi başaramıyorum", "beceremiyorum",
            # Self-esteem
            "özgüven", "kendime güven", "güvenmiyorum", "değersiz", "değersizim",
            "kusur", "eksiklik", "kusurlu",
            # Self-blame / shame
            "kendimi suçluyorum", "benim hatam", "benim yüzümden", "suçlu",
            "utanıyorum", "utanç",
        ],
        "theme_signals": ["self_worth_doubt"],
        "min_hits": 2,
        "confidence_base": 0.65,
        "confidence_high": 0.85,
    },
    {
        "name": "social_disconnection_pattern",
        "signals": [
            # Loneliness
            "yalnız", "yalnızım", "yapayalnız", "kimsem yok", "kimse yok",
            "kimseyle konuşamıyorum", "kimse anlamıyor", "dışlandım", "dışlanıyorum",
            # Rejection fear
            "reddedil", "kabul göremi", "istenmi", "terk",
            # Social withdrawal
            "insanlardan uzak", "insanlarla konuşmak", "sosyal",
        ],
        "theme_signals": ["social_disconnection"],
        "min_hits": 2,
        "confidence_base": 0.65,
        "confidence_high": 0.85,
    },
]

# Confidence thresholds
_CONFIDENCE_THRESHOLD = 0.70   # below this → report "none"
_HIGH_HIT_MULTIPLIER = 4       # hits >= this many → use confidence_high


# ---------------------------------------------------------------------------
# Core Detection Function
# ---------------------------------------------------------------------------

def detect_conversation_pattern(
    recent_user_messages: List[str],
    current_theme: Optional[str] = None,
    current_need: Optional[str] = None,
) -> Dict[str, object]:
    """
    Detect a short-term emotional pattern from the last 3–5 user messages.

    Args:
        recent_user_messages: List of raw user message strings (most recent LAST).
                               Only the last 5 messages are examined.
        current_theme:         Current turn's detected theme (from theme_need_engine).
        current_need:          Current turn's detected need (from theme_need_engine).

    Returns:
        {
            "pattern_name": str,     # pattern key or "none"
            "confidence": float,     # 0.0–1.0
            "hit_count": int,        # total keyword matches across messages
        }
    """
    # Guard: need at least 2 messages to detect a pattern
    if not recent_user_messages or len(recent_user_messages) < 2:
        return _no_pattern()

    # Work on the last 5 messages only (clean & lower)
    window = [turkish_lower(m) for m in recent_user_messages[-5:]]
    combined = " ".join(window)

    best_pattern: Optional[str] = None
    best_confidence: float = 0.0
    best_hits: int = 0

    for rule in _PATTERN_RULES:
        name = rule["name"]
        signals = rule["signals"]
        theme_signals = rule["theme_signals"]
        min_hits = rule["min_hits"]
        conf_base = rule["confidence_base"]
        conf_high = rule["confidence_high"]

        # Count keyword hits across all combined text without double-counting nested substrings
        temp_combined = combined
        keyword_hits = 0
        # Sort signals by length descending to match longest matches first
        sorted_signals = sorted(signals, key=len, reverse=True)
        for kw in sorted_signals:
            if kw in temp_combined:
                keyword_hits += 1
                # Replace with placeholder to prevent shorter nested keywords from matching
                temp_combined = temp_combined.replace(kw, "_" * len(kw))

        # Theme signal boost: if current_theme matches this pattern's themes, +1
        theme_boost = 1 if current_theme and current_theme in theme_signals else 0

        total_hits = keyword_hits + theme_boost

        # Must meet minimum hit threshold
        if total_hits < min_hits:
            continue

        # Choose confidence level based on hit count
        confidence = conf_high if total_hits >= _HIGH_HIT_MULTIPLIER else conf_base

        # Calculate contributing messages count
        contributing_messages_count = 0
        for i, m in enumerate(window):
            # Check if this specific message contains any of the rule's signals
            # Note: for contributing messages count, we check if any signal keyword is in this message
            has_keyword = any(kw in m for kw in signals)
            # The theme boost applies to the last message (representing current turn)
            is_last = (i == len(window) - 1)
            has_theme = is_last and current_theme and (current_theme in theme_signals)
            if has_keyword or has_theme:
                contributing_messages_count += 1

        # Strict activation requirements (Sprint 7.5.1):
        # 1. confidence >= 0.70
        # 2. hit_count >= 2
        # 3. at least 2 relevant user messages contributed to the pattern
        # 4. recent_user_messages length >= 2
        if (
            confidence < 0.70
            or total_hits < 2
            or contributing_messages_count < 2
            or len(recent_user_messages) < 2
        ):
            continue

        # Track best match
        if confidence > best_confidence or (confidence == best_confidence and total_hits > best_hits):
            best_pattern = name
            best_confidence = confidence
            best_hits = total_hits

    # Apply threshold filter
    if best_pattern is None or best_confidence < _CONFIDENCE_THRESHOLD:
        return _no_pattern()

    return {
        "pattern_name": best_pattern,
        "confidence": round(best_confidence, 2),
        "hit_count": best_hits,
    }


def _no_pattern() -> Dict[str, object]:
    """Return the default empty-pattern result."""
    return {
        "pattern_name": "none",
        "confidence": 0.0,
        "hit_count": 0,
    }


# ---------------------------------------------------------------------------
# Pattern → Soft Counseling Acknowledgement Templates
# ---------------------------------------------------------------------------

# These are instruction fragments injected into the system prompt.
# They describe HOW the counselor should acknowledge the pattern — softly,
# without diagnosis or exaggeration.

PATTERN_ACKNOWLEDGEMENT_INSTRUCTIONS: Dict[str, str] = {
    "withdrawal_pattern": (
        "Son birkaç mesajında hem keyifsizlikten hem de insanlardan uzaklaşma isteğinden "
        "söz ettiğini fark ediyorum. Bu örüntüye nazikçe değinebilirsin: "
        "Kullanıcının birkaç mesajda tekrarlanan bu çekilme eğilimini fark ettiğini "
        "empatik ve yargılamayan bir dille yansıt. "
        "Teşhis koymaktan, 'sen hep böylesin' türü genellemelerden ve abartılı ifadelerden KESİNLİKLE kaçın."
    ),
    "anxiety_spiral": (
        "Son birkaç mesajında kaygı veya başarısızlık korkusunun tekrar tekrar öne çıktığını fark ediyorum. "
        "Bu sarmalı nazikçe yansıtabilirsin: "
        "Kullanıcının aynı endişenin birkaç mesajda döndüğünü yumuşak bir dille tanı. "
        "'Her zaman kaygılanıyorsun' gibi mutlak genellemelerden KESİNLİKLE kaçın; "
        "bunun yerine 'son konuşmalarında…' veya 'bir süredir aklını meşgul eden…' gibi yumuşak ifadeler kullan."
    ),
    "uncertainty_cycle": (
        "Son konuşmalarında yönünü bulmakta zorlandığından birkaç kez söz ettin. "
        "Bu döngüyü nazikçe çerçevele: "
        "Kullanıcının belirsizliğinin birden fazla mesajda tekrar ettiğini fark ettiğini "
        "yumuşak bir dille yansıt. "
        "Tanı koymaktan, kesin genellemelerden ve 'sen sürekli…' ifadelerinden KESİNLİKLE kaçın."
    ),
    "self_worth_loop": (
        "Son birkaç mesajında kendini sorgulama veya yetersizlik hissinin tekrar ettiğini fark ediyorum. "
        "Bu örüntüyü nazikçe tanı: "
        "Kullanıcının öz-eleştirinin birden fazla mesajda döndüğünü empatik bir dille yansıt. "
        "'Sen hep kendini suçlarsın' türü kesin ifadelerden KESİNLİKLE kaçın; "
        "bunun yerine 'son konuşmalarında…' gibi yumuşak bir çerçeve kullan."
    ),
    "social_disconnection_pattern": (
        "Son birkaç mesajında bağlantı kurmanın zorluğundan ya da yalnızlık hissinden tekrar tekrar söz ettin. "
        "Bu örüntüyü nazikçe yansıt: "
        "Kullanıcının sosyal kopukluk hissinin birden fazla mesajda tekrar ettiğini "
        "empatik, yargılamayan ve yumuşak bir dille tanı. "
        "'Sen hep yalnızsın' türü abartılı genellemelerden KESİNLİKLE kaçın."
    ),
}
