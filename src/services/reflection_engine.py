import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

# Secure import of existing DB services
from src.services.database import (
    get_user_emotion_summary,
    get_mood_journals_for_user,
    get_scheduled_interventions_for_user
)
from src.services.behavioral_insights import generate_behavioral_insights
from src.services.wellness_reports import generate_wellness_report

logger = logging.getLogger(__name__)

# Deterministic supportive, non-diagnostic reflection templates
TEMPLATES = {
    "daily": {
        "anxiety": {
            "title": "Günlük İçgörü ve Refleksiyon",
            "text": "Bugün paylaşımlarınızda kaygı ve gerginlik benzeri duygu tonlarının öne çıktığı gözlemlendi. Günlük rutinlerinizdeki hızlı koşturmacalar veya zihinsel yoğunluk bu hisleri tetiklemiş olabilir. Kendinize dinlenmek, derin nefes almak ve şimdiki ana odaklanmak için küçük anlar ayırmanız içsel dengenizi destekleyebilir."
        },
        "sadness": {
            "title": "Günlük İçgörü ve Refleksiyon",
            "text": "Bugün paylaşımlarınızda daha durgun, melankolik veya hüzünlü duygu eğilimleri gözlemlendi. Enerjinizin düştüğünü hissetmeniz son derece insani ve doğaldır. Bu anlarda kendinize şefkatle yaklaşmanız, sevdiğiniz sakin bir hobiyle zaman geçirmeniz veya hafif bir yürüyüş yapmanız kendinizi daha hafif hissetmenize yardımcı olabilir."
        },
        "anger": {
            "title": "Günlük İçgörü ve Refleksiyon",
            "text": "Bugünkü etkileşimlerinizde hayal kırıklığı veya tepkisellik içeren gergin anların öne çıktığı fark edildi. Sınırlarınızın zorlandığını hissettiğinizde bu hislerin oluşması doğaldır. Tepki vermeden önce kendinize kısa duraklama payları vermek ve bedensel gerginliğinizi esneme hareketleriyle hafifletmek sakinleşmeyi kolaylaştırabilir."
        },
        "balanced": {
            "title": "Günlük İçgörü ve Refleksiyon",
            "text": "Bugünkü genel duygu durumunuzun dengeli, dingin ve olumlu bir tonda seyrettiği gözlemlendi. İçsel huzurunuzu korumak için kendinize şefkatle yaklaşmaya ve size iyi gelen küçük rutinlerinizi sürdürmeye devam edebilirsiniz."
        }
    },
    "weekly": {
        "anxiety": {
            "title": "Haftalık İçgörü ve Refleksiyon",
            "text": "Bu hafta kaygı ve gerginlik temalı duygu örüntülerinin zaman zaman öne çıktığı gözlemlendi. Özellikle haftanın bazı günlerinde zihinsel stres seviyesinin arttığı fark edildi. Hafta boyunca planlanan küçük nefes molaları ve düzenli dinlenme pratikleri bu yoğunluğu dengelemede oldukça destekleyici olabilir."
        },
        "sadness": {
            "title": "Haftalık İçgörü ve Refleksiyon",
            "text": "Bu hafta genel olarak hüzün veya durgun hislerin öne çıktığı ve enerjinizin düştüğü günler gözlemlendi. Duygusal dalgalanmaların olması insani bir süreçtir. Haftalık rutinlerinizde güvendiğiniz bir yakınınızla sohbet etmek, kendinize şefkat göstermek ve doğada kısa yürüyüşler yapmak bu sakin dönemi rahat geçirmenize katkıda bulunabilir."
        },
        "anger": {
            "title": "Haftalık İçgörü ve Refleksiyon",
            "text": "Hafta boyunca paylaşılan duygusal durumlarda hayal kırıklığı, sınır ihlalleri veya gergin tepkilerin zaman zaman yoğunlaştığı gözlemlendi. Stres yanıtlarınızı kontrol altında tutmak için gün içinde nefes egzersizlerine başvurmak, tepki sürelerinizi yavaşlatmak ve zihinsel sakinleşme alanları yaratmak yararlı olabilir."
        },
        "balanced": {
            "title": "Haftalık İçgörü ve Refleksiyon",
            "text": "Bu hafta boyunca duygusal dengenizin genel olarak kararlı, huzurlu ve olumlu bir seyir izlediği gözlemlendi. Zorlayıcı anlarda bile toparlanma becerinizin yüksek olduğu fark edildi. İçsel dengenizi korumak için kendinize değer vermeye ve keyifli anların tadını çıkarmaya devam edebilirsiniz."
        }
    },
    "crisis": {
        "title": "Hassas Dönem ve Destekleyici Refleksiyon",
        "text": "Son dönemde duygusal yoğunluğunuzun ve stres eşiğinizin oldukça yüksek olduğu gözlemlendi. Bu hassas zamanlarda yalnız olmadığınızı ve kendinize şefkatle yaklaşmanın ne kadar değerli olduğunu hatırlatmak isteriz. İçinizdeki gücü dinlendirmek için kendinize zaman tanıyın. İhtiyaç duyduğunuz her an, ücretsiz ve gizli olan 112 Acil Çağrı veya 114 Psikolojik Destek uzman hatlarına ulaşarak profesyonel bir rehberlikle kendinizi destekleyebileceğinizi lütfen unutmayın."
    }
}


def generate_reflection(user_id: str, period: str = "daily") -> Dict[str, Any]:
    """
    Computes a personalized, observational, non-diagnostic reflection summary.
    100% deterministic template-driven approach, zero GPT/OpenAI calls.
    Guarantees privacy-safety (uses metadata only, no raw texts or notes used).
    Crisis-safe: automatically switches to gentle helper tone if risk is detected.
    """
    start_time = time.time()
    
    # Map periods to days: daily = 1 day, weekly = 7 days
    days = 1 if period == "daily" else 7
    
    # 1. Fetch metadata securely
    try:
        emotion_sum = get_user_emotion_summary(user_id=user_id, days=days)
        insights = generate_behavioral_insights(user_id=user_id, days=days)
        mood_journals = get_mood_journals_for_user(user_id=user_id, days=days)
        interventions = get_scheduled_interventions_for_user(user_id=user_id)
    except Exception as e:
        logger.error(f"REFLECTION_ENGINE | Database query error: {e}")
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"REFLECTION_ENGINE | UserID: {user_id} | "
            f"reflection_generation_duration: {duration_ms:.2f}ms | "
            f"reflection_period: {period} | "
            f"dominant_emotion: error | source_count: 0 | "
            f"crisis_mode: False | reflection_length: 0"
        )
        return {
            "period": period,
            "reflection_title": "Refleksiyon Hazırlanamadı",
            "reflection_text": "Sistem veya veritabanı bağlantı hatası nedeniyle kişisel refleksiyon özetiniz şu anda hazırlanamadı.",
            "tone": "supportive",
            "dominant_emotion": "neutral",
            "generated_from": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    total_messages = emotion_sum.get("total_messages", 0)
    crisis_count = emotion_sum.get("crisis_count", 0)
    dominant_emotion_raw = emotion_sum.get("dominant_emotion", "neutral")
    
    mood_journal_count = len(mood_journals)
    
    # Calculate generated_from list dynamically based on active metadata presence
    generated_from = ["emotion_summary"]
    if len(insights) > 0:
        generated_from.append("behavioral_insights")
    if mood_journal_count > 0:
        generated_from.append("mood_journal")
    if len(interventions) > 0:
        generated_from.append("scheduled_interventions")
        
    source_count = len(generated_from)

    # 2. Threshold Check (At least 4 observations across messages + journal entries required)
    total_data_count = total_messages + mood_journal_count
    if total_data_count < 4:
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"REFLECTION_ENGINE | UserID: {user_id} | "
            f"reflection_generation_duration: {duration_ms:.2f}ms | "
            f"reflection_period: {period} | "
            f"dominant_emotion: neutral | source_count: {source_count} | "
            f"crisis_mode: False | reflection_length: 64"
        )
        return {
            "period": period,
            "reflection_title": "Yetersiz Veri",
            "reflection_text": "Henüz yeterli veri oluşmadığı için kişisel refleksiyon üretilemedi.",
            "tone": "supportive",
            "dominant_emotion": "neutral",
            "generated_from": generated_from,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    # 3. Crisis Override Check
    insight_types = {ins["type"] for ins in insights}
    crisis_override = (crisis_count >= 1) or ("crisis_risk_pattern" in insight_types)

    if crisis_override:
        title = TEMPLATES["crisis"]["title"]
        text = TEMPLATES["crisis"]["text"]
        tone = "supportive_crisis"
        dominant_emotion = "crisis"
        crisis_mode = True
    else:
        crisis_mode = False
        tone = "supportive"
        
        # Resolve dominant emotion code
        # Check standard mappings (turkish translation support in database results)
        dom_lower = str(dominant_emotion_raw).lower()
        if dom_lower in ["kaygı", "anxiety", "stres", "stress"]:
            dominant_emotion = "anxiety"
        elif dom_lower in ["üzüntü", "sadness", "sad", "durgun"]:
            dominant_emotion = "sadness"
        elif dom_lower in ["öfke", "anger", "angry", "kızgın"]:
            dominant_emotion = "anger"
        elif dom_lower in ["mutlu", "joy", "happiness", "mutluluk", "neşe"]:
            dominant_emotion = "happiness"
        else:
            dominant_emotion = "balanced"

        # Safe fallback selection
        period_templates = TEMPLATES.get(period, TEMPLATES["daily"])
        emotion_template = period_templates.get(dominant_emotion, period_templates["balanced"])
        
        title = emotion_template["title"]
        text = emotion_template["text"]

    # Enforce maximum text length safety cap (1200 characters)
    if len(text) > 1200:
        text = text[:1197] + "..."

    duration_ms = (time.time() - start_time) * 1000
    reflection_length = len(text)

    # 4. Structured Performance Log
    logger.info(
        f"REFLECTION_ENGINE | UserID: {user_id} | "
        f"reflection_generation_duration: {duration_ms:.2f}ms | "
        f"reflection_period: {period} | "
        f"dominant_emotion: {dominant_emotion} | "
        f"source_count: {source_count} | "
        f"crisis_mode: {crisis_mode} | "
        f"reflection_length: {reflection_length}"
    )

    return {
        "period": period,
        "reflection_title": title,
        "reflection_text": text,
        "tone": tone,
        "dominant_emotion": dominant_emotion,
        "generated_from": generated_from,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
