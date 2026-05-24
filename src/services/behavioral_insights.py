import time
import logging
from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict
from src.services.database import get_user_emotion_timeline

logger = logging.getLogger(__name__)

def generate_behavioral_insights(user_id: str, days: int = 7) -> List[Dict]:
    """
    Parses user emotion events over a period to extract rule-based behavioral insights.
    Completely privacy-safe: uses only emotion and risk metadata, no raw user messages.
    Completely crisis-safe: does NOT diagnose clinical conditions, provides only supportive context.
    Enforces a minimum message count threshold of 4 to prevent false positives.
    """
    start_time = time.time()
    
    # 1. Fetch user emotion events timeline (sorted chronologically ascending)
    events = get_user_emotion_timeline(user_id=user_id, days=days)
    total_messages = len(events)
    
    # 2. Strict Threshold Enforcement: if < 4, return empty immediately to avoid premature analysis
    if total_messages < 4:
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"INSIGHT_ENGINE | UserID: {user_id} | Days: {days} | "
            f"Not enough data. Total messages: {total_messages} (min: 4). "
            f"Latency: {duration_ms:.2f}ms"
        )
        return []
        
    insights = []
    
    # Pre-calculate emotional frequencies and flags
    crisis_count = 0
    anxiety_count = 0
    sadness_count = 0
    joy_count = 0
    anger_count = 0
    
    emotions_list = []
    dates_list = []
    
    for e in events:
        em = (e.get("emotion") or "neutral").lower()
        risk = (e.get("risk") or "Normal").lower()
        
        emotions_list.append(em)
        
        # Parse created_at datetime safely
        try:
            dt = datetime.fromisoformat(e["created_at"])
            dates_list.append(dt.date())
        except Exception:
            dates_list.append(datetime.now(timezone.utc).date())
            
        if risk in ["kriz", "1", "crisis"]:
            crisis_count += 1
            
        if em in ["anxiety", "kaygı", "stres", "stress"]:
            anxiety_count += 1
        elif em in ["sadness", "üzüntü", "sad", "durgun"]:
            sadness_count += 1
        elif em in ["joy", "happiness", "mutlu", "neşe", "mutluluk"]:
            joy_count += 1
        elif em in ["anger", "öfke", "angry", "kızgın"]:
            anger_count += 1
            
    anxiety_rate = anxiety_count / total_messages
    sadness_rate = sadness_count / total_messages
    joy_rate = joy_count / total_messages
    
    # Calculate dominant emotion
    counts = Counter(emotions_list)
    dominant_emotion = counts.most_common(1)[0][0] if emotions_list else "neutral"
    
    # 3. Rule-Based Inference Engine
    
    # Rule 1: crisis_risk_pattern
    if crisis_count >= 2:
        confidence = min(1.0, 0.70 + (crisis_count * 0.05))
        insights.append({
            "type": "crisis_risk_pattern",
            "severity": "high",
            "confidence": round(confidence, 2),
            "title": "Hassas duygu durum örüntüsü",
            "description": "Son dönemdeki etkileşimlerinizde yüksek düzeyde stres ve hassasiyet belirtileri gözlemlendi. Destekleyici yaklaşımlara ve gerektiğinde 112 veya 114 Psikolojik Destek Hattı gibi uzman kanallara başvurabileceğinizi unutmayın.",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
    # Rule 2: repeated_anxiety
    if anxiety_rate > 0.35:
        severity = "high" if anxiety_rate >= 0.60 else "medium"
        confidence = min(1.0, 0.60 + (anxiety_rate * 0.40))
        insights.append({
            "type": "repeated_anxiety",
            "severity": severity,
            "confidence": round(confidence, 2),
            "title": "Kaygı temalı örüntüler",
            "description": "Son günlerdeki sohbetlerinizde kaygı, huzursuzluk ve stres içerikli ifadelerin yoğunlaştığı fark edildi. Gün içinde kısa nefes egzersizleri ve hafif yürüyüşler zihninizi rahatlatmaya yardımcı olabilir.",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
    # Rule 3: prolonged_sadness
    sadness_distinct_days = len(set(dates_list[i] for i, em in enumerate(emotions_list) if em in ["sadness", "üzüntü", "sad", "durgun"]))
    if sadness_rate > 0.35 or sadness_distinct_days >= 3:
        severity = "medium" if sadness_rate >= 0.35 else "low"
        confidence = min(1.0, 0.50 + (sadness_rate * 0.50))
        insights.append({
            "type": "prolonged_sadness",
            "severity": severity,
            "confidence": round(confidence, 2),
            "title": "Düşük duygu durumu eğilimi",
            "description": "Son paylaşımlarınızda üzüntü ve durgunluk eğilimleri sıkça gözlemlendi. Duygularınızı güvendiğiniz bir yakınınızla paylaşmak veya sevdiğiniz aktivitelere küçük adımlarla zaman ayırmak kendinizi daha hafif hissettirebilir.",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
    # Rule 4: stress_increase
    if total_messages >= 4:
        mid = total_messages // 2
        first_half = emotions_list[:mid]
        second_half = emotions_list[mid:]
        
        stress_emotions = ["anxiety", "kaygı", "stres", "stress", "anger", "öfke", "angry", "fear", "korku", "sadness", "üzüntü", "sad"]
        first_stress_count = sum(1 for em in first_half if em in stress_emotions)
        second_stress_count = sum(1 for em in second_half if em in stress_emotions)
        
        first_stress_rate = first_stress_count / len(first_half)
        second_stress_rate = second_stress_count / len(second_half)
        
        if second_stress_rate - first_stress_rate >= 0.20:
            increase_amount = second_stress_rate - first_stress_rate
            confidence = min(1.0, 0.70 + (increase_amount * 0.50))
            insights.append({
                "type": "stress_increase",
                "severity": "medium",
                "confidence": round(confidence, 2),
                "title": "Stres seviyesinde artış trendi",
                "description": "Görüşmelerinizin ilerleyen günlerindeki duygu durumunuzda stres, gerginlik ve yorgunluk eğilimlerinin arttığı gözlemlendi. Kendinize küçük dinlenme araları vermeyi ihmal etmeyin.",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
    # Rule 5: emotional_instability (volatility)
    positive_emotions = ["joy", "happiness", "mutlu", "neşe", "mutluluk"]
    negative_emotions = ["sadness", "üzüntü", "sad", "anxiety", "kaygı", "stres", "stress", "anger", "öfke", "angry", "fear", "korku"]
    
    transitions = 0
    last_type = None
    
    for em in emotions_list:
        if em in positive_emotions:
            current_type = "pos"
        elif em in negative_emotions:
            current_type = "neg"
        else:
            current_type = None
            
        if current_type and last_type and current_type != last_type:
            transitions += 1
            
        if current_type:
            last_type = current_type
            
    if transitions >= 3:
        confidence = min(1.0, 0.50 + (transitions * 0.10))
        insights.append({
            "type": "emotional_instability",
            "severity": "medium",
            "confidence": round(confidence, 2),
            "title": "Dalgalı duygu durumu seyri",
            "description": "Kısa zaman aralıklarında duygu durumunuzda ani iniş çıkışlar ve değişimler gözlemlendi. Bu dalgalanmalar yorucu olabilir; düzenli uyku, hafif egzersizler ve stabil rutinler dengede kalmanıza yardımcı olabilir.",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
    # Rule 6: positive_recovery
    joy_recovery = False
    if total_messages >= 4:
        mid = total_messages // 2
        first_half = emotions_list[:mid]
        second_half = emotions_list[mid:]
        
        first_joy_rate = sum(1 for em in first_half if em in positive_emotions) / len(first_half)
        second_joy_rate = sum(1 for em in second_half if em in positive_emotions) / len(second_half)
        
        if second_joy_rate - first_joy_rate >= 0.15:
            joy_recovery = True
            
    if len(emotions_list) >= 3:
        last_3 = emotions_list[-3:]
        last_3_joy = sum(1 for em in last_3 if em in positive_emotions)
        if last_3_joy >= 2:
            joy_recovery = True
            
    if joy_recovery:
        confidence = min(1.0, 0.60 + (joy_rate * 0.40))
        insights.append({
            "type": "positive_recovery",
            "severity": "low",
            "confidence": round(confidence, 2),
            "title": "Duygu durumunda olumlu gelişim",
            "description": "Son dönemdeki sohbetlerinizde olumlu hislerin, umut verici ve neşeli duyguların arttığı gözlemlendi. Bu olumlu gidişatı pekiştirmek için size keyif veren aktivitelere devam edebilirsiniz.",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    duration_ms = (time.time() - start_time) * 1000
    
    # 4. Structured Performance Log
    logger.info(
        f"INSIGHT_ENGINE | UserID: {user_id} | Days: {days} | "
        f"insight_generation_duration: {duration_ms:.2f}ms | "
        f"insight_count: {len(insights)} | "
        f"dominant_emotion: '{dominant_emotion}' | "
        f"crisis_count: {crisis_count}"
    )
    
    return insights
