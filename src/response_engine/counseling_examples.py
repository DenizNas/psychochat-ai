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
            "assistant": "İçindeki bu büyük ağırlığı ve yorgunluğu hissetmen çok anlaşılır. Bazen üzüntü ve hüzün hissi enerjimizi aşağı çekerek bizi kabuğumuza çekilmeye zorlar; bu aslında zihnimizin ve bedenimizin dinlenme ihtiyacının bir yansımasıdır. Şu an büyük çözümler üretmeye çalışmak yerine, kendine karşı beklentilerini biraz düşürmek ve belki sadece pencerenden dışarı bakıp derin bir nefes almak iyi gelebilir. İstersen bu yorgun hissin en çok hangi anlarda yoğunlaştığına birlikte bakalım, ne dersin?"
        },
        {
            "user": "Bugün yataktan çıkmak bile istemedim, içimde büyük bir hüzün var.",
            "assistant": "Bugün yataktan çıkmak istememiş olman son derece doğal, ruhunun bu yavaşlama ihtiyacını kabul etmekle başlayabiliriz. Yoğun hüzün dönemlerinde vücudumuz kendini bir çeşit kış uykusu moduna alarak bizi yavaşlatır; bu durum ruhsal enerjimizi koruma çabasıdır. Bugün kendine hiç yüklenmeden, sadece yataktan çıkıp yüzünü yıkamak veya ılık bir bardak su içmek gibi tek bir küçük adımla başlayabilirsin. Son günlerde seni bu kadar yorgun hissettiren, enerjini tüketen belirli bir olay oldu mu?"
        },
        {
            "user": "İçimdeki bu burukluk hiç geçmeyecekmiş gibi geliyor.",
            "assistant": "İçindeki o burukluk ve çaresizlik yerleşince sanki hep orada kalacakmış gibi hissettirir, seni çok iyi anlıyorum. Ancak hüzün dalgalar gibidir; şu an ne kadar keskin ve aşılmaz görünse de zamanla yerini daha sakin sulara bırakacaktır. Bugün bu ağır hisleri taşırken kendine şefkat göstermek adına, belki en sevdiğin sıcak bir içeceği hazırlamak gibi küçük bir an yaratabilirsin. Bu burukluğun en çok hangi düşüncelerle birlikte tetiklendiğini paylaşmak ister misin?"
        }
    ],
    "anxiety": [
        {
            "user": "Gelecek hakkında düşünmek beni çok endişelendiriyor, nefesim daralıyor.",
            "assistant": "Geleceğin getirdiği belirsizlikler karşısında zihninin ve bedeninin bu denli gerilmesi çok anlaşılır bir durum. Zihnimiz gelecekte bir tehdit sezinlediğinde, vücudumuz bizi korumak için otomatik bir alarm tepkisi verir; kalbin hızlı atması ve nefesin sıkışması aslında bu koruma sisteminin bir parçasıdır. Şimdi kendini sakinleşmeye zorlamadan, sadece bulunduğun odadaki üç nesneyi içinden sessizce isimlendirmeyi ve omuzlarını yavaşça serbest bırakmayı dener misin? Geleceği bir kenara bırakıp şu an en çok hangi düşüncenin seni sıkıştırdığına bakmak ister misin?"
        },
        {
            "user": "Her şey kötü gidecekmiş gibi bir his var içimde, sakinleşemiyorum.",
            "assistant": "İçindeki o sürekli tetikte olma halini ve huzursuzluğu paylaştığın için teşekkür ederim, böyle hissetmen son derece insani. Kaygı yüksek olduğunda, zihnimiz bizi en kötüsüne hazırlamak için durmaksızın felaket senaryoları üretir; bu durum tamamen hayatta kalma mekanizmamızla ilgilidir. Şimdi sadece ayak tabanlarının yere bastığını hissetmek ve burnundan alıp ağzından yavaşça vereceğin birkaç nefesle bedeni şimdiye davet etmek iyi bir başlangıç olabilir. Zihninin şu an en çok hangi senaryoyu fısıldadığını benimle paylaşmak ister misin?"
        },
        {
            "user": "İçimde bir sıkışma var ve felaket senaryoları kurup duruyorum.",
            "assistant": "Göğsündeki o sıkışmayı ve zihnindeki felaket senaryolarını hissetmen son derece anlaşılır. Kaygı anlarında vücudumuz tehlike moduna geçtiği için nefesimiz ve kaslarımız otomatik olarak gerilir; bu fizyolojik olarak yaşanan olağan bir tepkidir. Şu an o senaryoları hemen çözmeye çalışmak yerine, bulunduğun yerdeki sert bir yüzeye dokunarak bedeni şimdiye getirmeyi ve yavaşça nefes alıp vermeyi dener misin? İstersen bu senaryoların en çok hangi anlarda yoğunlaştığına birlikte bakalım?"
        }
    ],
    "fear": [
        {
            "user": "Yalnız kalmaktan ve hata yapmaktan çok korkuyorum.",
            "assistant": "Hata yapma korkusu ve yalnızlık ihtimalinin sende yarattığı bu ürperti son derece doğal. Bilinmezlik karşısında zihnimizin bizi korumak amacıyla korku üretmesi insan olmanın getirdiği temel mekanizmalardan biridir. Bugün kendine mükemmel olma baskısı yapmadan, sadece en küçük hataların bile birer öğrenme süreci olduğunu hatırlatmak iyi gelebilir. Bu korkunun en çok hangi durumlarda daha baskın şekilde gün yüzüne çıktığını benimle paylaşmak ister misin?"
        },
        {
            "user": "Bu durum beni çok korkutuyor, ne yapacağımı bilmiyorum.",
            "assistant": "Bilinmezliğin ortasında yönünü kaybetmiş hissetmek ve korkmak çok anlaşılır. Zihnimiz önünü göremediğinde kendini korumak için alarm durumuna geçer ve bizi hareketsiz bırakabilir. Şu an tüm resmi çözmeye çalışmak yerine, bugün sadece senin kontrolünde olan küçücük bir adıma odaklanmayı dener misin? Bu durumun seni en çok korkutan yanı nedir, anlatmak ister misin?"
        },
        {
            "user": "Geceleri aniden korkuyla uyanıyorum ve kendimi güvende hissetmiyorum.",
            "assistant": "Gecenin o sessizliğinde aniden korkuyla uyanmanın yarattığı huzursuzluğu tahmin edebiliyorum. Uyku geçişlerinde beynimiz bazen gün içindeki stresleri işlerken aniden alarm durumuna geçebilir; bu fizyolojik bir tepkidir. Uyandığında hemen yataktan fırlamak yerine, üstündeki battaniyenin dokusuna odaklanıp odadaki tanıdık nesnelere bakarak güvende olduğunu kendine hatırlatabilirsin. Gün içinde kafanı en çok kurcalayan endişeler nelerdir?"
        }
    ],
    "anger": [
        {
            "user": "Herkes beni çıldırtıyor, artık katlanamıyorum.",
            "assistant": "Gerçekten sınırlarının sonuna gelmiş gibi hissetmen ve öfke duyman son derece anlaşılır bir tepki. Öfke, aslında sınırımızın ihlal edildiğini veya adaletsiz bir durum olduğunu bize haber veren son derece sağlıklı ve koruyucu bir alarm sinyalidir. Şu an o öfkeyle aceleyle tepki vermek yerine, sadece 10 saniye boyunca derin bir nefes alıp bedendeki o gerginliğin yavaşça dağılmasına izin vermek iyi olabilir. Seni bu derece çileden çıkaran olayda, en çok hangi sınırının aşılmış olduğunu hissettin?"
        },
        {
            "user": "Çok sinirliyim, haksızlığa uğradım.",
            "assistant": "Haksızlığa uğramışlık hissinin yarattığı o yoğun öfkeyi ve kızgınlığı hissetmen çok anlaşılır. Öfke, adaletsizliğe karşı kendimizi savunmamız için içsel gücümüzü harekete geçiren son derece doğal ve işlevsel bir duygudur. Şimdi bu öfkenin sıcaklığıyla bir karar vermeden önce, derin nefesler alarak bedensel uyarılmayı yavaşlatmak iyi bir adım olabilir. Yaşadığın bu haksızlığı ve seni en çok neyin yaraladığını biraz anlatmak ister misin?"
        },
        {
            "user": "Öfkemi kontrol edemiyorum, sonradan pişman oluyorum.",
            "assistant": "Öfke patlamalarının ardından gelen o pişmanlık hissinin yarattığı huzursuzluğu paylaştığın için teşekkürler. Öfke anında beynimizin rasyonel kısmı devreden çıkar ve tamamen duygusal tepkilerle hareket ederiz; bu da sonradan pişmanlık getiren ani tepkilere sebep olur. Öfkenin yükselmeye başladığını hissettiğin o ilk anda, ortamdan 2 dakikalığına uzaklaşmak ve derin nefes alarak kendine alan yaratmak yardımcı olabilir. Genelde bu öfkeyi tetikleyen ilk kıvılcım ne oluyor, birlikte bakabiliriz."
        }
    ],
    "loneliness": [
        {
            "user": "Kendimi çok yalnız hissediyorum, kimse beni aramıyor.",
            "assistant": "Telefonunun çalmaması ve etrafında bir bağ hissedememek insan için gerçekten derin bir boşluk yaratır, hissettiğin bu yalnızlık çok gerçek ve anlaşılır. Bizler bağ kurmaya programlanmış sosyal canlılarız; bu yüzden diğer insanlarla aramızda kopukluk hissettiğimizde kendimizi güvensiz ve izole hissetmemiz tamamen doğaldır. Bu hissi hafifletmek için büyük adımlar atmak yerine, bugün belki sadece dışarı çıkıp bir kahve alırken oradaki insanlara ufak bir selam vermek gibi düşük baskılı bir temas deneyebilirsin. Bu yalnızlık hissinin en çok günün hangi saatlerinde üzerine çöktüğünü benimle paylaşmak ister misin?"
        },
        {
            "user": "Kimseye içimi dökemiyorum, yapayalnızım.",
            "assistant": "İçindekileri paylaşacak, seni yargılamadan dinleyecek birinin eksikliğini hissetmek gerçekten çok ağır. İnsan olarak hislerimizi paylaşma ve onaylanma ihtiyacımız en temel gereksinimlerimizden biridir; bu karşılanmadığında yalnız hissetmek son derece normaldir. Burası senin güvenli alanın, kendini hazır hissettiğinde içindekileri istediğin hızda dökebilirsin. Şu an zihnini en çok meşgul eden ve içinde biriken o ilk düşünce nedir?"
        },
        {
            "user": "Etrafımda insanlar var ama hiçbiri beni gerçekten tanımıyor.",
            "assistant": "Kalabalığın içinde bile görünmez hissetmek, etrafındakilerin seni gerçekten anlamadığını bilmek çok yıpratıcı bir yalnızlık türüdür. Yalnızlık sadece fiziksel tecrit değil, aynı zamanda duygusal olarak görülememe hissidir; bu yüzden derin bağlar kurma isteğin çok doğaldır. Bugün ilişkilerini hemen değiştirmeye çalışmak yerine, kendini daha rahat ifade edebileceğin ufak bir iletişim anı yaratabilirsin. Hayatında seni en çok anladığını hissettiğin kişi kimdi sence?"
        }
    ],
    "motivation_loss": [
        {
            "user": "Hiçbir şey yapmak içimden gelmiyor, çok isteksizim.",
            "assistant": "İçinde hiçbir şeye karşı heves kalmamış olması, canının hiçbir şey yapmak istememesi çok anlaşılır. Çoğu zaman harekete geçmek için önce motivasyonun gelmesini bekleriz; oysa psikolojide motivasyon hareketin ardından gelir, yani ufak bir başlangıç döngüyü tersine çevirebilir. Kendine büyük hedefler koymak yerine, sadece 2 dakikalık bir başlangıç süresi vererek masandaki bir eşyayı düzeltmek gibi gözle görülür tek bir küçük görevle başlamak ister misin? Bugün seni bu denli hareketsiz bırakan yorgunluğu biraz konuşalım mı?"
        },
        {
            "user": "Hedeflerim vardı ama artık hiçbirine odaklanamıyorum.",
            "assistant": "Büyük hedefler karşısında odaklanamamak ve kendini bloke olmuş hissetmek çok doğal bir durum. Zihnimiz hedefleri çok büyük gördüğünde veya enerji seviyemiz düştüğünde kendini korumak için odağı kapatır ve bizi yavaşlatır. Şimdi o büyük hedefleri bir kenara bırakıp, bugün için sadece en basit ve zahmetsiz tek bir adıma odaklanmayı dener misin? Seni bu süreçte odaklanmaktan alıkoyan en büyük düşünce veya endişe nedir?"
        },
        {
            "user": "Eskiden keyif aldığım hiçbir şey artık beni heyecanlandırmıyor.",
            "assistant": "Eskiden heyecan veren şeylerin artık tatsız ve anlamsız gelmesi insana kendini boşlukta hissettirir, bunu yaşaman çok normal. Enerjimiz tükendiğinde veya ruhsal olarak doygunluğa ulaştığımızda, ilgi duyduğumuz şeyler geri çekilebilir; bu zihnin dinlenme talebidir. Kendini zorla keyif almaya çalışmak yerine, şu an sadece durmana ve dinlenmene izin vermek iyi bir adım olabilir. Bu keyifsizlik hissinin ne zamandan beri daha belirgin olduğunu benimle paylaşmak ister misin?"
        }
    ],
    "relationship_problems": [
        {
            "user": "İlişkimde sürekli kavga ediyoruz, beni hiç anlamıyor.",
            "assistant": "Değer verdiğin biriyle sürekli tartışmak ve sesini duyuramamak insanı gerçekten çok yıpratır. İlişkilerde iki taraf da kendini güvende hissetmediğinde, iletişim savunmacı bir hal alabilir ve bu da kısırdöngüye yol açar. Son kavganın sıcaklığı geçtikten sonra, durumu hemen çözmek yerine sadece kendi hislerine odaklanıp sakin bir an seçmek iyi olabilir. Son tartışmada ona aslında neyi duymasını istediğini sakinlikle ifade etme fırsatın oldu mu?"
        },
        {
            "user": "Arkadaşımla tartıştım ve aramız bozuldu.",
            "assistant": "Önem verdiğin bir arkadaşınla aranın açılması insanın canını sıkar, hissettiğin bu burukluk son derece anlaşılır. Yakın ilişkilerdeki çatışmalar, hayatımızdaki güvenli alanlarımızı sarsarak bizi huzursuz eder ve bu tepki çok doğaldır. Aramızdaki gerginliği hemen çözmeye çalışmak yerine, hislerini kağıda yazarak zihnini sakinleştirmek ve ona ufacık bir mesaj atmak iyi bir ilk adım olabilir. Arkadaşınla aranızdaki bu gerginliğe sebep olan konuyu senin gözünden dinlemeyi çok isterim."
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
            "assistant": "Her şeyin üst üste yığılması ve sorumlulukların büyüklüğü karşısında bunalmış hissetmen çok anlaşılır. Zihnimiz aynı anda çok fazla görevi işlemeye çalıştığında bilişsel yükümüz aşırı artar ve bu da bizi adeta kilitleyen bir stres tepkisine yol açar. Hepsini tek seferde bitirmeye çalışmak yerine, şu an listendeki sadece en acil tek bir sonraki eylemi seçip diğerlerini şimdilik askıya alabilirsin. İstersen o yığının içinden bugün için seçebileceğimiz tek bir küçük adıma birlikte karar verelim?"
        },
        {
            "user": "Çok gerginim, her şey üzerime geliyor.",
            "assistant": "Bedeninin ve zihninin bu yoğun gerginlikle yüklenmiş olması son derece yorucu, bu baskıyı hissetmen çok anlaşılır. Stres seviyesi arttığında vücudumuz 'savaş ya da kaç' moduna girerek kaslarımızı sıkar ve bizi tetikte tutar; bu çok olağan bir fizyolojik durumdur. Bu gerginliği azaltmak için omuzlarını yavaşça düşürmeyi ve 2 dakika boyunca sadece nefesinin ritmine odaklanmayı deneyebilirsin. Bugün bu gerginliği en çok neyin tırmandırdığını hissettin?"
        },
        {
            "user": "Gündelik hayattaki küçük aksilikler bile beni çok yıpratıyor.",
            "assistant": "Küçük aksiliklerin bile batmaya başlaması bardaktaki suyun çoktan dolduğunu ve taşmak üzere olduğunu gösterir, çok haklısın. Zihnimiz kronik bir yük altındayken, normalde kolayca çözeceğimiz pürüzleri büyük birer tehdit olarak algılar ve aşırı duyarlı hale gelir. Bugün kendine ek sorumluluk yüklemeden, sadece dinlenmek için küçük bir alan yaratabilirsin. Bardaktaki o suyu asıl biriktiren ana stres kaynaklarını konuşmak ister misin?"
        }
    ],
    "guilt_shame": [
        {
            "user": "Kendimi çok suçlu hissediyorum, hata yaptım.",
            "assistant": "Yaptığın bir hatadan dolayı içinde hissettiğin bu suçluluk ve huzursuzluk hissi çok anlaşılır. Ancak sorumluluk almak ile kendini amansızca hırpalamak ve suçlamak arasında önemli bir fark vardır; hata yapmak insan olmanın doğal bir parçasıyken, öz-suçlama sadece kendimize zarar verir. Bu ağır hissi hafifletmek için, hatanı telafi edebileceğin küçük bir adım olup olmadığını düşünebilir veya kendine hata yapma hakkı tanıyarak şefkatle yaklaşmayı deneyebilirsin. İstersen seni bu kadar suçluluk hissine sürükleyen durumu daha yakından ve yargılamadan birlikte konuşalım?"
        },
        {
            "user": "Çok utanıyorum, yaptığım şeyi kimseye anlatamam.",
            "assistant": "İçinde taşıdığın utancın yarattığı o sıkışmışlığı ve bunu paylaşmanın getirdiği tedirginliği tahmin edebiliyorum. Utanç, kendimizi başkalarının gözünde eksik veya kusurlu gördüğümüzde hissettiğimiz, bizi tamamen saklanmaya iten çok yoğun ama bir o kadar da evrensel bir duygudur. Kendini hemen anlatmaya zorlamadan, sadece bu hissin içinde yarattığı bedensel baskıyı fark etmek ve kendine karşı biraz daha yumuşak olmak iyi bir adım olabilir. Hazır hissettiğinde, seni bu denli saklanmaya iten düşüncenin ne olduğunu benimle paylaşmak ister misin?"
        }
    ],
    "uncertainty": [
        {
            "user": "Hayatımda ne yapacağımı bilmiyorum, kararsızlık beni tüketiyor.",
            "assistant": "Hayatında önünü görememek ve kararsızlığın yarattığı o askıda kalma hissi insanı gerçekten çok yorar, bu belirsizliğe karşı huzursuz olman çok anlaşılır. Hayat her zaman net yollar sunmaz ve belirsizlikle baş etmek zihnimiz için en karmaşık süreçlerden biridir; bu yüzden yönünü kaybetmiş gibi hissetmen oldukça doğaldır. Şimdi tüm geleceği çözmeye çalışmak yerine, hayatında kontrolünde olan durumlar ile kontrol edemeyeceğin şeyleri basit bir kağıda listelemek zihnini netleştirebilir. Şu an hayatında kontrolün altında olduğunu bildiğin en ufak şey ne, buna bakmak ister misin?"
        },
        {
            "user": "Hangi yolu seçeceğimi bilmiyorum, arada kaldım.",
            "assistant": "İki seçenek arasında kalmak ve yanlış bir karar verme endişesi zihni adeta felç edebilir, bu kararsızlık hissini yaşaman çok doğal. Karar verme aşamalarında zihnimiz kaybetme korkusunu ön plana çıkarır ve bu da bizi sürekli belirsizlik içinde askıda tutar. Büyük bir seçim yapmadan önce, her iki seçeneğin de getirebileceği artı ve eksileri basitçe yazıp zihnini rahatlatmayı deneyebilirsin. Seçeneklerinden biri hakkında konuşarak kafandaki o yükü biraz olsun hafifletelim mi?"
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
            "suçlu", "suçluyum", "utanç", "utanıyorum", "pişmanım", "pişman",
            "belirsiz", "kararsız", "kararsızım",
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

    if any(k in clean_text for k in ["suçluluk", "suçlu", "pişman", "utanç", "utanıyorum", "utandım", "kendimi suçluyorum", "vicdan azabı"]):
        return "guilt_shame"

    if any(k in clean_text for k in ["belirsiz", "kararsız", "ne yapacağımı bilmiyorum", "emin değilim", "arada kaldım", "kararsızım", "net değil", "yönümü", "yolumu şaşırd"]):
        return "uncertainty"
        
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
