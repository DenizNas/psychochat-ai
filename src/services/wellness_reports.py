import time
import logging
from datetime import datetime, timezone
from typing import Dict, List

from src.services.database import get_user_emotion_summary
from src.services.behavioral_insights import generate_behavioral_insights

logger = logging.getLogger(__name__)


def generate_wellness_report(user_id: str, period: str = "daily", days: int = 7) -> Dict:
    """
    Main reporting engine for Phase 8.
    Generates deterministic, explainable, non-diagnostic Daily & Weekly Wellness Reports
    based entirely on privacy-safe metadata.
    """
    start_time = time.time()
    
    # 1. Fetch emotion summary securely
    try:
        summary = get_user_emotion_summary(user_id=user_id, days=days)
        insights = generate_behavioral_insights(user_id=user_id, days=days)
    except Exception as e:
        logger.error(f"WELLNESS_REPORT_GENERATOR | Error fetching data from database: {e}")
        # Return graceful error / empty payload
        return {
            "period": period,
            "summary_title": "Rapor hazırlanamadı.",
            "summary_text": "Sunucu hatası veya veritabanı erişim sorunu nedeniyle wellness raporunuz geçici olarak oluşturulamadı.",
            "dominant_emotion": "Nötr",
            "total_messages": 0,
            "crisis_count": 0,
            "highlights": [],
            "suggestions": [
                "Lütfen internet bağlantınızı kontrol edip tekrar deneyin."
            ],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    total_messages = summary.get("total_messages", 0)
    crisis_count = summary.get("crisis_count", 0)
    dominant_emotion = summary.get("dominant_emotion", "Nötr")
    
    # 2. Empty-safe Check (At least 4 messages/events required)
    if total_messages < 4:
        highlights: List[str] = []
        suggestions = [
            "Sohbet etmeye devam ederek duygu geçmişinizi zenginleştirebilirsiniz.",
            "Duygusal farkındalığınızı artırmak için gün içinde duygularınızı izlemeye özen gösterebilirsiniz."
        ]
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"WELLNESS_REPORT_GENERATOR | UserID: {user_id} | "
            f"report_generation_duration: {duration_ms:.2f}ms | "
            f"report_period: {period} | "
            f"total_messages: {total_messages} | "
            f"crisis_count: {crisis_count} | "
            f"highlight_count: {len(highlights)} | "
            f"suggestion_count: {len(suggestions)}"
        )
        
        return {
            "period": period,
            "summary_title": "Henüz yeterli veri oluşmadı.",
            "summary_text": "Wellness raporunuzun hazırlanabilmesi için en az 4 günlük sohbet geçmişi veya duygu durum kaydı gerekmektedir.",
            "dominant_emotion": "Nötr",
            "total_messages": total_messages,
            "crisis_count": crisis_count,
            "highlights": highlights,
            "suggestions": suggestions,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    # 3. Crisis-Safe Redirection Check
    insight_types = {ins["type"] for ins in insights}
    crisis_override_active = (crisis_count >= 1) or ("crisis_risk_pattern" in insight_types)
    
    if crisis_override_active:
        summary_title = "Hassas Dönem & Öncelikli Destek Hatırlatıcısı"
        summary_text = "Son dönemde yoğun veya hassas duygusal eşiklerden geçmiş olabilirsiniz. Kendinize şefkatle yaklaşmak ve yalnız olmadığınızı bilmek bu süreçte en değerli adımdır. İhtiyaç duyduğunuz her an uzman desteği alabileceğinizi lütfen unutmayın."
        report_dominant = "crisis"
        
        highlights = [
            "Duygusal yoğunluk seviyenizin bu dönemde artış gösterdiği öne çıktı.",
            "Kendinize şefkatle ve sabırla yaklaşmanız son derece büyük önem taşımaktadır.",
            "İçsel dengenizi dinlendirmek için kendinize zaman tanımanız yararlı olabilir."
        ]
        suggestions = [
            "Ücretsiz 112 Acil Çağrı veya 114 Psikolojik Destek kanallarından uzman desteği alabilirsiniz.",
            "Kendinize güvenli bir alan yaratıp derin ve yavaş nefesler almayı deneyebilirsiniz.",
            "Duygularınızı güvendiğiniz bir yakınınızla veya bir uzmanla paylaşabilirsiniz.",
            "Kendinizi yargılamadan sadece şimdiki ana odaklanmayı deneyebilirsiniz."
        ]
        
    else:
        # 4. Normal Observational Language Mapping (Non-Diagnostic)
        dom_lower = str(dominant_emotion).lower()
        
        if dom_lower in ["kaygı", "anxiety", "stres", "stress"]:
            summary_title = "Dengede Kaygı ve Stres Yönetimi"
            summary_text = "Yaptığınız paylaşımlarda kaygı ve gerginlik benzeri duygu tonlarının öne çıktığı gözlemlendi. Zihninizi sakinleştirecek rutinler edinmek içsel dengenizi yeniden kurmaya yardımcı olabilir."
            report_dominant = "anxiety"
            
            highlights = [
                "Kaygı temalı duygusal eğilimler daha belirgin öne çıktı.",
                "Zihinsel stres düzeyinde hafif artış eğilimleri gözlemlendi." if "stress_increase" in insight_types else "Duygusal tepki seviyelerinizde hassasiyet gözlemlendi.",
                "Hassas duygu anlarında tekrarlayan kaygılar fark edildi." if "repeated_anxiety" in insight_types else "Dışsal etkenlere bağlı olarak stres yanıtları oluştu."
            ]
            suggestions = [
                "Sabah saatlerinde kısa nefes egzersizleri uygulamayı deneyebilirsiniz.",
                "Öğleden sonraları kısa ve dinlendirici yürüyüşler yapabilirsiniz.",
                "Gün sonunda düşüncelerinizi bir kağıda yazarak somutlaştırmayı deneyebilirsiniz.",
                "Uykudan önce ekran sürenizi sınırlandırmak sakinleşmenizi kolaylaştırabilir."
            ]
            
        elif dom_lower in ["üzüntü", "sadness", "hüzün"]:
            summary_title = "İçe Dönüş ve Dinginlik Dönemi"
            summary_text = "Konuşmalarınızda hüzün veya melankoli temalı duygu tonlarının öne çıktığı gözlemlendi. Bu duyguların insani ve geçici olduğunu bilerek kendinize zaman tanımak iyileşmeyi besleyebilir."
            report_dominant = "sadness"
            
            highlights = [
                "Hüzünlü duygu tonları bu dönemde daha belirgin öne çıktı.",
                "Süreğen hüzün durumuna bağlı dinginlik anları gözlemlendi." if "prolonged_sadness" in insight_types else "Hassas duygusal geçişler öne çıktı."
            ]
            suggestions = [
                "Değer verdiğiniz bir dostunuzla yumuşak bir sohbet gerçekleştirmeyi düşünebilirsiniz.",
                "Kendinizi dinlendirecek, sevdiğiniz bir müzik veya hobiyle zaman geçirebilirsiniz.",
                "Yavaş adımlarla tazeleyici bir yürüyüşe çıkmak iyi gelebilir.",
                "Günlük olumlamaları okuyarak kendinize şefkat gösterebilirsiniz."
            ]
            
        elif dom_lower in ["öfke", "anger", "nefret"]:
            summary_title = "Hassasiyet ve Duygusal Regülasyon"
            summary_text = "Bu dönemde hayal kırıklığı veya öfke benzeri yoğun sınır ve tepki örüntülerinin öne çıktığı gözlemlendi. Tepki vermeden önce kendinize kısa duraklama payları vermek sakinleşmeyi destekleyebilir."
            report_dominant = "anger"
            
            highlights = [
                "Yoğun tepki ve öfke eğilimleri bu dönemde öne çıktı.",
                "Sınır ihlallerine karşı duygusal duyarlılık gözlemlendi."
            ]
            suggestions = [
                "Öfkenizi bedensel hareketlerle (hafif esneme, kısa yürüyüşler) dışa vurabilirsiniz.",
                "Tepki vermeden önce derin ve yavaş nefesler alarak 10'a kadar saymayı deneyebilirsiniz.",
                "Sakinleştirici doğa sesleri dinlemek zihninizi dinlendirebilir."
            ]
            
        else: # Happiness, Neutral or positive recovery
            summary_title = "Huzurlu ve Dengeli Wellness Durumu"
            summary_text = "Bu dönemdeki duygu durumunuzun genel olarak dengeli, dingin ve olumlu bir tonda seyrettiği gözlemlendi. İçsel huzurunuzu korumak için kendinize şefkatle yaklaşmaya devam edebilirsiniz."
            report_dominant = "happiness"
            
            highlights = [
                "Olumlu ve kararlı duygusal dengeniz öne çıktı.",
                "Dengeleyici toparlanma anları başarıyla sürdürüldü." if "positive_recovery" in insight_types else "Duygusal esneklik seviyenizin dengede olduğu fark edildi."
            ]
            suggestions = [
                "Bugün yaşadığınız küçük de olsa güzel bir anı veya şükran duyduğunuz bir detayı fark edebilirsiniz.",
                "Sevdiğiniz bir rutin ile günün keyfini çıkarabilirsiniz.",
                "Bu dingin hali sürdürmek için kendinize şefkatle yaklaşmaya devam edebilirsiniz."
            ]

    # Enforce maximum limits (At most 5 highlights and 5 suggestions)
    highlights = highlights[:5]
    suggestions = suggestions[:5]
    
    duration_ms = (time.time() - start_time) * 1000
    
    # 5. Structured Diagnostic Performance Logging
    logger.info(
        f"WELLNESS_REPORT_GENERATOR | UserID: {user_id} | "
        f"report_generation_duration: {duration_ms:.2f}ms | "
        f"report_period: {period} | "
        f"total_messages: {total_messages} | "
        f"crisis_count: {crisis_count} | "
        f"highlight_count: {len(highlights)} | "
        f"suggestion_count: {len(suggestions)}"
    )

    return {
        "period": period,
        "summary_title": summary_title,
        "summary_text": summary_text,
        "dominant_emotion": report_dominant,
        "total_messages": total_messages,
        "crisis_count": crisis_count,
        "highlights": highlights,
        "suggestions": suggestions,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
