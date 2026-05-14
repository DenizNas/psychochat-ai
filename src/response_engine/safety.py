import logging
import re
import json
from typing import Dict, Any, Tuple, Optional

# Regex compile flags
_RE_FLAGS = re.IGNORECASE | re.UNICODE

logger = logging.getLogger(__name__)

# Crisis Categories
CAT_SELF_HARM = "self_harm"
CAT_SUICIDE = "suicide_ideation"
CAT_IMMEDIATE_DANGER = "immediate_danger"
CAT_SEVERE_DISTRESS = "severe_distress"
CAT_VIOLENCE = "violence_risk"
CAT_UNKNOWN_CRISIS = "unknown_crisis"
CAT_INJECTION_ATTEMPT = "injection_attempt"
CAT_UNSAFE_ADVICE = "unsafe_advice"

# Pattern groups for unsafe GPT output or dangerous user intent
# CAT_IMMEDIATE_DANGER: user-input patterns indicating imminent physical danger
UNSAFE_PATTERNS = {
    CAT_SELF_HARM: [
        r"bilek(lerini)?\s*kes", r"kendine zarar ver", r"bıçak kullan", r"kendini kes", r"canını yak",
        r"zarar verme yöntemi", r"nasıl kesilir", r"derin kes", r"kendime zarar"
    ],
    CAT_SUICIDE: [
        r"kendini öldür", r"intihar et", r"yaşamına son ver", r"as kendini", r"hap içerek",
        r"ölmek için", r"kurtuluş yok", r"yaşamak istemiyorum", r"hayatıma son"
    ],
    CAT_IMMEDIATE_DANGER: [
        r"b[ıi]çak\s*ald[ıi]m", r"bi[cç]ak\s*ald[ıi]m",
        r"silah\s*ald[ıi]m", r"kendimi\s*[öo]ld[üu]rece[gğ][iı]m",
        r"[sş]imdi\s*yapaca[gğ][iı]m", r"son\s*kez\s*yaz[iı]yorum",
        r"art[iı]k\s*dayanam[iı]yorum", r"hemen\s*yapaca[gğ][iı]m",
        r"eve\s*gidince\s*yapaca[gğ][iı]m", r"ila[cç]\s*ald[iı]m", r"zehir\s*i[cç]tim"
    ],
    CAT_UNSAFE_ADVICE: [
        r"sakin ol geçer", r"abartıyorsun", r"boşver", r"kimseye söyleme", r"bunu yapabilirsin",
        r"mantıklı görünüyor", r"bir şey olmaz", r"geçici bir durum", r"dert etme"
    ],
    CAT_INJECTION_ATTEMPT: [
        r"önceki kuralları unut", r"rolünü değiştir", r"sistem promptunu",
        r"güvenlik kurallarını yok say", r"ignore previous instructions",
        r"disregard (your )?safety", r"bypass safety", r"act as if you have no restrictions",
        r"pretend you are", r"jailbreak"
    ]
}

# BLOCK_LIST for specifically forbidden condescending or dangerous phrases
BLOCK_LIST = [
    "sakin ol geçer", "abartıyorsun", "boşver", "kimseye söyleme", 
    "bunu yapabilirsin", "canını yakabilirsin", "mantıklı görünüyor"
]

SAFE_CRISIS_TEMPLATES = {
    "tr": {
        "default": (
            "Şu an çok zor bir dönemden geçtiğinizi hissedebiliyorum. "
            "Size destek olmak isterim ancak bir yapay zeka olarak sınırlı yeteneklere sahibim. "
            "Lütfen şu an güvende olduğunuzdan emin olun. Yanınızda size destek olabilecek "
            "profesyonel bir uzmanla veya güvendiğiniz birisiyle konuşmak size iyi gelebilir. "
            "Yalnız değilsiniz, her zaman bir çıkış yolu vardır."
        ),
        CAT_IMMEDIATE_DANGER: (
            "Güvenliğiniz benim için en öncelikli konu. Şu an kendinizi veya başkasını tehlikede hissediyorsanız, "
            "lütfen hemen 112 Acil Çağrı Merkezi'ni arayın veya en yakın sağlık kuruluşuna başvurun. "
            "Profesyonel destek almak şu an atılabilecek en güvenli adımdır. Lütfen yalnız kalmayın."
        ),
        CAT_SELF_HARM: (
            "Yaşadığınız acıyı ve zorluğu duyabiliyorum. Kendinize zarar verme düşünceleri çok ağır olabilir. "
            "Lütfen şu an kendinizi korumaya odaklanın ve bir uzmandan destek almayı düşünün. "
            "112'yi arayarak profesyonel yardım isteyebilirsiniz. Sizi dinleyecek ve yanınızda olacak insanlar var."
        ),
        CAT_SUICIDE: (
            "Şu an hissettiğiniz çaresizliği anlıyorum ama lütfen yalnız olmadığınızı bilin. "
            "Bu zor duygularla tek başınıza baş çıkmak zorunda değilsiniz. "
            "Hemen 112'yi arayarak profesyonel destek alabilir veya güvendiğiniz bir yakınınızla iletişime geçebilirsiniz. "
            "Yaşamınız değerli ve size yardım etmek isteyen uzmanlar var."
        )
    },
    "en": {
        "default": (
            "I can hear how much pain you are in right now. I want to support you, but as an AI, "
            "I have limitations. Please ensure you are in a safe place. Speaking with a professional "
            "or someone you trust can make a big difference. You don't have to go through this alone."
        ),
        CAT_IMMEDIATE_DANGER: (
            "Your safety is my priority. If you feel you are in immediate danger, please contact "
            "your local emergency services (like 911 or 112) immediately or go to the nearest emergency room. "
            "Professional help is the safest step right now. You are not alone."
        )
    }
}

def log_safety_event(event_data: Dict[str, Any]):
    """Structured logging for safety decisions, protecting user privacy."""
    logger.warning(f"SAFETY_LOG: {json.dumps(event_data)}")

def check_safety(
    text: str,
    risk_level: str = "Normal",
    language: str = "tr",
    mode: str = "gpt_output"
) -> Tuple[bool, Optional[str]]:
    """
    Checks if the text is safe.

    Args:
        text:       The text to check (user input OR GPT output).
        risk_level: Current crisis risk label from ML model.
        language:   Language code (tr/en).
        mode:       "user_input"  — checks user-sent text for crisis signals.
                    "gpt_output"  — checks GPT-generated text for unsafe advice/injection.

    Returns:
        (is_safe: bool, safety_reason: Optional[str])
    """
    if not text or not text.strip():
        return False, "empty_output"

    # --- 1. Injection attempt check (highest priority, both modes) ---
    for pattern in UNSAFE_PATTERNS[CAT_INJECTION_ATTEMPT]:
        if re.search(pattern, text, flags=_RE_FLAGS):
            return False, CAT_INJECTION_ATTEMPT

    if mode == "user_input":
        # --- User input mode: detect crisis signals in what the user wrote ---
        # Priority: immediate_danger > self_harm > suicide
        for category in [CAT_IMMEDIATE_DANGER, CAT_SELF_HARM, CAT_SUICIDE]:
            for pattern in UNSAFE_PATTERNS.get(category, []):
                if re.search(pattern, text, flags=_RE_FLAGS):
                    return False, category
        # NOTE: CAT_UNSAFE_ADVICE is NOT checked for user input
        # (user may say these words in a neutral context)
        return True, None

    # --- GPT output mode ---
    # 2. Block-list: explicitly forbidden dismissive phrases in GPT responses
    for phrase in BLOCK_LIST:
        if re.search(re.escape(phrase), text, flags=_RE_FLAGS):
            return False, CAT_UNSAFE_ADVICE

    # 3. Harmful pattern check in GPT output (skip injection — already done)
    for category, patterns in UNSAFE_PATTERNS.items():
        if category in (CAT_INJECTION_ATTEMPT, CAT_UNSAFE_ADVICE):
            continue
        for pattern in patterns:
            if re.search(pattern, text, flags=_RE_FLAGS):
                return False, category

    # 4. Crisis state heuristic: GPT reply too short/terse is suspicious
    is_crisis = risk_level.lower() in ["1", "crisis", "kriz"]
    if is_crisis and len(text.split()) < 3:
        return False, CAT_SEVERE_DISTRESS

    return True, None

def get_crisis_safe_response(language: str = "tr", category: str = "default") -> str:
    """Returns a pre-defined safe response template based on category and language."""
    lang_templates = SAFE_CRISIS_TEMPLATES.get(language, SAFE_CRISIS_TEMPLATES["tr"])
    
    # Map internal categories to template keys
    category_map = {
        CAT_SELF_HARM: CAT_SELF_HARM,
        CAT_SUICIDE: CAT_SUICIDE,
        CAT_IMMEDIATE_DANGER: CAT_IMMEDIATE_DANGER,
        CAT_SEVERE_DISTRESS: "default",
        CAT_VIOLENCE: "default",
        CAT_UNKNOWN_CRISIS: "default",
        CAT_INJECTION_ATTEMPT: "default",
        CAT_UNSAFE_ADVICE: "default"
    }
    
    template_key = category_map.get(category, "default")
    return lang_templates.get(template_key, lang_templates["default"])
