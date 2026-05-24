import time
import logging
from datetime import datetime, timezone
from typing import List, Dict
from src.services.database import get_user_emotion_summary
from src.services.behavioral_insights import generate_behavioral_insights

logger = logging.getLogger(__name__)

def generate_smart_interventions(user_id: str, days: int = 7) -> List[Dict]:
    """
    Analyzes behavioral insights and daily summaries to output gentle, clinical-safe interventions.
    Completely privacy-safe: uses only metadata labels, no raw text.
    Completely crisis-safe: crisis triggers a safety guidance override.
    Filters duplicated recommendations and enforces a maximum of 3 items.
    """
    start_time = time.time()
    
    # 1. Fetch backend summary (contains message counts and crisis count)
    summary = get_user_emotion_summary(user_id=user_id, days=days)
    total_messages = summary.get("total_messages", 0)
    crisis_count = summary.get("crisis_count", 0)
    dominant_emotion = summary.get("dominant_emotion") or "neutral"
    
    # 2. Strict Threshold Enforcement: if < 4, return empty immediately to avoid premature recommendations
    if total_messages < 4:
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"INTERVENTION_ENGINE | UserID: {user_id} | Days: {days} | "
            f"Not enough data. Total messages: {total_messages} (min: 4). "
            f"Latency: {duration_ms:.2f}ms"
        )
        return []
        
    # 3. Fetch computed behavioral insights
    insights = generate_behavioral_insights(user_id=user_id, days=days)
    insight_types = {ins["type"] for ins in insights}
    
    interventions = []
    crisis_detected = False
    
    # 4. Check for Crisis Indicators VEYA High Stress Patterns
    if crisis_count >= 1 or "crisis_risk_pattern" in insight_types:
        crisis_detected = True
        
    if crisis_detected:
        # CRISIS OVERRIDE: Prioritize support/safety guidance and keep standard wellness advice minimized
        interventions.append({
            "type": "priority_support",
            "severity": "priority_support",
            "title": "Kendinize şefkatle yaklaşma vakti",
            "description": "Son görüşmelerinizde yoğun stres ve duygusal hassasiyet örüntüleri gözlemlendi. Yalnız olmadığınızı bilmenizi isteriz. İhtiyaç duyduğunuz her an 112 Acil Destek veya 114 Psikolojik Destek gibi uzman kanallardan tamamen ücretsiz ve profesyonel rehberlik alabilirsiniz. Bir profesyonelden destek almak iyileşme sürecinin en güçlü adımıdır.",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Add at most one very soft grounding exercise under crisis override
        interventions.append({
            "type": "breathing_break",
            "severity": "supportive",
            "title": "Kısa ve sakin bir nefes molası",
            "description": "Şu an zihninizde yoğun bir fırtına olabilir. Sırtınızı yaslayıp, burnunuzdan 4 saniye derin nefes alarak 4 saniye tutmayı ve ardından yavaşça vermeyi deneyin. Bu fiziksel rahatlama sürecinizi destekleyecektir.",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        # Standard Trigger Rules
        if "repeated_anxiety" in insight_types:
            interventions.append({
                "type": "breathing_break",
                "severity": "supportive",
                "title": "Nefesinize odaklanmak için ufak bir mola",
                "description": "Son günlerdeki sohbetlerinizde kaygılı hislerin yoğunlaştığı fark edildi. Omuzlarınızı rahat bırakıp sadece nefesinizi izlemek ve yavaşça soluk alıp vermek bedeninizi gevşetebilir.",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
        if "prolonged_sadness" in insight_types:
            interventions.append({
                "type": "social_connection",
                "severity": "supportive",
                "title": "Yakınlarınızla küçük bir paylaşım",
                "description": "Paylaşımlarınızda sakin ve durgun bir seyir gözlemlendi. Sevdiğiniz bir arkadaşa sadece kısa bir mesaj atmak veya bir yakınınızın sesini duymak kendinizi daha güvende hissettirebilir.",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
        if "stress_increase" in insight_types:
            interventions.append({
                "type": "short_walk",
                "severity": "supportive",
                "title": "Zihinsel alanı tazelemek için hafif yürüyüş",
                "description": "Görüşmelerinizin ilerleyen süreçlerinde stres seviyenizin arttığı gözlemlendi. Birkaç dakikalık açık hava yürüyüşü veya pencereyi açıp dışarıyı izlemek bedensel gerginliğinizi hafifletecektir.",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
        if "emotional_instability" in insight_types:
            interventions.append({
                "type": "grounding_exercise",
                "severity": "supportive",
                "title": "Şimdiki ana odaklanmak için zihinsel çapa",
                "description": "Duygularınızda iniş çıkışlı dalgalanmalar gözlemlendi. Bulunduğunuz odada gözünüze çarpan 5 nesneyi ve kulağınıza gelen 3 sesi zihninizde adlandırmayı deneyin. Bu topraklama egzersizi sakinlik kazandırır.",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
        if "positive_recovery" in insight_types:
            interventions.append({
                "type": "positive_reflection",
                "severity": "gentle",
                "title": "Umut dolu anları fark etme zamanı",
                "description": "Son paylaşımlarınızda güzel bir olumlu gelişim trendi gözlendi. Sizi bugün ufak da olsa mutlu eden veya şükran duyduğunuz bir detayı zihninizde tazelemek bu güzel enerjiyi besleyecektir.",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
        # Add dynamic hydration/sleep fillers if list is short to enrich companion value
        if len(interventions) < 2:
            interventions.append({
                "type": "hydration_reminder",
                "severity": "gentle",
                "title": "Bedensel dinginlik için bir bardak su",
                "description": "Stres ve zihinsel yorgunluğu azaltmanın en temel yollarından biri düzenli su tüketimidir. Kendinize şimdi taze bir bardak su ikram etmeye ne dersiniz?",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
        if len(interventions) < 3:
            interventions.append({
                "type": "sleep_reminder",
                "severity": "gentle",
                "title": "Zihni tazelemek için sakin uyku rutinleri",
                "description": "Zihinsel dengemizi korumanın anahtarlarından biri kaliteli bir uykudur. Bu akşam uyku saatinden yarım saat önce ekranları kapatıp dinlenmeye geçmek gücünüzü tazeleyecektir.",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
    # 5. Cap Enforcement: Order by severity precedence and limit to maximum 3 items
    severity_order = {"priority_support": 3, "supportive": 2, "gentle": 1}
    interventions.sort(key=lambda x: severity_order.get(x["severity"], 0), reverse=True)
    
    final_interventions = interventions[:3]
    
    duration_ms = (time.time() - start_time) * 1000
    
    # 6. Structured Performance Logging
    logger.info(
        f"INTERVENTION_ENGINE | UserID: {user_id} | Days: {days} | "
        f"intervention_generation_duration: {duration_ms:.2f}ms | "
        f"intervention_count: {final_interventions} | "
        f"dominant_emotion: '{dominant_emotion}' | "
        f"crisis_detected: {crisis_detected}"
    )
    
    return final_interventions
