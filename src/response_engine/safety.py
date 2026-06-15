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
        "default": [
            "Şu an çok zor bir dönemden geçtiğinizi hissedebiliyorum. Size destek olmak isterim ancak bir yapay zeka olarak sınırlı yeteneklere sahibim. Lütfen şu an güvende olduğunuzdan emin olun. Yanınızda size destek olabilecek profesyonel bir uzmanla veya güvendiğiniz birisiyle konuşmak size iyi gelebilir. Yalnız değilsiniz, her zaman bir çıkış yolu vardır.",
            "Yaşadığınız zor durumun yükünü hissedebiliyorum. Size yardımcı olmak isterim fakat bir yapay zeka asistanı olarak klinik veya profesyonel destek sağlayamam. Lütfen güvenliğinize dikkat edin, güvendiğiniz biriyle veya bir uzmanla bu duyguları paylaşmak çok yararlı olabilir. Yanınızda duracak insanlar olduğunu unutmayın.",
            "Şu an içinden geçtiğiniz sürecin ne kadar ağır olduğunu duyabiliyorum. Size eşlik etmek isterim ancak sınırları olan bir yapay zekayım. Lütfen kendinizi güvende hissettirecek adımlar atın. Profesyonel bir psikoloğa, destek hatlarına veya bir yakınınıza ulaşmanız size çok yardımcı olabilir. Destek almak için yalnız olmadığınızı kendinize hatırlatın."
        ],
        CAT_IMMEDIATE_DANGER: [
            "Güvenliğiniz benim için en öncelikli konu. Şu an kendinizi veya başkasını tehlikede hissediyorsanız, lütfen hemen 112 Acil Çağrı Merkezi'ni arayın veya en yakın sağlık kuruluşuna başvurun. Profesyonel destek almak şu an atılabilecek en güvenli adımdır. Lütfen yalnız kalmayın.",
            "Şu an hayati bir risk veya tehlike altındaysanız, lütfen hemen 112 Acil Çağrı Merkezi'ni veya 114 Psikolojik Destek Hattı'nı arayın. En yakın hastanenin acil servisine başvurmanız da çok önemlidir. Lütfen güvende kalmak için hemen profesyonel ekiplere ulaşın.",
            "Kendinizi veya çevrenizdekileri tehlikede hissettiğiniz anlarda, en doğru adım profesyonel yardım almaktır. Lütfen vakit kaybetmeden 112 Acil Servis hattını arayın ya da en yakın sağlık kuruluşuna yönelin. Sizi destekleyecek uzmanlar görev başındadır, lütfen onlarla iletişime geçin."
        ],
        CAT_SELF_HARM: [
            "Yaşadığınız acıyı ve zorluğu duyabiliyorum. Kendinize zarar verme düşünceleri çok ağır olabilir. Lütfen şu an kendinizi korumaya odaklanın ve bir uzmandan destek almayı düşünün. 112'yi arayarak profesyonel yardım isteyebilirsiniz. Sizi dinleyecek ve yanınızda olacak insanlar var.",
            "Kendinize zarar verme düşünceleriyle baş etmek tek başınıza çok zor olabilir. Lütfen kendinizi güvende tutacak bir alana geçin ve hemen 112'yi ya da 114 Psikolojik Destek Hattı'nı arayın. Bir profesyonelden yardım istemek şu an yapabileceğiniz en cesurca ve güvenli adımdır.",
            "İçinizdeki bu büyük acının kendinize zarar verme isteği uyandırdığını hissediyorum. Lütfen bu zor anı atlatabilmek için hemen acil hatlardan (112) veya psikolojik danışma hatlarından (114) profesyonel destek talep edin. Bu süreci tek başınıza sırtlanmak zorunda değilsiniz."
        ],
        CAT_SUICIDE: [
            "Şu an hissettiğiniz çaresizliği anlıyorum ama lütfen yalnız olmadığınızı bilin. Bu zor duygularla tek başınıza baş çıkmak zorunda değilsiniz. Hemen 112'yi arayarak profesyonel destek alabilir veya güvendiğiniz bir yakınınızla iletişime geçebilirsiniz. Yaşamınız değerli ve size yardım etmek isteyen uzmanlar var.",
            "Yoğun bir çaresizlik hissettiğinizi duyuyorum fakat yalnız olmadığınızı ve destek alabileceğinizi hatırlatmak isterim. Lütfen hemen 112 Acil Servis'i veya 114 Psikolojik Destek Hattı'nı arayın. Bu sıkıntıları aşmanızda size rehberlik edecek uzmanlarla konuşmak yaşamınız için en güvenli adımdır.",
            "Bu zor duyguların içinde kaybolmuş hissetmeniz çok insani, ancak her zaman bir çıkış yolu vardır. Lütfen hemen 112 Acil hattına ya da 114 Psikolojik Destek hattına ulaşarak profesyonel yardım isteyin. Kendinize destek alma şansı verin, yaşamınız çok değerlidir."
        ]
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
    res = lang_templates.get(template_key, lang_templates["default"])
    if isinstance(res, list):
        import random
        return random.choice(res)
    return res

def classify_crisis_level(text: str, risk_label: str) -> str:
    """
    Classifies the crisis level of the user input into:
    none, low, medium, high, imminent
    """
    if not text or not text.strip():
        return "none"

    text_lower = text.lower()
    
    # 1. Imminent checks (Immediate intent or danger)
    imminent_keywords = [
        r"kendime zarar vermek üzereyim",
        r"kendime zarar veriyorum",
        r"birine zarar vereceğim",
        r"birine zarar verecegim",
        r"birini öldüreceğim",
        r"birini öldürecegim",
        r"kendimi asıyorum",
        r"kendimi asacağım",
        r"kendimi asacagım",
    ]
    for pat in imminent_keywords:
        if re.search(pat, text_lower, flags=_RE_FLAGS):
            return "imminent"
            
    for pat in UNSAFE_PATTERNS.get(CAT_IMMEDIATE_DANGER, []):
        if re.search(pat, text_lower, flags=_RE_FLAGS):
            return "imminent"
            
    # 2. High checks (Suicidal ideation, self-harm intent, serious violence ideation)
    high_keywords = [
        r"yaşamak istemiyorum",
        r"yaşamak\s*anlamsız",
        r"ölmek istiyorum",
        r"intihar etmek istiyorum",
        r"intihar\s*düşünüyorum",
        r"kendimi öldürmeyi düşünüyorum",
        r"yaşamıma son vermek",
        r"hayatıma son vermek",
        r"kendime zarar vermek istiyorum",
        r"kendimi kesmek istiyorum",
        r"birini öldürmeyi düşünüyorum",
        r"birine zarar vermeyi düşünüyorum",
    ]
    for pat in high_keywords:
        if re.search(pat, text_lower, flags=_RE_FLAGS):
            return "high"
            
    for category in [CAT_SUICIDE, CAT_SELF_HARM]:
        for pat in UNSAFE_PATTERNS.get(category, []):
            if re.search(pat, text_lower, flags=_RE_FLAGS):
                return "high"
                
    # 3. Medium check: if ML model predicts crisis but no keyword overrides it
    is_model_crisis = str(risk_label).lower() in ["kriz", "1", "crisis"]
    if is_model_crisis:
        return "medium"
        
    # 4. Low check: check for general sadness, anxiety, distress terms
    distress_indicators = [
        r"kötü\s*hissediyorum", r"kötüyüm", r"kaygılıyım", r"üzgünüm", 
        r"ağlamak", r"stresliyim", r"çaresiz", r"canım\s*sıkkın"
    ]
    for pat in distress_indicators:
        if re.search(pat, text_lower, flags=_RE_FLAGS):
            return "low"
            
    return "none"

def get_custom_crisis_response(crisis_level: str, text: str) -> str:
    """
    Generates a concise safety-first crisis response in Turkish.
    """
    text_lower = text.lower()
    is_violence = any(re.search(pat, text_lower, flags=_RE_FLAGS) for pat in [r"birine zarar", r"birini öldür", r"zarar vereceğim", r"zarar verecegim"])
    
    if is_violence:
        ack = "Şu an yoğun bir öfke veya zarar verme düşüncesiyle karşı karşıya olduğunu duyuyorum. Güvende kalman ve çevrendekilerin güvenliği en önemli konudur."
    else:
        ack = "Şu an çok zor bir süreçten geçtiğini ve büyük bir acı hissettiğini duyuyorum. Güvende kalman en öncelikli konudur."
        
    response_parts = [
        ack,
        "Şu an yalnız kalmaman önemli.",
        "Türkiye'deysen 112 Acil Çağrı Merkezi'ni arayabilirsin. Eğer başka bir yerdeysen, bulunduğun ülkedeki acil yardım hattını arayabilirsin.",
        "Lütfen hemen yakınında olan veya güvendiğin birini arayarak yanında kalmasını iste."
    ]
    
    is_imminent_harm = (crisis_level == "imminent")
    if is_imminent_harm and not is_violence:
        response_parts.append("Kendine zarar vermek için kullanabileceğin tüm araçlardan veya maddelerden hemen uzaklaşmanı öneririm.")
        
    response_parts.append("Şu anda kendine zarar verme ihtimalin yakın mı?")
    
    return " ".join(response_parts)
