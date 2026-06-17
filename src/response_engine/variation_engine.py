from typing import List, Dict, Optional, Tuple
from src.ai.preprocessing import turkish_lower

# Define the variants registry
VARIANTS = {
    "validation": [
        {
            "id": "val_1",
            "keywords": ["yükü taş", "yorulduğunu", "görebiliyorum"],
            "directive": (
                "1. Paragraf — Duygusal Yansıtma tarzı: 'Bu yükü taşırken ne kadar yorulduğunu görebiliyorum. "
                "Paylaşman çok değerli.'\n"
                "2. Paragraf — Normalizasyon ve Anlam-Yapma tarzı: Bu his çoğu zaman tembellikten değil, "
                "uzun süredir taşınan zihinsel ve duygusal yüklerden kaynaklanır."
            )
        },
        {
            "id": "val_2",
            "keywords": ["ne kadar yorduğunu", "hissedebiliyorum"],
            "directive": (
                "1. Paragraf — Duygusal Yansıtma tarzı: 'Bunun seni ne kadar yorduğunu hissedebiliyorum. "
                "Duygularını hissetmene izin ver.'\n"
                "2. Paragraf — Normalizasyon ve Anlam-Yapma tarzı: Bazen zihin ve beden, taşınan yükün altında "
                "bu şekilde ağırlaşır; bu bir eksiklik değil, uzun süre taşımanın doğal bir yansımasıdır."
            )
        },
        {
            "id": "val_3",
            "keywords": ["baş etmeye çalışmak", "kolay görünmüyor"],
            "directive": (
                "1. Paragraf — Duygusal Yansıtma tarzı: 'Bu duygularla tek başına baş etmeye çalışmak kolay "
                "görünmüyor, yanındayım.'\n"
                "2. Paragraf — Normalizasyon ve Anlam-Yapma tarzı: Bu his çoğunlukla biriken duygusal yorgunluğun "
                "bir dışavurumudur; güçsüzlükten değil, yoğun içsel çabanın sonucundan gelir."
            )
        },
        {
            "id": "val_4",
            "keywords": ["ağırlığını duyabiliyorum", "yaşadığın şeyin"],
            "directive": (
                "1. Paragraf — Duygusal Yansıtma tarzı: 'Yaşadığın şeyin ağırlığını en derinden duyabiliyorum. "
                "Bu hislerinde yalnız değilsin.'\n"
                "2. Paragraf — Normalizasyon ve Anlam-Yapma tarzı: Bu tür ağır hisler çoğu zaman uzun süredir "
                "içte biriken ve dile getirilemeyen duygusal yüklerden beslenir; bu durum bir zayıflık değil, "
                "taşınan şeyin büyüklüğünün bir göstergesidir."
            )
        }
    ],

    "anhedonia": [
        {
            "id": "anh_1",
            "keywords": ["keyif ve ilginin", "yavaş yavaş çekilmiş"],
            "directive": (
                "1. Paragraf — Anhedonia Yansıtma tarzı: '"
                "Hiçbir şeyden keyif alamıyor olmak, insanın içindeki ilginin ve enerjinin "
                "yavaş yavaş çekilmiş gibi hissettirmesine neden olabilir.'\n"
                "2. Paragraf — Normalizasyon tarzı: '"
                "Bu çoğu zaman tembellikten ya da isteksizlikten değil, "
                "zihnin ve bedenin bir süredir taşıdığı yükün nazik bir işareti olabilir.'"
            )
        },
        {
            "id": "anh_2",
            "keywords": ["dünyanın renkleri", "solmuş gibi"],
            "directive": (
                "1. Paragraf — Anhedonia Yansıtma tarzı: '"
                "Eskiden anlam taşıyan şeylerin şimdi renksiz ve boş durması, "
                "sanki dünyanın renklerinin solmuş gibi görünmesi çok yorucu bir his.'\n"
                "2. Paragraf — Normalizasyon tarzı: '"
                "Bu içsel boşluk kişisel bir eksiklikten değil, "
                "zihnin kendini koruma biçiminden kaynaklanıyor olabilir.'"
            )
        },
        {
            "id": "anh_3",
            "keywords": ["bağlantısızlık", "keyif kapasitesi"],
            "directive": (
                "1. Paragraf — Anhedonia Yansıtma tarzı: '"
                "Etrafındaki her şeyle olan bağlantının kopmuş gibi hissettirmesi, "
                "hiçbir şeyin seni çekmiyor olması gerçekten ağır bir deneyim.'\n"
                "2. Paragraf — Normalizasyon tarzı: '"
                "Keyif kapasitesi bazen taşınan yük altında geçici olarak kapanabilir; "
                "bu durumu hak etmediğin ve çünkü tembelsin anlamına gelmiyor.'"
            )
        }
    ],

    "reflection": [
        {
            "id": "ref_1",
            "keywords": ["çıkmazda hissederken", "sanki"],
            "directive": "Yansıtma cümlesi tarzı: 'Kendini bu çıkmazda hissederken, sanki her şey üst üste geliyor gibi algılaman çok normal.'"
        },
        {
            "id": "ref_2",
            "keywords": ["yaşadığın bu tıkanıklık", "aslında"],
            "directive": "Yansıtma cümlesi tarzı: 'Yaşadığın bu tıkanıklık, aslında zihninin biraz durup nefes almaya ihtiyacı olduğunu söylüyor.'"
        },
        {
            "id": "ref_3",
            "keywords": ["içinde biriken bu baskı", "şu an"],
            "directive": "Yansıtma cümlesi tarzı: 'İçinde biriken bu baskı, şu an yönünü net görmeni zorlaştırıyor gibi görünüyor.'"
        }
    ],
    "psychoeducation": [
        {
            "id": "psy_1",
            "keywords": ["zihnimiz belirsizlik", "tepkiler verebilir"],
            "directive": "Psikoeğitim açıklaması tarzı: 'Zihnimiz belirsizlik ve baskı durumlarında tehdit algılayıp bu tarz alarm tepkileri verebilir.'"
        },
        {
            "id": "psy_2",
            "keywords": ["bedenin kendini koruma", "yoğun kaygılar"],
            "directive": "Psikoeğitim açıklaması tarzı: 'Psikolojik olarak, bu tür yoğun kaygılar bedenin kendini korumaya yönelik geliştirdiği otomatik bir uyarılma halidir.'"
        },
        {
            "id": "psy_3",
            "keywords": ["içsel dengemiz", "baskı altında"],
            "directive": "Psikoeğitim açıklaması tarzı: 'İçsel dengemiz bazen dış beklentiler ve gelecek kaygısı altında gerilebilir, bu geçici bir tepkidir.'"
        }
    ],
    "action_planning": [
        {
            "id": "act_1",
            "keywords": ["ufak bir adım", "atabileceğimiz"],
            "directive": "Eylem planlama önerisi tarzı: 'Şşu an için atabileceğimiz en ufak adım, durumu kontrol etmeye çalışmak yerine bir an durup nefes almaktır.'"
        },
        {
            "id": "act_2",
            "keywords": ["büyük resmi çözmek", "sadece"],
            "directive": "Eylem planlama önerisi tarzı: 'Büyük resmi hemen çözmeye çalışmak yerine, sadece önündeki tek bir küçük göreve odaklanmayı deneyebilirsin.'"
        },
        {
            "id": "act_3",
            "keywords": ["kontrol edebileceğin", "tek bir küçük"],
            "directive": "Eylem planlama önerisi tarzı: 'Şu an kontrol edebileceğin tek bir küçük şeye odaklanmak zihnini rahatlatacaktır.'"
        }
    ],
    "exploration": [
        {
            "id": "exp_1",
            "keywords": ["en çok ne zaman", "belirginleşiyor"],
            "directive": "Takip sorusu tarzı: 'Bu his en çok hangi anlarda belirginleşiyor, biraz anlatmak ister misin?'"
        },
        {
            "id": "exp_2",
            "keywords": ["biraz daha açmak", "ister misin"],
            "directive": "Takip sorusu tarzı: 'Bunu biraz daha açmak ister misin? Seni dinlemek için buradayım.'"
        },
        {
            "id": "exp_3",
            "keywords": ["hayatında neyi", "zorlaştırıyor"],
            "directive": "Takip sorusu tarzı: 'Bu durum şu an hayatında seni en çok neyi yaparken zorlaştırıyor?'"
        }
    ],
    "strengths_focused": [
        {
            "id": "str_1",
            "keywords": ["gösterdiğin çaba", "farkındayım"],
            "directive": "Güçlü yön odaklı tarz: 'Bu durumla başa çıkmak için gösterdiğin çabanın ve direncin farkındayım. Kendine şefkat göster.'"
        },
        {
            "id": "str_2",
            "keywords": ["adım atmış olman", "başarıdır"],
            "directive": "Güçlü yön odaklı tarz: 'Tüm zorluğa rağmen buraya gelip paylaşma adımı atmış olman bile senin içsel gücünü gösterir.'"
        },
        {
            "id": "str_3",
            "keywords": ["geçmişteki zorlukları", "nasıl aştığını"],
            "directive": "Güçlü yön odaklı tarz: 'Geçmişteki benzer zorlukları nasıl aştığını hatırlamak, bugünkü adımların için sana rehberlik edebilir.'"
        }
    ]
}

def select_linguistic_variants(
    recent_responses: List[str],
    emotion: str,
    subtype: Optional[str] = None,
    strategy: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Selects a linguistic variant directive for the given strategy and checks against recent response history
    to prevent repeating phrases.
    
    Inputs:
      - recent_responses: List of recent assistant response texts (used for overlap checking).
      - emotion: Mapped counseling category (e.g. sadness, anxiety, fear, loneliness).
      - subtype: Detected emotion subtype (e.g. exam_anxiety, failure_fear, anhedonia).
      - strategy: Detected conversation strategy label.
      
    Returns:
      - Tuple of (selected_variant_id, selected_directive_text)
    """
    strat = (strategy or "").strip().lower()

    # If subtype has dedicated variants, use those instead of the generic strategy pool.
    # This ensures anhedonia gets anhedonia-specific directives, not generic validation ones.
    sub = (subtype or "").strip().lower()
    if sub and sub in VARIANTS:
        strat = sub
    elif not strat or strat not in VARIANTS:
        # Fallback to a default based on emotion if strategy is missing or unknown
        emotion_to_strategy = {
            "sadness": "validation",
            "fear": "validation",
            "anger": "validation",
            "loneliness": "validation",
            "guilt_shame": "validation",
            "uncertainty": "action_planning",
            "anxiety": "psychoeducation",
            "neutral": "exploration"
        }
        strat = emotion_to_strategy.get(emotion.strip().lower(), "exploration")

    options = VARIANTS.get(strat, VARIANTS["exploration"])
    
    # Clean up recent responses
    clean_history = [turkish_lower(resp) for resp in recent_responses or []]

    # If recent response history is empty, select a safe deterministic default variant (first option)
    if not clean_history:
        default_opt = options[0]
        return default_opt["id"], default_opt["directive"]

    # Filter out variants that appear in recent responses using keyword matching
    available = []
    for opt in options:
        is_repeated = False
        for kw in opt["keywords"]:
            # Check if keyword kw is a substring in any of the recent responses
            kw_clean = turkish_lower(kw)
            if any(kw_clean in resp for resp in clean_history):
                is_repeated = True
                break
        if not is_repeated:
            available.append(opt)

    # If all variants are filtered, fall back safely without crashing (select first option)
    if not available:
        fallback_opt = options[0]
        return fallback_opt["id"], fallback_opt["directive"]

    # Deterministically select one variant using the length of clean_history to distribute
    selected_index = len(clean_history) % len(available)
    selected_opt = available[selected_index]

    return selected_opt["id"], selected_opt["directive"]
