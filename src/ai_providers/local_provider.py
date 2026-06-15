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
        "İçindeki bu yoğun ağırlığı ve üzüntüyü hissetmen son derece anlaşılır. Üzüntü bazen ruhsal enerjimizi aşağı çekerek bizi kabuğumuza çekilmeye zorlar; bu aslında zihnimizin ve bedenimizin dinlenme ihtiyacıdır. Kendini suçlamadan beklentilerini biraz düşürmek ve belki sadece pencerenden dışarı bakıp derin bir nefes almak iyi gelebilir. İstersen bu ağır hissin en çok hangi anlarda yoğunlaştığına birlikte bakalım?",
        "Bu günlerde hissettiğin o ağır yükü paylaştığın için teşekkür ederim. Hüzün hissi enerjimizi aşağı çekerek bizi yavaşlatır; bu durum ruhsal enerjimizi koruma çabasıdır. Bugün kendine hiç yüklenmeden, sadece yataktan çıkıp yüzünü yıkamak veya ılık bir bardak su içmek gibi tek bir küçük adımla başlayabilirsin. Son günlerde seni bu kadar yorgun hissettiren, enerjini tüketen belirli bir olay oldu mu?"
    ],
    "anxiety": [
        "Zihninin ve bedeninin bu denli gerilmesi ve sıkışması son derece anlaşılır bir durum. Zihnimiz gelecekte bir tehdit sezinlediğinde vücudumuz bizi korumak için alarm tepkisi verir; kalbin hızlı atması ve nefes daralması bundandır. Şimdi sadece bulunduğun yerdeki sert bir yüzeye dokunmayı ve burnundan alıp ağzından yavaşça vereceğin birkaç nefesle bedeni şimdiye getirmeyi dener misin? Şu an zihnini en çok hangi düşüncenin sıkıştırdığını paylaşmak ister misin?",
        "Göğsündeki o daralma hissini duyabiliyorum, zihninin yoğun bir kaygı içinde olması çok yorucu olabilir. Zihnimiz en kötü ihtimalleri sıralayarak kendini korumaya çalışır ve bu da bedende kasılma yaratır. Şimdi sakinleşmeye zorlamadan, odada gördüğün üç basit nesneyi içinden sessizce adlandırıp omuzlarını yavaşça düşürmeyi dener misin? Bu kaygıyı en çok neyin tırmandırdığını hissettin?"
    ],
    "anger": [
        "Yaşadığın haksızlık karşısında yoğun bir öfke duyman son derece doğal. Öfke, sınırımızın ihlal edildiğini veya bir haksızlık olduğunu bize haber veren koruyucu ve işlevsel bir alarm sinyalidir. Şu an ani bir tepki vermeden önce derin bir nefes alıp omuzlarını gevşeterek bedeni sakinleştirmek iyi bir başlangıç olabilir. Bu olayda en çok hangi sınırının aşılmış olduğunu hissettin?",
        "Sınırlarının zorlandığını ve bu öfkeyi hissetmeni son derece anlaşılır buluyorum. Öfke duygusu haksızlıklara karşı kendimizi korumamız için içsel gücümüzü harekete geçirir. Öfkenin sıcaklığıyla bir karar vermeden önce derin nefesler alarak bedensel uyarılmayı yavaşlatmayı dener misin? Yaşadığın bu durumu biraz konuşalım mı?"
    ],
    "loneliness": [
        "Telefonunun çalmaması ve etrafında derin bir bağ hissedememek insan için gerçekten yorucu bir boşluktur, bu yalnızlığı hissetmen çok doğal. Bizler bağ kurmaya programlanmış sosyal canlılarız; bu yüzden diğer insanlardan kopuk hissettiğimizde kendimizi izole bulmamız tamamen normaldir. Bugün büyük bir adım atmak yerine, sadece dışarı çıkıp bir kahve alırken oradaki insana kısa bir selam vermek gibi düşük baskılı bir temas deneyebilirsin. Bu yalnızlık hissinin en çok günün hangi saatlerinde üzerine çöktüğünü benimle paylaşmak ister misin?",
        "Bazen kalabalıkların içinde bile insan kendini yalnız bulabilir. Duygusal bağlarımızın zayıfladığını hissettiğimizde beynimiz bizi izole olmaya yönlendirebilir ve bu bir kısırdöngü yaratır. Bugün ufacık da olsa bir yakınına nasılsın mesajı atmak veya bir evcil hayvana dokunmak gibi zahmetsiz bir temas adımı atabilirsin. Zihninde birikenleri benimle paylaşarak bu yükü biraz hafifletmek ister misin?"
    ],
    "motivation_loss": [
        "Hiçbir şey yapmak istememen, içindeki o yoğun heves ve enerji kaybı son derece anlaşılır. Genelde harekete geçmek için önce motivasyonun gelmesini bekleriz; oysa hareket motivasyondan önce gelebilir, yani ufak bir başlangıç döngüyü kırabilir. Büyük hedefleri bir kenara bırakıp sadece 2 dakikalık bir başlangıç süresi vererek masanı düzeltmek gibi gözle görülür küçük bir görevle başlamak ister misin? Bugün seni bu denli hareketsiz bırakan yorgunluk hakkında ne hissettiğini paylaşmak ister misin?",
        "Canının hiçbir şey istemediği günlerde kendine yüklenmemen, ruhunun bu mola isteğini kabul etmen çok önemli. Enerji seviyemiz düştüğünde zihnimiz kendini nadasa alır ve bu çok doğaldır. Kendini zorlamadan, bugün sadece bir bardak su içmek veya pencereden dışarı bakmak gibi en zahmetsiz adımlarla güne devam etmeyi deneyebilirsin. Bu isteksizlik en çok hangi anlarda üzerine çöküyor?"
    ],
    "relationship_problems": [
        "Değer verdiğin insanlarla aranda gerginlik çıkması ve anlaşılamamak insanı gerçekten çok yıpratır. İlişkilerde taraflar kendilerini güvende hissetmediğinde iletişim savunmacı bir hal alabilir. Durumu hemen çözmek yerine iki tarafa da biraz zaman tanımak ve sakinleşince kendi hislerine odaklanmak iyi bir adım olabilir. Son tartışmanızda ona aslında neyi duymasını istediğini sakinlikle ifade etme fırsatın oldu mu?",
        "İlişkilerdeki hayal kırıklıkları insanı yorar ve yalnız hissettirir. İki tarafın da kendini haklı görmesi çatışmayı büyütebilir. Bugün kendini suçlamadan, bu durumun sende yarattığı hisleri sakinlikle gözden geçirmeyi deneyebilirsin. İlişkinizde en çok hangi konuda duyulmadığını hissediyorsun?"
    ],
    "self_esteem_issues": [
        "Kendini yetersiz gördüğün anlarda kendi çabalarını ve değerini fark etmek çok zorlaşır, kendine haksızlık ediyor olabilirsin. Kendimizi başkalarıyla kıyasladığımızda iyi taraflarımızı görmemiz imkansızlaşır; oysa mükemmel olmak zorunda değiliz. Bugün kendini tamamen sevmeye zorlamak yerine, ufak bir kusurunu kabullenerek kendine karşı biraz daha yumuşak olmayı dener misin? Son günlerde seni bu yetersizlik hissine sürükleyen belirli bir olay oldu mu?",
        "Kendi değerini başkalarının gözünden ölçmek seni yıpratabilir. İçsel eleştirmen sesimiz bazen bizi korumaya çalışırken aşırı sertleşir. Hatalar yapabilen bir insan olduğunu kabul etmek ve kendine şefkatle yaklaşmak iyi bir ilk adım olabilir. Kendi içinde fena olmadığını düşündüğün ufak bir özelliğin var mı?"
    ],
    "stress": [
        "Her şeyin üst üste yığılması ve sorumlulukların ağırlığı altında bunalmış hissetmen çok anlaşılır. Zihnimiz aynı anda çok fazla görevle ilgilenmeye çalıştığında bilişsel yükümüz aşırı artar ve bu da bizi adeta kilitleyen bir stres tepkisine yol açar. Hepsini tek seferde bitirmeye çalışmak yerine, şu an sadece en acil tek bir sonraki eylemi seçip diğerlerini erteleyebilirsin. İstersen o yığının içinden bugün için seçebileceğimiz tek bir küçük adıma birlikte karar verelim?",
        "Bu stresli dönemin geçici olduğunu kendine hatırlatmak belki zihnini biraz olsun ferahlatabilir. Aynı anda her şeye yetişmeye çalışmak bizi tüketir ve uyarılmışlık halini tetikler. Bugün listendeki bazı şeyleri ertelemek veya gücünün yettiği kadarıyla ilgilenmek en sağlıklı adım olacaktır. Zihnindeki bu yoğun yükü biraz hafifletmek için en çok neye ihtiyacın var?"
    ],
    "fear": [
        "Korku hissetmek seni zayıf yapmaz, sadece insan olduğunu ve beyninin seni koruma çabasını gösterir. Zihnimiz önünü göremediğinde veya bilinmezlikle karşılaştığında kendini korumak için alarm durumuna geçer. Şimdi büyük resmi çözmeye çalışmadan, ayaklarının yere bastığını hissetmek ve buradasın, güvendesin diyerek bedeni rahatlatmak iyi olabilir. Bu durumun seni en çok korkutan yanı nedir?",
        "Zihnindeki o ürkütücü senaryoların seni yorduğunu görebiliyorum. Korku anında beynimiz savaş ya da kaç moduna girer ve mantıklı düşünmeyi zorlaştırır. Sakinleşmek için kendine zaman tanı ve 1-2 derin nefes alarak şimdiye odaklan. Korkunun en çok hangi anlarda yoğunlaştığını konuşalım mı?"
    ],
    "guilt_shame": [
        "Hata yapmış olmanın getirdiği o suçluluk ve huzursuzluk hissi son derece anlaşılır. Ancak sorumluluk almak ile kendini amansızca hırpalamak ve suçlamak arasında önemli bir fark vardır; hata yapmak insanlığımızın bir parçasıyken öz-suçlama sadece kendimize zarar verir. Bu ağır hissi hafifletmek için hatanı telafi edebileceğin küçük bir adım olup olmadığını düşünebilir veya kendine hata yapma hakkı tanıyarak şefkatle yaklaşmayı deneyebilirsin. Seni bu kadar suçluluk hissine sürükleyen durumu yargılamadan dinlememi ister misin?",
        "İçinde taşıdığın utancın yarattığı o sıkışmışlığı tahmin edebiliyorum. Utanç, kendimizi başkalarının gözünde kusurlu gördüğümüzde hissettiğimiz evrensel bir duygudur. Kendini hemen anlatmaya zorlamadan, bu hissin içinde yarattığı bedensel baskıyı fark etmek ve kendine karşı biraz daha yumuşak olmak iyi bir adım olabilir. Bu hissi paylaşarak üzerindeki ağırlığı hafifletmek ister misin?"
    ],
    "uncertainty": [
        "Önünü görememek ve kararsızlığın yarattığı o askıda kalma hissi insanı gerçekten çok yorar, bu belirsizliğe karşı huzursuz olman çok anlaşılır. Hayat her zaman net yollar sunmaz ve belirsizlikle baş etmek zihnimiz için en karmaşık süreçlerden biridir; bu yüzden yönünü kaybetmiş gibi hissetmen oldukça doğaldır. Şimdi tüm geleceği çözmeye çalışmak yerine, hayatında kontrolünde olan durumlar ile kontrol edemeyeceğin şeyleri listelemek zihnini netleştirebilir. Şu an kontrol edebileceğin en ufak şey ne sence?",
        "İki seçenek arasında kalmak ve yanlış karar verme korkusu zihni felç edebilir. Karar verme aşamalarında kaybetme endişesi bizi sürekli belirsizlik içinde askıda tutar. Büyük bir seçim yapmadan önce, her iki seçeneğin de getirebileceği artı ve eksileri basitçe yazarak zihnini rahatlatmayı deneyebilirsin. Seçeneklerin hakkında konuşup aklındaki yükü biraz azaltalım mı?"
    ],
    "neutral": [
        "Merhaba, buradayım. Bugün nasıl hissettiğini paylaşmak ister misin?",
        "Seni dinlemeye ve paylaşmak istediğin her ne varsa eşlik etmeye hazırım. Kendini nasıl hissediyorsun?",
        "Zihninden geçenleri acele etmeden kendi hızında anlatabilirsin. Burası senin için güvenli bir paylaşım alanı."
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
    "kendime güven": "self_esteem_issues", "özgüven": "self_esteem_issues",
    "suçlu": "guilt_shame", "pişman": "guilt_shame", "utanç": "guilt_shame", "utan": "guilt_shame",
    "belirsiz": "uncertainty", "kararsız": "uncertainty", "ne yapacağ": "uncertainty"
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

        # Greeting/Test early exit checks
        clean_text_check = user_actual_text_lower.strip().replace(".", "").replace("!", "").replace(",", "")
        if clean_text_check in {"merhaba", "selam", "hey", "hi", "hello", "selamlar"}:
            response_text = "Merhaba, buradayım. Bugün nasıl hissettiğini paylaşmak ister misin?"
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
        elif clean_text_check in {"bağlantı testi", "baglanti testi", "test", "deneme", "test mesajı", "deneme mesajı"}:
            response_text = "Bağlantı testi başarılı. Size nasıl yardımcı olabilirim?"
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
                    personalized_text = f"{active_stressor} tarafındaki belirsizliklerin zihnini ve bedenini bu denli germesi çok anlaşılır. Zihin bir tehdit sezinlediğinde vücut kendini korumak için alarm tepkisi verir; kalbin hızlı atması bundandır. Şimdi sakinleşmeye zorlamak yerine ayak tabanlarının yere bastığını hissedip 1-2 derin nefes almayı dener misin? Bu durumun seni en çok sıkıştıran yanını paylaşmak ister misin?"
                elif category == "relationship_problems":
                    personalized_text = f"{active_stressor} tarafında yaşanan anlaşmazlıklar ve duyulmamış olmak insanı gerçekten yıpratır. İlişkilerde taraflar güvende hissetmediğinde iletişim savunmacı bir hal alabilir. Durumu hemen çözmeye çalışmak yerine kendine biraz sakinleşme alanı tanımayı dener misin? Son tartışmada en çok hangi konuda anlaşılmadığını hissettin?"
                elif category == "sadness":
                    personalized_text = f"Bu yorgunluk ve üzüntü hissi, son dönemde üst üste gelen {active_stressor} durumlarının ruhundaki doğal etkisidir. Üzüntü enerjimizi aşağı çekerek bizi dinlenmeye davet eder; bu zihnin kendini koruma yoludur. Bugün beklentileri düşürüp kendine hiç yüklenmeden ufacık bir mola vermeyi dener misin? Bu hissin en çok hangi anlarda yoğunlaştığını konuşmak ister misin?"
                else: # stress
                    personalized_text = f"{active_stressor} tarafındaki bu birikmiş yükün seni bunaltmış olması son derece doğal. Sorumluluklar yığıldığında bilişsel yükümüz aşırı artar ve stres tepkisi bizi kilitleyebilir. Hepsini tek seferde bitirmeye çalışmak yerine sadece tek bir sonraki küçük eyleme odaklanabilir misin? Öncelik vermemiz gereken o ilk adım ne olurdu?"
                    
                if display_name:
                    personalized_text = f"{display_name}, " + personalized_text[0].lower() + personalized_text[1:]
                        
            elif current_goal and category in ("self_esteem_issues", "motivation_loss", "anxiety"):
                if category == "self_esteem_issues":
                    personalized_text = f"Kendine karşı bu kadar sertleştiğinde, ulaşmak istediğin hedefler (örneğin {current_goal}) de gözüne çok uzak görünebilir. İçsel eleştirmen sesimiz bazen bizi korumaya çalışırken haksızlık eder. Bugün mükemmel olmaya çalışmak yerine tek bir kusurunu kabullenerek kendine karşı biraz daha yumuşak olmayı dener misin? Seni bu yetersizlik hissine sürükleyen olay neydi?"
                elif category == "motivation_loss":
                    personalized_text = f"Daha önce {current_goal} konusunda çalışmak istediğinden bahsetmiştin; bugün motivasyonun eksik olmasını kabul etmek iyi bir adımdır. Harekete geçmek için motivasyonu beklemek yerine küçük bir adım attığında motivasyon peşinden gelebilir. Kendini zorlamadan sadece 2 dakikalık küçük bir başlangıç yapmayı dener misin? Bugün seni bu denli hareketsiz bırakan şeyi paylaşmak ister misin?"
                else: # anxiety
                    personalized_text = f"Daha önce {current_goal} hedefine odaklanmak istediğini belirtmiştin; şu anki kaygı hissini o yoldaki doğal bir uyarılma olarak görebiliriz. Zihin yeni adımlarda alarm tepkisi vererek bizi korumaya çalışır. Şimdi sakinleşmeye zorlamadan derin nefesler alarak bedeni şimdiye getirmeyi dener misin? Bu kaygıyı en çok neyin tetiklediğini konuşalım mı?"
                    
                if display_name:
                    personalized_text = f"{display_name}, " + personalized_text[0].lower() + personalized_text[1:]
                    
            elif last_advice_topic and category in ("stress", "anxiety"):
                personalized_text = f"Geçenlerde bahsettiğimiz {advice_tr} pratikleri zihnindeki bilişsel yükü ve uyarılmışlığı hafifletmek için harika bir yoldur. Zihin dolduğunda bu pratikler sinir sistemini yatıştırır. Bugün kendine 5 dakikalık bir {advice_tr} alanı tanımak ister misin? Bu pratiğin sana nasıl hissettirdiğini benimle paylaşır mısın?"
                if display_name:
                    personalized_text = f"{display_name}, geçenlerde bahsettiğimiz {advice_tr} pratikleri zihnindeki bilişsel yükü ve uyarılmışlığı hafifletmek için harika bir yoldur. Zihin dolduğunda bu pratikler sinir sistemini yatıştırır. Bugün kendine 5 dakikalık bir {advice_tr} alanı tanımak ister misin? Bu pratiğin sana nasıl hissettirdiğini benimle paylaşır mısın?"
                    
            elif recent_emotion and category == "sadness":
                personalized_text = f"Son zamanlarda hissettiğin o {recent_emotion} hali ruhunu epey yormuş gibi duruyor. Üzüntü dalgalar gibidir, zihni nadasa almak için enerjimizi aşağı çeker. Bugün beklentileri düşürüp kendine biraz şefkat göstermeyi dener misin? Seni en çok yoran bu durum hakkında konuşalım mı?"
                if display_name:
                    personalized_text = f"{display_name}, son zamanlarda hissettiğin o {recent_emotion} hali ruhunu epey yormuş gibi duruyor. Üzüntü dalgalar gibidir, zihni nadasa almak için enerjimizi aşağı çeker. Bugün beklentileri düşürüp kendine biraz şefkat göstermeyi dener misin? Seni en çok yoran bu durum hakkında konuşalım mı?"
                    
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
