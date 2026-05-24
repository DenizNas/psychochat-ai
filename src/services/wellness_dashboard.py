import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from src.services.database import (
    get_user_emotion_summary,
    get_user_emotion_timeline,
    get_mood_journals_for_user,
    get_scheduled_interventions_for_user,
    get_notification_events_for_user
)
from src.services.behavioral_insights import generate_behavioral_insights
from src.services.smart_interventions import generate_smart_interventions
from src.services.wellness_reports import generate_wellness_report
from src.services.reflection_engine import generate_reflection

logger = logging.getLogger(__name__)


def generate_wellness_dashboard(user_id: str, days: int = 7) -> Dict[str, Any]:
    """
    Metadata-driven dashboard aggregation service for Phase 8 Prompt 6.
    Compiles emotional distribution, journal activity, insights, notifications,
    active interventions, and computes a non-diagnostic, privacy-safe wellness score.
    """
    start_time = time.time()
    try:
        # 1. Fetch analytical metadata via secure db/service layer (raw-text free)
        emotion_summary = get_user_emotion_summary(user_id=user_id, days=days)
        insights = generate_behavioral_insights(user_id=user_id, days=days)
        active_interventions = generate_smart_interventions(user_id=user_id, days=days)
        
        scheduled_interventions = get_scheduled_interventions_for_user(user_id=user_id)
        notifications = get_notification_events_for_user(user_id=user_id)
        mood_journals = get_mood_journals_for_user(user_id=user_id, days=days)
        
        period = "daily" if days == 1 else "weekly"
        latest_report = generate_wellness_report(user_id=user_id, period=period, days=days)
        latest_reflection = generate_reflection(user_id=user_id, period=period)
        
    except Exception as e:
        logger.error(f"DASHBOARD_ENGINE | Secure query aggregation failed: {e}")
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"DASHBOARD_ENGINE | UserID: {user_id} | "
            f"dashboard_generation_duration: {duration_ms:.2f}ms | "
            f"dashboard_days: {days} | total_messages: 0 | "
            f"wellness_score: None | crisis_count: 0 | section_count: 0"
        )
        return {
            "days": days,
            "overview": {
                "total_messages": 0,
                "dominant_emotion": "Nötr",
                "crisis_count": 0,
                "journal_count": 0,
                "scheduled_intervention_count": 0,
                "notification_count": 0
            },
            "wellness_score": {
                "score": None,
                "label": "Hizmet Dışı",
                "description": "Dashboard yüklenirken sunucu tarafında bir hata oluştu."
            },
            "sections": {
                "emotion_distribution": {},
                "daily_trend": [],
                "top_insights": [],
                "active_interventions": [],
                "latest_reflection": {},
                "latest_report": {}
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    total_messages = emotion_summary.get("total_messages", 0)
    crisis_count = emotion_summary.get("crisis_count", 0)
    dominant_emotion = emotion_summary.get("dominant_emotion", "Nötr")
    journal_count = len(mood_journals)
    
    # 2. Counts inside timeframe
    scheduled_count = len(scheduled_interventions)
    
    notification_count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for n in notifications:
        try:
            n_time = datetime.fromisoformat(n["scheduled_for"].replace("Z", "+00:00"))
            if n_time >= cutoff:
                notification_count += 1
        except Exception:
            pass

    # 3. Wellness Score Math (Privacy & Crisis Safe)
    total_data_count = total_messages + journal_count
    
    if total_data_count < 4:
        score = None
        score_label = "Yetersiz Veri"
        score_desc = "Henüz yeterli veri oluşmadığı için genel wellness eğilim skoru hesaplanamadı."
    else:
        current_score = 70
        
        # Emotion contributions
        dist = emotion_summary.get("emotion_distribution", {})
        pos_count = 0
        neg_count = 0
        for emotion, count in dist.items():
            em_lower = emotion.lower()
            if em_lower in ["mutluluk", "sakin", "joy", "calm", "happiness", "neşe"]:
                pos_count += count
            elif em_lower in ["kaygı", "anxiety", "stres", "stress", "üzüntü", "sadness", "sad", "durgun", "melankolik", "öfke", "anger", "angry", "yorgun", "tired"]:
                neg_count += count
                
        # Positives add up to +20 max
        current_score += min(20, pos_count * 5)
        # Negatives subtract up to -25 max
        current_score -= min(25, neg_count * 4)
        
        # Mood Journal contributions
        pos_journal = 0
        neg_journal = 0
        for j in mood_journals:
            j_mood = j.get("mood", "").lower()
            intensity = j.get("intensity", 3)
            if j_mood in ["happy", "calm"]:
                pos_journal += intensity
            elif j_mood in ["anxious", "sad", "angry", "tired"]:
                neg_journal += intensity
                
        current_score += min(10, pos_journal * 2)
        current_score -= min(15, neg_journal * 2)
        
        # Behavioral insights contributions
        insight_types = {ins["type"] for ins in insights}
        if "positive_recovery" in insight_types:
            current_score += 10
        if "stress_increase" in insight_types or "crisis_risk_pattern" in insight_types:
            current_score -= 15
            
        # Crisis strict override (ensure score is clamped and capped realistically)
        if crisis_count >= 1 or "crisis_risk_pattern" in insight_types:
            current_score = min(current_score, 40)
            
        score = max(10, min(100, current_score))
        
        if score >= 90:
            score_label = "Yüksek İçsel Denge"
            score_desc = "Duygusal esnekliğinizin ve sakin anlarınızın oldukça belirgin olduğu gözlemlendi."
        elif score >= 70:
            score_label = "Dengelenme Süreci"
            score_desc = "Duygu seyrinizin hafif dalgalanmalarla birlikte genel bir denge eğiliminde olduğu gözlemlendi."
        elif score >= 50:
            score_label = "Hassas Denge Eğilimi"
            score_desc = "Zaman zaman stres veya duygusal yoğunlukların öne çıktığı gözlemlendi; dinlenmeye alan açmak iyi gelebilir."
        else:
            score_label = "Yoğun Duygusal Dönem"
            score_desc = "Son zamanlarda duygusal yoğunluğun veya stres eşiğinin oldukça yüksek olduğu gözlemlendi. Kendinize şefkat göstermek ve destek kanallarını değerlendirmek yararlı olabilir."

    # Build safe sections (capped at 3 items to optimize payload size)
    top_insights = insights[:3]
    active_interventions_list = active_interventions[:3]
    
    sections = {
        "emotion_distribution": emotion_summary.get("emotion_distribution", {}),
        "daily_trend": emotion_summary.get("daily_trend", []),
        "top_insights": top_insights,
        "active_interventions": active_interventions_list,
        "latest_reflection": latest_reflection,
        "latest_report": latest_report
    }

    duration_ms = (time.time() - start_time) * 1000
    section_count = len([k for k, v in sections.items() if v])

    # 4. Structured performance metrics log
    logger.info(
        f"DASHBOARD_ENGINE | UserID: {user_id} | "
        f"dashboard_generation_duration: {duration_ms:.2f}ms | "
        f"dashboard_days: {days} | total_messages: {total_messages} | "
        f"wellness_score: {score} | crisis_count: {crisis_count} | "
        f"section_count: {section_count}"
    )

    return {
        "days": days,
        "overview": {
            "total_messages": total_messages,
            "dominant_emotion": dominant_emotion,
            "crisis_count": crisis_count,
            "journal_count": journal_count,
            "scheduled_intervention_count": scheduled_count,
            "notification_count": notification_count
        },
        "wellness_score": {
            "score": score,
            "label": score_label,
            "description": score_desc + " Bu skor yalnızca genel wellness eğilimini gösterir; tıbbi bir değerlendirme değildir."
        },
        "sections": sections,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
