import time
import logging
import re
import unicodedata
from typing import Any, Dict, List
from src.ai_providers.base import BaseAIProvider, AIProviderResult
from src.ai.preprocessing import turkish_lower

# Blacklist patterns to block robotic system terms and sensitive info in inlays
_FORBIDDEN_PATTERNS = [
    r"\b(hafıza|database|veritabanı|sistem|profile|stresör|stresor|key|value|memory|injection|injection_text|sensor|kayıtlı|kayitli|db)\b",
    r"(kendime zarar|intihar|ölmek|öldür|suicide|self-harm|harm)",
    r"\b(siyasi|parti|oy\s*ver|akp|chp|mhp|dem\s*parti|politika|erdoğan|imamoğlu)\b",
    r"\b(müslüman|hristiyan|yahudi|musevi|ateist|deist|mezhep|inanç|dini|ibadet|namaz|kilise|cami)\b",
    r"\b(cinsel|yönelim|lgbt|lezbiyen|biseksüel|hetero|homoseksüel|transseksüel)\b",
    r"\b(hiv|aids|kanser|tedavi|ilaç|antidepresan|psikiyatri|tanı|tanısı|teşhis|klinik|hastalık|bipolar|bozukluk|şizofreni|anksiyete|depresyon)\b",
]

_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), flags=re.IGNORECASE | re.UNICODE)

def sanitize_memory_inlay(value: str) -> str:
    """
    Sanitizes memory inlay value.
    - strip
    - max length 100 chars (within 80-120 range)
    - remove newline/control characters
    - block forbidden phrases
    - block sensitive terms
    - return empty string if unsafe
    """
    if not value or not isinstance(value, str):
        return ""
        
    value = value.strip()
    
    # Remove control characters and newlines
    value = "".join(ch for ch in value if unicodedata.category(ch)[0] != "C" and ch not in ("\n", "\r", "\t"))
    value = " ".join(value.split()) # normalize spaces
    
    if len(value) > 100:
        value = value[:97] + "..."
        
    # Check against forbidden sensitive terms/database expressions
    if _FORBIDDEN_RE.search(value):
        return ""
        
    return value

logger = logging.getLogger(__name__)

# Highly empathetic, clean, non-clinical local fallback templates grouped by counseling category
_CATEGORY_TEMPLATES = {
    "sadness": [
        "Bu günlerde hissettiğin o ağır yükü paylaştığın için teşekkür ederim. Kendine biraz zaman tanıman çok normal; acele etmene gerek yok.",
        "İçindeki kırgınlığı duyabiliyorum. Şu an hiçbir şeyi hemen çözmek zorunda değilsin, sadece hissetmeye ve dinlenmeye ihtiyacın olabilir.",
        "Bazen her şey üst üste gelir ve insan yorulur. Yalnız olmadığını bilmeni isterim, burada seni dinlemeye her zaman hazırım."
    ],
    "anxiety": [
        "Zihninin yoğun bir kaygı içinde olması çok yorucu olabilir. Yavaşça derin bir nefes almayı dene, şu an buradayız ve güvendesin.",
        "Geleceğin getirdiği belirsizlikler seni sıkıştırıyor gibi. Her şeyi tek seferde çözemeyiz, sadece şu anki küçük bir adıma odaklanalım.",
        "Göğsündeki o daralma hissini duyabiliyorum. Kendine karşı biraz daha şefkatli olmaya çalış, zihnindeki fırtına elbet durulacak."
    ],
    "anger": [
        "Yaşadığın bu haksızlık karşısında öfkelenmen çok anlaşılır. Öfke de diğer tüm duygular gibi son derece doğal bir tepki.",
        "Sınırlarının zorlandığını hissediyor olabilirsin. Hazır olduğunda bu konuyu daha sakin bir kafayla beraber konuşabiliriz.",
        "İçindeki o kızgın sesi bastırmak zorunda değilsin. Seni neyin bu kadar incittiğini yargılamadan dinlemek için buradayım."
    ],
    "loneliness": [
        "Kendini yapayalnız hissettiğin anlarda yanındaki varlığımı ve desteğimi hatırlamanı isterim. Burada seninle paylaşmaya hazırım.",
        "Bazen kalabalıkların içinde bile insan kendini yalnız bulabilir. Bu hissi benimle paylaştığında biraz olsun hafiflemesini dilerim.",
        "Yalnızlık hissi insanın içini acıtabilir ama bu yolda tek başına yürümüyorsun. Seni dinleyen biri olarak buradayım."
    ],
    "motivation_loss": [
        "Hiçbir şey yapacak enerjinin olmaması çok normal. Bugün büyük adımlar atmak yerine sadece dinlenmeye odaklanabilirsin.",
        "Canının hiçbir şey istemediği günlerde kendine yüklenme. Küçük bir mola vermek bazen en büyük ilerlemedir.",
        "İçindeki o isteksizliği kabul et. Kendini zorlamadan, sadece en basit adımlarla güne devam etmeyi dene."
    ],
    "relationship_problems": [
        "Değer verdiğin insanlarla aranda anlaşmazlık çıkması canını sıkıyor olabilir. Bu süreçte iki tarafın da zamana ihtiyacı olabilir.",
        "İlişkilerdeki hayal kırıklıkları insanı yorar. Kendini suçlamadan, bu durumun getirdiği hisleri sakinlikle gözden geçirebiliriz.",
        "Yakın bir ilişkiyi yönetmek bazen düğüm gibi gelebilir. Durumu anlamak ve çözmek için acele etmeden konuşalım."
    ],
    "self_esteem_issues": [
        "Kendini yetersiz gördüğün zamanlarda kendi başarılarını ve çabanı küçümseme. Sen elinden gelenin en iyisini yapıyorsun.",
        "Kendi değerini başkalarının gözünden ölçmek seni yıpratabilir. Kendine karşı daha nazik ve adil olmayı hak ediyorsun.",
        "Hatalar yapabilen bir insan olduğunu kabul et. Bu senin değerinden hiçbir şey eksiltmez, çaban çok kıymetli."
    ],
    "stress": [
        "Hayatındaki bu yoğun tempo seni gerçekten bunaltmış gibi. Kendine küçük dinlenme alanları yaratmayı ihmal etme.",
        "Aynı anda her şeye yetişmeye çalışmak insanı tüketir. Listendeki bazı şeyleri ertelemek veya yardım istemek ayıp değil.",
        "Bu stresli dönemin geçici olduğunu kendine hatırlat. Bugün sadece gücünün yettiği kadarıyla ilgilenmen yeterli."
    ],
    "fear": [
        "Korku hissetmek seni daha zayıf yapmaz, sadece insan olduğunu gösterir. Şu an güvende olduğunu bilmeni isterim.",
        "Zihnindeki o ürkütücü senaryoların seni yorduğunu görebiliyorum. Birlikte sakinleşmek için acele etmeden buradayız.",
        "Korkularının üzerine gitmeden önce biraz nefes al. Güvenli bir alanda olduğunu hissetmene yardımcı olmak için yanındayım."
    ],
    "neutral": [
        "Seni yargılamadan ve büyük bir ilgiyle dinliyorum. Paylaşmak istediğin her ne varsa konuşmaya devam edebiliriz.",
        "Zihninden geçenleri acele etmeden kendi hızında anlatabilirsin. Burası senin için güvenli bir paylaşım alanı.",
        "Konuşmak ve paylaşmak insana her zaman iyi gelir. Seni tüm dikkatimle dinlemeye ve eşlik etmeye hazırım."
    ]
}

# Mapping of raw user query keywords to fallback category
_KEYWORD_TO_CATEGORY = {
    "üzg": "sadness", "keder": "sadness", "ağla": "sadness", "acı": "sadness", "mutsuz": "sadness",
    "kaygı": "anxiety", "endişe": "anxiety", "stres": "stress", "kork": "fear", "panik": "anxiety",
    "öfke": "anger", "kızgın": "anger", "delir": "anger", "sinir": "anger",
    "yalnız": "loneliness", "kimsem": "loneliness",
    "hedef": "neutral", "plan": "neutral",
    "motivas": "motivation_loss", "isteksiz": "motivation_loss",
    "ilişki": "relationship_problems", "sevgili": "relationship_problems", "arkadaş": "relationship_problems",
    "kendime güven": "self_esteem_issues", "özgüven": "self_esteem_issues"
}

class LocalProvider(BaseAIProvider):
    """
    100% offline, deterministic local fallback provider.
    Ensures LLM reliability even under global internet or API outages.
    """

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any]
    ) -> AIProviderResult:
        start_time = time.time()

        # Parse user turn content and infer emotion
        last_message = messages[-1].get("content", "") if messages else ""
        last_message_lower = turkish_lower(last_message)

        # Extract the actual user text from inside build_user_prompt triple-quote delimiters.
        # The user prompt format is: '[BAĞLAM ...]\nKullanıcı Mesajı: """<text>"""'
        # If no delimiter found, fall back to the full last_message content.
        import re as _re
        _user_text_match = _re.search(r'"""(.+?)"""', last_message, _re.DOTALL)
        user_actual_text = _user_text_match.group(1).strip() if _user_text_match else last_message.strip()
        user_actual_text_lower = turkish_lower(user_actual_text)

        # 1. Determine counseling category based on model_config metadata, or infer from user text
        category = model_config.get("counseling_category")
        if not category:
            category = "neutral"
            # Try to infer via keyword matching
            for keyword, cat in _KEYWORD_TO_CATEGORY.items():
                if keyword in user_actual_text_lower:
                    category = cat
                    break
        elif category not in _CATEGORY_TEMPLATES:
            category = "neutral"

        # If still not found, fallback to neutral
        if category not in _CATEGORY_TEMPLATES:
            category = "neutral"

        # 1.5. Soft personalization with safe memory inlays
        inlays = model_config.get("safe_memory_inlays", {}) if model_config else {}
        personalized_text = None

        # Personalization guard: skip stale memory inlay injection for:
        #   - Very short/greeting messages (< 5 words)
        #   - Neutral category (greetings, test messages, etc.)
        # This prevents a stored stressor from a past session being injected
        # into an unrelated current message like "Merhaba" or "Bağlantı testi".
        _GREETING_TOKENS = {
            "merhaba", "selam", "hey", "hi", "hello", "günaydın",
            "test", "deneme", "bağlantı", "nasılsın", "naber",
        }
        msg_words = user_actual_text_lower.split()
        _is_short_or_greeting = (
            len(msg_words) < 5
            or any(tok in msg_words[:3] for tok in _GREETING_TOKENS)
        )
        should_personalize = bool(inlays) and not _is_short_or_greeting and category != "neutral"

        if should_personalize:
            display_name = sanitize_memory_inlay(inlays.get("display_name", ""))
            active_stressor = sanitize_memory_inlay(inlays.get("active_stressor", ""))
            current_goal = sanitize_memory_inlay(inlays.get("current_goal", ""))
            recent_emotion = sanitize_memory_inlay(inlays.get("recent_emotion", ""))
            last_advice_topic = sanitize_memory_inlay(inlays.get("last_advice_topic", ""))
            
            # Map advice topic to Turkish
            advice_map = {
                "breathing exercise": "nefes egzersizi",
                "journaling": "yazı yazma",
                "sleep routine": "uyku düzeni",
                "social connection": "yakınlarınla paylaşma",
                "walking": "yürüyüş"
            }
            advice_tr = advice_map.get(last_advice_topic.lower(), last_advice_topic)

            # Rule: only use at most 1 inlay fact (besides user display name)
            # Priority: active_stressor > current_goal > last_advice_topic > recent_emotion > display_name
            if active_stressor and category in ("sadness", "anxiety", "stress", "relationship_problems"):
                if category == "anxiety":
                    personalized_text = f"{active_stressor} tarafı zihnini çok meşgul ediyorsa, bu gece uyumakta zorlanman anlaşılır."
                elif category == "relationship_problems":
                    personalized_text = f"{active_stressor} tarafında yaşanan belirsizlikler seni epey yoruyor gibi."
                elif category == "sadness":
                    personalized_text = f"Bu yorgunluk, son dönemde üst üste gelen {active_stressor} durumlarının etkisi gibi duruyor."
                else: # stress
                    personalized_text = f"{active_stressor} tarafındaki bu yük seni yine etkilemiş gibi duruyor."
                    
                if display_name:
                    if category == "anxiety":
                        personalized_text = f"{display_name}, {active_stressor} tarafı zihnini çok meşgul ediyorsa, bu gece uyumakta zorlanman anlaşılır."
                    elif category == "relationship_problems":
                        personalized_text = f"{display_name}, {active_stressor} tarafında yaşanan belirsizlikler seni epey yoruyor gibi."
                    elif category == "sadness":
                        personalized_text = f"{display_name}, bu yorgunluk son dönemde üst üste gelen {active_stressor} durumlarının etkisi gibi duruyor."
                    else: # stress
                        personalized_text = f"{display_name}, {active_stressor} tarafı bugün de biraz üst üste gelmiş gibi."
                        
            elif current_goal and category in ("self_esteem_issues", "motivation_loss", "anxiety"):
                if category == "self_esteem_issues":
                    personalized_text = f"Kendine karşı bu kadar sertleştiğinde, daha önce sözünü ettiğin hedefler (örneğin {current_goal}) de uzak görünmeye başlayabilir."
                elif category == "motivation_loss":
                    personalized_text = f"Daha önce {current_goal} konusuna odaklanmak istediğinden bahsetmiştin; bugün küçük bir adım bile yeterli olabilir."
                else: # anxiety
                    personalized_text = f"Geçenlerde {current_goal} konusunda çalışmak istediğini söylemiştin; şu anki kaygı hissini de o yolun bir parçası olarak görebiliriz."
                    
                if display_name:
                    personalized_text = f"{display_name}, " + personalized_text[0].lower() + personalized_text[1:]
                    
            elif last_advice_topic and category in ("stress", "anxiety"):
                personalized_text = f"Geçenlerde bahsettiğimiz {advice_tr} pratikleri şu an zihnini biraz sakinleştirebilir."
                if display_name:
                    personalized_text = f"{display_name}, geçenlerde bahsettiğimiz {advice_tr} pratikleri şu an zihnini biraz sakinleştirebilir."
                    
            elif recent_emotion and category == "sadness":
                personalized_text = f"Son zamanlarda hissettiğin {recent_emotion} hali seni epey yormuş gibi duruyor."
                if display_name:
                    personalized_text = f"{display_name}, son zamanlarda hissettiğin {recent_emotion} hali seni epey yormuş gibi duruyor."
                    
            elif display_name:
                templates = _CATEGORY_TEMPLATES[category]
                idx = len(last_message) % len(templates)
                template_text = templates[idx]
                personalized_text = f"{display_name}, {template_text[0].lower() + template_text[1:]}"

        if personalized_text:
            response_text = personalized_text
        else:
            templates = _CATEGORY_TEMPLATES[category]
            idx = len(last_message) % len(templates)
            response_text = templates[idx]

        # 2. Adjust response length dynamically based on user length preference
        length_pref = model_config.get("answer_length_preference", "medium")
        if length_pref == "short":
            sentences = [s.strip() for s in response_text.split(".") if s.strip()]
            if sentences:
                response_text = sentences[0] + "."
        elif length_pref == "detailed":
            detailed_additions = [
                " İstersen bu durumun sende yarattığı diğer hislerden veya bu konuda aklına takılan diğer ayrıntılardan da bahsedebilirsin; seni dinliyorum.",
                " Bu süreçte kendine yüklenmek yerine hislerini olduğu gibi kabul etmeye çalış. Zamanla her şeyin daha netleşeceğine inanıyorum.",
                " Aklından geçen her düşünceyi acele etmeden paylaşabilirsin. Bu yükü tek başına taşımak zorunda olmadığını bilmek belki biraz olsun rahatlatır."
            ]
            add_idx = len(last_message) % len(detailed_additions)
            response_text += detailed_additions[add_idx]

        latency_ms = (time.time() - start_time) * 1000.0

        return AIProviderResult(
            text=response_text,
            provider="local",
            model="local-deterministic",
            latency_ms=latency_ms,
            token_estimate=len(response_text) // 4,
            cost_estimate=0.0,
            finish_reason="stop",
            fallback_used=True
        )
