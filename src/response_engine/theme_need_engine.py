"""
theme_need_engine.py — Phase 4.1 Sprint 7.4

Theme & Need Extraction Layer

Runs AFTER:  emotion classification, subtype detection
and BEFORE:  strategy selection, prompt construction

Returns a psychological understanding snapshot per turn:
    {"theme": ..., "need": ..., "intent": ...}

Design:
- Fully deterministic (no ML, no randomness).
- Priority chain: subtype-level → keyword-level → emotion-level → fallback.
- Pure function, no side effects.
- Does NOT yet modify prompts or strategy — only extracts and transports.
"""

from typing import Optional, Dict
from src.ai.preprocessing import turkish_lower

# ---------------------------------------------------------------------------
# Frozen Taxonomies
# ---------------------------------------------------------------------------

THEME_TAXONOMY = frozenset({
    "loss_of_pleasure",
    "fear_of_failure",
    "exam_pressure",
    "social_disconnection",
    "life_direction_uncertainty",
    "self_worth_doubt",
    "relationship_distress",
    "general_distress",
})

NEED_TAXONOMY = frozenset({
    "validation_normalization",
    "emotional_exploration",
    "gentle_reassurance",
    "practical_guidance",
    "grounding",
    "connection_support",
})

INTENT_TAXONOMY = frozenset({
    "emotional_expression",
    "help_seeking",
    "problem_solving",
    "self_reflection",
})

# ---------------------------------------------------------------------------
# [1] Subtype -> (theme, need, intent)  — highest priority
# ---------------------------------------------------------------------------

_SUBTYPE_MAP: Dict[str, Dict[str, str]] = {
    "anhedonia": {
        "theme": "loss_of_pleasure",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "burnout": {
        "theme": "general_distress",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "grief": {
        "theme": "general_distress",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "hopelessness": {
        "theme": "general_distress",
        "need": "gentle_reassurance",
        "intent": "emotional_expression",
    },
    "disappointment": {
        "theme": "general_distress",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "exam_anxiety": {
        "theme": "exam_pressure",
        "need": "gentle_reassurance",
        "intent": "help_seeking",
    },
    "performance_anxiety": {
        "theme": "fear_of_failure",
        "need": "gentle_reassurance",
        "intent": "self_reflection",
    },
    "social_anxiety": {
        "theme": "social_disconnection",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "generalized_anxiety": {
        "theme": "general_distress",
        "need": "grounding",
        "intent": "help_seeking",
    },
    "failure_fear": {
        "theme": "fear_of_failure",
        "need": "emotional_exploration",
        "intent": "self_reflection",
    },
    "rejection_fear": {
        "theme": "self_worth_doubt",
        "need": "validation_normalization",
        "intent": "self_reflection",
    },
    "future_fear": {
        "theme": "life_direction_uncertainty",
        "need": "gentle_reassurance",
        "intent": "self_reflection",
    },
    "health_fear": {
        "theme": "general_distress",
        "need": "gentle_reassurance",
        "intent": "help_seeking",
    },
    "guilt": {
        "theme": "self_worth_doubt",
        "need": "validation_normalization",
        "intent": "self_reflection",
    },
    "shame": {
        "theme": "self_worth_doubt",
        "need": "validation_normalization",
        "intent": "self_reflection",
    },
    "decision_uncertainty": {
        "theme": "life_direction_uncertainty",
        "need": "practical_guidance",
        "intent": "help_seeking",
    },
    "life_direction_uncertainty": {
        "theme": "life_direction_uncertainty",
        "need": "practical_guidance",
        "intent": "self_reflection",
    },
}

# ---------------------------------------------------------------------------
# [2] Keyword clusters — text-level refinement, third priority overall
#     Each entry: ([keywords], theme, need, intent)
#     Longer/more-specific phrases are listed first within each cluster.
# ---------------------------------------------------------------------------

_KEYWORD_RULES = [
    # loss_of_pleasure
    (
        [
            "hiçbir şeyden keyif", "keyif alam", "zevk alam", "hiçbir şey hissettirm",
            "tadı yok", "eskiden sevdiğim", "ilgi kayb", "içsel boşluk",
            "renksiz", "anlamsız",
        ],
        "loss_of_pleasure", "validation_normalization", "emotional_expression",
    ),
    # fear_of_failure
    (
        ["başarısız olmaktan", "başarısız ol", "hata yap", "yanlış yap", "yapamayacağım"],
        "fear_of_failure", "emotional_exploration", "self_reflection",
    ),
    # exam_pressure
    (
        ["sınav", "vize", "final", "yks", "lgs", "ösym", "yazılı"],
        "exam_pressure", "gentle_reassurance", "help_seeking",
    ),
    # social_disconnection
    (
        [
            "yalnız hissediyorum", "yalnız hissediyom", "yalnızım",
            "kimsem yok", "bağ kuramıyorum", "dışlanmış", "izole",
        ],
        "social_disconnection", "connection_support", "emotional_expression",
    ),
    # life_direction_uncertainty
    (
        [
            "ne yapacağımı bilmiyorum", "ne yapacağımı", "yönünü kaybettim",
            "hayatımın yönü", "nereye gidece", "boşluktayım", "neye yarar",
        ],
        "life_direction_uncertainty", "practical_guidance", "help_seeking",
    ),
    # self_worth_doubt
    (
        [
            "kendimi yetersiz", "değersiz hissediyorum", "hiçbir işe yaramıyorum",
            "özgüvenim yok", "kendime güvenemiyorum",
        ],
        "self_worth_doubt", "validation_normalization", "self_reflection",
    ),
    # relationship_distress
    (
        ["ilişkim bozuldu", "aramız açıldı", "tartıştık", "anlaşamıyoruz"],
        "relationship_distress", "emotional_exploration", "help_seeking",
    ),
    # explicit help_seeking
    (
        ["ne yapmalıyım", "ne yapabilirim", "nasıl başa çıkarım", "çözüm bulamıyorum"],
        "general_distress", "practical_guidance", "help_seeking",
    ),
    # self_reflection markers
    (
        [
            "neden böyleyim", "neden böyle hissediyorum", "anlam veremiyorum", "kendimi sorguluyorum",
            "neden hep böyle hissediyorum", "neden böyleyim", "neden ben",
            "kendimi anlamıyorum", "kendimi çözemedim", "neden sürekli", "neden tekrar tekrar",
        ],
        "general_distress", "emotional_exploration", "self_reflection",
    ),
]

# ---------------------------------------------------------------------------
# [3] Emotion -> (theme, need, intent) — broad category defaults
# ---------------------------------------------------------------------------

_EMOTION_MAP: Dict[str, Dict[str, str]] = {
    "sadness": {
        "theme": "general_distress",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "anxiety": {
        "theme": "general_distress",
        "need": "grounding",
        "intent": "help_seeking",
    },
    "fear": {
        "theme": "general_distress",
        "need": "gentle_reassurance",
        "intent": "emotional_expression",
    },
    "anger": {
        "theme": "general_distress",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "loneliness": {
        "theme": "social_disconnection",
        "need": "connection_support",
        "intent": "emotional_expression",
    },
    "motivation_loss": {
        "theme": "general_distress",
        "need": "validation_normalization",
        "intent": "emotional_expression",
    },
    "relationship_problems": {
        "theme": "relationship_distress",
        "need": "emotional_exploration",
        "intent": "help_seeking",
    },
    "self_esteem_issues": {
        "theme": "self_worth_doubt",
        "need": "validation_normalization",
        "intent": "self_reflection",
    },
    "stress": {
        "theme": "general_distress",
        "need": "practical_guidance",
        "intent": "help_seeking",
    },
    "guilt_shame": {
        "theme": "self_worth_doubt",
        "need": "validation_normalization",
        "intent": "self_reflection",
    },
    "uncertainty": {
        "theme": "life_direction_uncertainty",
        "need": "practical_guidance",
        "intent": "help_seeking",
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_theme_and_need(
    text: str,
    emotion: str,
    subtype: Optional[str] = None,
) -> Dict[str, str]:
    """
    Extracts psychological theme, need, and intent from a user turn.

    Priority chain (highest to lowest):
        1. Subtype-level lookup  (_SUBTYPE_MAP)
        2. Keyword-level rules   (_KEYWORD_RULES)
        3. Emotion-level lookup  (_EMOTION_MAP)
        4. Neutral fallback

    Parameters
    ----------
    text : str
        Raw user input text.
    emotion : str
        Primary emotion label (e.g. "sadness", "anxiety").
    subtype : Optional[str]
        Detected emotion subtype (e.g. "anhedonia", "exam_anxiety").

    Returns
    -------
    dict with keys "theme", "need", "intent" — all values are members of their
    respective taxonomy frozensets.
    """
    clean = turkish_lower(text or "").strip()
    sub = (subtype or "").strip().lower()
    emo = (emotion or "").strip().lower()

    base_res = None

    # [1] Subtype lookup — most specific, highest priority
    if sub and sub in _SUBTYPE_MAP:
        base_res = dict(_SUBTYPE_MAP[sub])

    # [2] Keyword rules — text-level refinement
    if not base_res:
        for keywords, theme, need, intent in _KEYWORD_RULES:
            if any(kw in clean for kw in keywords):
                base_res = {"theme": theme, "need": need, "intent": intent}
                break

    # [3] Emotion-level fallback
    if not base_res:
        if emo in _EMOTION_MAP:
            base_res = dict(_EMOTION_MAP[emo])

    # [4] Unknown / neutral fallback
    if not base_res:
        base_res = {
            "theme": "general_distress",
            "need": "emotional_exploration",
            "intent": "emotional_expression",
        }

    # [NEW] Check for explicit communicative intent overrides in the user's text
    intent_override = None

    # problem_solving: user wants to solve, choose, or decide a structured problem
    # Priority: problem_solving > self_reflection > help_seeking > emotional_expression
    problem_solving_kws = [
        # Original keywords
        "nasıl çözebilirim", "nasıl çözebileceğimi", "nasıl çözebiliriz", "nasıl düzelir",
        "karar veremiyorum", "karar vermekte", "seçim yapmakta", "seçim yapamıyorum",
        "seçim yapamadım", "karar veremedim", "ne yapacağıma karar", "hangisini seçmeliyim",
        "nasıl hallederim", "nasıl aşabilirim", "nasıl atlatabilirim", "nasıl kurtulabilirim",
        "nasıl başa çıkabilirim", "çözüm yolu", "çözüm bulmak", "çözüm yolları", "hangisini seçeyim",
        "nasıl karar verebilirim", "nasıl karar veririm", "arada kaldım", "kararsızım", "seçenek arasında",
        # Sprint 7.4 additions
        "hangi seçeneği seçmeliyim", "iki seçenek arasında kaldım", "hangisi daha mantıklı",
        "neyi seçmeliyim", "kararımı veremiyorum",
    ]

    # help_seeking: user asks for support, guidance, or next steps
    help_seeking_kws = [
        "ne yapmalıyım", "ne yapabilirim", "nasıl başa çıkarım", "çözüm bulamıyorum",
        "yol göster", "yardım et", "yardımcı olur musun", "tavsiye", "öneri",
        "ne yapmam gerek", "bana yardım", "önerin var mı", "destek ol", "bir yol göster",
        "ne yapacağımı bilmiyorum", "ne yapacagimi bilmiyorum", "yönünü kaybettim",
        "ne yapmamı önerirsin", "tavsiyen var mı",
        "yardımcı olabilir misin", "neler yapabilirim", "yardımcı ol", "bana yol göster",
        "önerin nedir", "tavsiyeniz nedir"
    ]

    # self_reflection: user is looking inward, trying to understand their feelings/behavior
    self_reflection_kws = [
        # Original keywords
        "neden böyleyim", "neden böyle hissediyorum", "neden hep böyle", "neden hep",
        "neden ben", "neden hissettiğimi", "anlam veremiyorum", "kendimi sorguluyorum",
        "kendi kendime soruyorum", "sorguluyorum", "fark ettim", "keşfetmek istiyorum",
        "anlamaya çalışıyorum", "neden kaynaklanıyor", "niye böyle", "acaba neden",
        "neden böyleyiz", "nedenini anlamak", "niye hep", "niye ben", "anlamlandıramıyorum",
        "kendi içimde", "kendimi anlamak",
        # Sprint 7.4 additions
        "neden hep böyle hissediyorum", "neden böyleyim", "kendimi anlamıyorum",
        "kendimi çözemedim", "neden sürekli", "neden tekrar tekrar",
    ]

    # Check for exact word matches for "neden" and "niye" as indicators of self_reflection
    words = clean.split()
    is_reflective_question = "neden" in words or "niye" in words

    # Intent priority enforcement: problem_solving > self_reflection > help_seeking > emotional_expression
    if any(kw in clean for kw in problem_solving_kws):
        intent_override = "problem_solving"
    elif any(kw in clean for kw in self_reflection_kws) or is_reflective_question:
        intent_override = "self_reflection"
    elif any(kw in clean for kw in help_seeking_kws):
        intent_override = "help_seeking"

    if intent_override:
        base_res["intent"] = intent_override

    return base_res
