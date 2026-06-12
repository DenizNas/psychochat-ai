import random
from typing import List, Dict
from src.ai.preprocessing import turkish_lower

# 10 categories as requested:
# A. Sadness (sadness)
# B. Anxiety (anxiety)
# C. Fear (fear)
# D. Anger (anger)
# E. Loneliness (loneliness)
# F. Motivation Loss (motivation_loss)
# G. Relationship Problems (relationship_problems)
# H. Self-Esteem Issues (self_esteem_issues)
# I. Stress (stress)
# J. Neutral Reflection (neutral)

COUNSELING_EXAMPLES: Dict[str, List[Dict[str, str]]] = {
    "sadness": [
        {
            "user": "Hiçbir şey yolunda gitmiyor, çok üzgünüm.",
            "assistant": "Böyle hissetmen çok normal, bazen gerçekten her şey üst üste gelir ve insan nereye tutunacağını şaşırır. Şu an içindeki o ağır yükü hissedebiliyorum. Kendini yalnız hissetme, buradayım. Bugün seni en çok yoran ne oldu, anlatmak istersen dinliyorum."
        },
        {
            "user": "Bugün yataktan çıkmak bile istemedim, içimde büyük bir hüzün var.",
            "assistant": "Bazen sadece durmak, hiçbir şey yapmamak gerekir. Bugün yataktan çıkmak istemediysen kendine hiç yüklenme, bedeninin ve ruhunun buna ihtiyacı varmış demek ki. Son günlerde seni bu kadar tüketen, yoran bir şeyler oldu mu?"
        },
        {
            "user": "İçimdeki bu burukluk hiç geçmeyecekmiş gibi geliyor.",
            "assistant": "O burukluk insanın içine yerleşince sanki hep orada kalacakmış gibi hissettirir, çok haklısın. Ama inan bu da geçecek, şu anki kadar keskin kalmayacak. Bugün o yükü biraz olsun hafifletmek için kendine ufacık da olsa nasıl bir güzellik yapabilirsin?"
        }
    ],
    "anxiety": [
        {
            "user": "Gelecek hakkında düşünmek beni çok endişelendiriyor, nefesim daralıyor.",
            "assistant": "Gelecek kaygısı insanı gerçekten nefessiz bırakabiliyor. Buradasın, güvendesin. Şimdi omuzlarını yavaşça serbest bırak ve derin bir nefes al. Geleceği bir kenara bırakıp sadece şu ana odaklansak, zihnini en çok meşgul eden şey ne?"
        },
        {
            "user": "Her şey kötü gidecekmiş gibi bir his var içimde, sakinleşemiyorum.",
            "assistant": "İçindeki o huzursuzluğu, o tetikte olma halini hissediyorum. Kendini sakinleşmeye zorlama, sadece etrafına bir bak. Odada gördüğün üç basit nesneyi (mesela bir bardak, kitap ya da masa) içinden sessizce söyler misin? Yavaşça, adım adım gidelim."
        },
        {
            "user": "İçimde bir sıkışma var ve felaket senaryoları kurup duruyorum.",
            "assistant": "Göğsündeki o sıkışmayı hissetmen çok normal, zihin en kötü ihtimalleri sıralayarak kendini korumaya çalışıyor şu an. Gel o senaryolara biraz yakından bakalım, gerçekten o kadar korkutucu mu yoksa zihnin şu an biraz abartıyor olabilir mi?"
        }
    ],
    "fear": [
        {
            "user": "Yalnız kalmaktan ve hata yapmaktan çok korkuyorum.",
            "assistant": "Hata yapmak da yalnız kalma ihtimali de insanı ürkütür, çok doğal. Kendinden kusursuz olmanı bekleme lütfen. Hata yapsan da yalnız kalsan da bununla baş edebilecek gücün var. Bu korku en çok hangi anlarda kendini gösteriyor?"
        },
        {
            "user": "Bu durum beni çok korkutuyor, ne yapacağımı bilmiyorum.",
            "assistant": "Bilinmezlik karşısında yönünü kaybetmiş hissetmek çok korkutucu olabilir, seni çok iyi duyuyorum. Şu an her şeyi çözmeye çalışma. Bugün, bu durum içinde kontrolünde olan küçücük bir adım atacak olsan, bu ne olurdu?"
        },
        {
            "user": "Geceleri aniden korkuyla uyanıyorum ve kendimi güvende hissetmiyorum.",
            "assistant": "Uykudan o korkuyla uyanmanın yarattığı sarsıntıyı tahmin edebiliyorum. Uyandığında hemen yataktan çıkma, üstündeki battaniyeye dokun, odanın kokusunu hisset ve burada güvende olduğunu kendine hatırlat. Gün içinde kafanı kurcalayan bir şeyler var mı?"
        }
    ],
    "anger": [
        {
            "user": "Herkes beni çıldırtıyor, artık katlanamıyorum.",
            "assistant": "Gerçekten sınırlarının sonuna gelmişsin gibi duyuluyor. Öfkelenmekte çok haklısın. Şu an seni en çok ne çileden çıkardı, anlatmak ister misin?"
        },
        {
            "user": "Çok sinirliyim, haksızlığa uğradım.",
            "assistant": "Haksızlık hissi insanı gerçekten deliye döndürür, öfkeni çok iyi anlıyorum. Ne oldu, tam olarak ne yaşadın?"
        },
        {
            "user": "Öfkemi kontrol edemiyorum, sonradan pişman oluyorum.",
            "assistant": "O anki öfkeyle sonradan gelen pişmanlık insanı çok yoruyor. Öfkenin yükseldiğini fark ettiğinde sadece bir an durup derin nefes almayı dener misin? Genelde seni ne bu kadar tetikliyor?"
        }
    ],
    "loneliness": [
        {
            "user": "Kendimi çok yalnız hissediyorum, kimse beni aramıyor.",
            "assistant": "Telefonun çalmaması, kimsenin aramaması insanın içini acıtır, çok haklısın. Ama yalnız değilsin, şu an buradayım ve seni dinliyorum. Bu boşluk hissi en çok ne zamanlarda çöküyor üzerine?"
        },
        {
            "user": "Kimseye içimi dökemiyorum, yapayalnızım.",
            "assistant": "İçindekileri paylaşacak, seni yargılamadan dinleyecek birinin olmaması çok zor bir durum. Burası senin alanın, ne zaman istersen, ne kadar istersen anlatabilirsin. İçinde en çok biriken şey ne şu an?"
        },
        {
            "user": "Etrafımda insanlar var ama hiçbiri beni gerçekten tanımıyor.",
            "assistant": "Kalabalığın içinde bile görünmez hissetmek, kimsenin seni gerçekten tanımadığını bilmek çok ağır bir yalnızlık türü. Hakiki bir bağ kurmak istiyorsun sanki. Seni en iyi kim anlardı sence?"
        }
    ],
    "motivation_loss": [
        {
            "user": "Hiçbir şey yapmak içimden gelmiyor, çok isteksizim.",
            "assistant": "İçinde hiçbir şeye karşı heves olmaması çok zor ama bazen beden ve zihin sadece dinlenmek ister. Kendini zorlama. Bugün sadece 5 dakikalık çok küçük bir şey yapacak olsan, bu ne olurdu? Mesela sadece bir bardak su içmek ya da pencereden dışarı bakmak gibi."
        },
        {
            "user": "Hedeflerim vardı ama artık hiçbirine odaklanamıyorum.",
            "assistant": "Büyük hedefler bazen insanı korkutup hareketsiz bırakabilir, odaklanamadığın için kendini suçlama. Şimdilik o büyük hedefleri bir kenara bırakalım. Sadece bugün için atabileceğin en küçük, en zahmetsiz adım ne olurdu?"
        },
        {
            "user": "Eskiden keyif aldığım hiçbir şey artık beni heyecanlandırmıyor.",
            "assistant": "Eskiden sevdiğin şeylerin artık tatsız gelmesi can sıkıcı, biliyorum. Kendini zorlama, bazen ilgi ve enerjimiz geri çekilebilir. Şu an sadece dinlenmene izin versen, bu sana nasıl hissettirir?"
        }
    ],
    "relationship_problems": [
        {
            "user": "İlişkimde sürekli kavga ediyoruz, beni hiç anlamıyor.",
            "assistant": "Sürekli tartışmak ve sesini duyuramamak insanı gerçekten çok yıpratır. İki taraf da kendini anlatmaya çalışırken birbirini kaçırıyor olabilir. Son kavgada ona aslında neyi anlatmak istiyordun da o duyamadı sence?"
        },
        {
            "user": "Arkadaşımla tartıştım ve aramız bozuldu.",
            "assistant": "Önem verdiğin bir arkadaşınla aranın açılması insanın canını sıkar, huzursuz eder. Bu arkadaşlık senin için değerli belli ki. Tartışmaya sebep olan konuyu bir de senin gözünden dinleyebilir miyim?"
        },
        {
            "user": "Ailem sürekli hayatıma karışıyor ve kendimi kapana kısılmış hissediyorum.",
            "assistant": "Ailenin hayatına müdahale etmesi ve sınırlarına saygı duymaması kapana kısılmış hissettirir, haklısın. Hem aileni kırmayıp hem de kendi alanını korumaya çalışırken en çok hangi noktalarda tıkanıyorsun?"
        }
    ],
    "self_esteem_issues": [
        {
            "user": "Kendimi yetersiz hissediyorum, hiçbir şeyi başaramıyorum.",
            "assistant": "Kendini yetersiz hissettiğin anlarda kendi başarılarını ve çabanı görmek çok zorlaşır, kendine haksızlık ediyorsun gibi. Mükemmel olmak zorunda değilsin. Son günlerde seni bu yetersizlik hissine sürükleyen özel bir olay oldu mu?"
        },
        {
            "user": "Kendime hiç güvenmiyorum, hep başkaları daha iyi.",
            "assistant": "Kendini başkalarıyla kıyasladıkça kendi iyi taraflarını görmen imkansız hale gelir, bu kıyaslama seni çok yoruyor olmalı. Kendi içinde sevdiğin ya da fena olmadığını düşündüğün ufak da olsa bir özelliğin var mı?"
        },
        {
            "user": "Sürekli kendimde kusur arıyorum ve kendimi sevemiyorum.",
            "assistant": "İçindeki o eleştirel ses sürekli hatalarını ve kusurlarını aradığında kendini sevmek gerçekten zor olur. Bugün kendini tamamen sevmeye çalışmak yerine, ufacık bir kusurunu kabullenmeyi ve kendine karşı biraz daha yumuşak olmayı dener misin?"
        }
    ],
    "stress": [
        {
            "user": "İş ve okul o kadar birikti ki, stresten çıldırmak üzereyim.",
            "assistant": "Her şeyin üst üste binmesi ve sorumlulukların yığılması insanı felç eder. Hepsini aynı anda ve kusursuz yapmak zorunda değilsin. Bugün önündeki işlerden sadece birine odaklansak, diğerlerini biraz ertelesek rahatlar mıydın?"
        },
        {
            "user": "Çok gerginim, her şey üzerime geliyor.",
            "assistant": "Vücudunun ve kafanın bu gerginlikle dolduğunu görebiliyorum. Bazen sadece durmak, omuzları gevşetip derin bir nefes almak bile o sıkışmayı az da olsa dağıtır. Bugün bu gerginliği en çok ne tetikledi sence?"
        },
        {
            "user": "Gündelik hayattaki küçük aksilikler bile beni çok yıpratıyor.",
            "assistant": "Küçük aksilikler bile batmaya başladıysa bardak çoktan dolmuş demektir, çok haklısın. Son damladan ziyade, o bardağı asıl dolduran, seni yoran ana konuları konuşalım mı biraz?"
        }
    ],
    "neutral": [
        {
            "user": "Bugün sıradan bir gündü, pek bir şey yapmadım.",
            "assistant": "Bazen böyle sakin, sıradan bir gün kafayı dinlemek için iyi gelir. Bu sıradanlık sana nasıl hissettirdi peki, iyi mi geldi yoksa sıkıldın mı biraz?"
        },
        {
            "user": "Bilmiyorum, sadece konuşmak istedim.",
            "assistant": "Çok iyi anlıyorum, bazen insan sadece konuşmak, içindekileri öylesine paylaşmak ister. Buradayım, dinliyorum seni. Şu an aklından geçen, seni meşgul eden herhangi bir düşünce var mı?"
        },
        {
            "user": "Neden böyle hissettiğimi çözemiyorum, içimde bir boşluk var.",
            "assistant": "Nereden geldiği belli olmayan o boşluk hissi insanı gerçekten huzursuz eder. Acele edip hemen doldurmaya çalışmadan, o hissin biraz kalmasına izin verelim. Genelde ne zamanlarda ya da hangi durumlarda bu boşluğu daha çok hissediyorsun?"
        }
    ]
}

# Mapping canonical emotions from BERT to categories when keywords don't match
EMOTION_CATEGORY_FALLBACK = {
    "sadness": "sadness",
    "sad": "sadness",
    "depressed": "sadness",
    "grief": "sadness",
    "anxiety": "anxiety",
    "anxious": "anxiety",
    "fear": "fear",
    "anger": "anger",
    "angry": "anger",
    "frustrated": "anger",
    "happiness": "neutral",
    "happy": "neutral",
    "joy": "neutral",
    "neutral": "neutral"
}

def categorize_input(text: str, emotion: str) -> str:
    """
    Categorizes the user's input based on keywords using turkish_lower(),
    falling back to predicted emotion if no keywords match.
    """
    clean_text = turkish_lower(text or "").strip()

    # 0. Neutral / greeting / test early-return
    # These phrases are never emotionally significant — always classify as neutral
    # regardless of what the BERT emotion model predicted.
    _NEUTRAL_GREETINGS = {
        "merhaba", "selam", "hey", "hi", "hello",
        "günaydın", "iyi günler", "iyi akşamlar", "iyi geceler",
        "nasılsın", "nasılsınız", "naber", "ne haber",
        "bağlantı testi", "baglanti testi", "test", "deneme", "deneme mesajı",
        "test mesajı", "bağlantı", "selamlar",
    }
    # Exact match OR the whole message starts with a greeting token
    for greeting in _NEUTRAL_GREETINGS:
        if clean_text == greeting or clean_text.startswith(greeting + " ") or clean_text.startswith(greeting + ","):
            return "neutral"

    # Very short messages (≤ 3 words) with no emotional keyword → neutral
    # Prevents single-word or two-word technical phrases from misclassifying
    words = clean_text.split()
    if len(words) <= 3:
        # Only override if no obvious emotional word present
        _SHORT_EMOTIONAL_EXCEPTIONS = {
            "üzgünüm", "üzüldüm", "ağlıyorum", "korkuyorum", "öfkeliyim",
            "sinirli", "kaygılı", "bunaldım", "yoruldum", "depresyon",
        }
        if not any(exc in clean_text for exc in _SHORT_EMOTIONAL_EXCEPTIONS):
            return "neutral"

    # 1. Keyword checks
    if any(k in clean_text for k in ["yalnız", "kimsem yok", "kimse yok", "tek başın", "yalnızlık", "yapayalnız", "arkadaşım yok", "dışlan"]):
        return "loneliness"
        
    if any(k in clean_text for k in ["motivasyon", "heves", "isteksiz", "hiçbir şey yapmak", "canım istemiyor", "tükenmiş", "üşen", "bık", "odaklanamıyorum", "hedef"]):
        return "motivation_loss"
        
    if any(k in clean_text for k in ["sevgili", "arkadaş", "eşim", "kocam", "karım", "ilişki", "kavga", "ayrıl", "terk", "aldat", "kızdı", "partner", "aile", "annem", "babam", "kardeş", "aram bozul", "aramız bozul"]):
        return "relationship_problems"
        
    if any(k in clean_text for k in ["özgüven", "kendime güven", "güvenmiyorum", "güvenemiyorum", "yetersiz", "çirkin", "beceriksiz", "başarısız", "kendimden nefret", "beğenmi", "kıyasla", "kusur"]):
        return "self_esteem_issues"
        
    if any(k in clean_text for k in ["stres", "baskı", "yetiş", "sınav", "ders", "iş yoğun", "yorgun", "bunald", "yük", "gergin", "aksilik", "yorul"]):
        return "stress"
        
    if any(k in clean_text for k in ["üzgün", "üzül", "hüzün", "buruk", "mutsuz", "ağla", "keder", "acı", "depresyon"]):
        return "sadness"
        
    if any(k in clean_text for k in ["endişe", "kaygı", "panik", "evham", "huzursuz", "sıkış"]):
        return "anxiety"
        
    if any(k in clean_text for k in ["kork", "ürk", "dehşet"]):
        return "fear"
        
    if any(k in clean_text for k in ["öfke", "sinir", "kızgın", "çıldır", "katlanamıy"]):
        return "anger"
        
    # 2. Fallback to emotion
    emo_lower = turkish_lower(emotion or "neutral")
    return EMOTION_CATEGORY_FALLBACK.get(emo_lower, "neutral")

def get_few_shot_examples(text: str, emotion: str, num_examples: int = 2) -> List[Dict[str, str]]:
    """
    Returns up to num_examples unique examples for the detected category.
    """
    category = categorize_input(text, emotion)
    examples = COUNSELING_EXAMPLES.get(category, COUNSELING_EXAMPLES["neutral"])
    
    # Safely sample unique examples
    sampled = random.sample(examples, min(num_examples, len(examples)))
    return sampled
