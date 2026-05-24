import os
import time
import logging
from datetime import datetime, timedelta, timezone, time as datetime_time
from typing import List, Dict

from src.services.database import (
    SessionLocal,
    ScheduledIntervention,
    get_user_emotion_summary,
    cancel_pending_interventions,
    save_scheduled_intervention
)
from src.services.behavioral_insights import generate_behavioral_insights

logger = logging.getLogger(__name__)

# Enforce permanent Europe/Istanbul (UTC+3) timezone
ISTANBUL_TZ = timezone(timedelta(hours=3))


def schedule_user_interventions(user_id: str) -> List[Dict]:
    """
    Main scheduling engine for Phase 8.
    Analyzes user insights and aggregates them into a personalized, quiet-hours-safe,
    cooldown-compliant, daily-capped intervention list.
    
    Returns the refreshed list of scheduled interventions.
    """
    start_time = time.time()
    
    scheduled_count = 0
    skipped_due_to_quiet_hours = 0
    skipped_due_to_cooldown = 0
    crisis_override_active = False
    
    # 1. Graceful DB Fallback / Exception Shielding
    try:
        summary = get_user_emotion_summary(user_id=user_id, days=7)
        insights = generate_behavioral_insights(user_id=user_id, days=7)
    except Exception as e:
        logger.error(f"INTERVENTION_SCHEDULER | Graceful Fallback triggered. DB or Insight Service unavailable: {e}")
        # Return empty schedule or empty list safely without crashing
        return []

    # 2. Check for active crisis OR crisis_risk_pattern in insights
    crisis_count = summary.get("crisis_count", 0)
    insight_types = {ins["type"] for ins in insights}
    
    if crisis_count >= 1 or "crisis_risk_pattern" in insight_types:
        crisis_override_active = True
        
    db = SessionLocal()
    try:
        if crisis_override_active:
            # CRISIS OVERRIDE: Clear standard pending interventions, prioritize emergency guidance
            cancel_pending_interventions(user_id)
            
            # Schedule immediate high-priority safety guidance (bypasses quiet hours due to immediate safety)
            now_utc = datetime.now(timezone.utc)
            scheduled_time_utc = now_utc + timedelta(minutes=1)
            
            # Save crisis intervention to DB
            save_scheduled_intervention(
                user_id=user_id,
                intervention_type="priority_support",
                scheduled_for=scheduled_time_utc,
                status="pending",
                priority="high",
                source_insight="crisis_risk_pattern",
                delivery_channel="in_app"
            )
            scheduled_count += 1
            logger.warning(f"INTERVENTION_SCHEDULER | CRISIS OVERRIDE active for UserID: {user_id}. Safety guidance scheduled.")
            
        else:
            # NORMAL SCHEDULING FLOW
            # Cancel previous pending standard interventions to rebuild latest deterministic timeline
            cancel_pending_interventions(user_id)
            
            # Prepare tomorrow's base date in Europe/Istanbul timezone
            now_local = datetime.now(ISTANBUL_TZ)
            tomorrow_local_date = (now_local + timedelta(days=1)).date()
            
            # Map candidate interventions based on rules
            candidates = []
            
            # Rule 1: repeated_anxiety -> sabah breathing_break (09:00)
            if "repeated_anxiety" in insight_types:
                t_local = datetime.combine(tomorrow_local_date, datetime_time(9, 0), ISTANBUL_TZ)
                candidates.append({
                    "type": "breathing_break",
                    "time_local": t_local,
                    "priority": "medium",
                    "source": "repeated_anxiety"
                })
                
            # Rule 2: stress_increase -> öğleden sonra short_walk (14:00)
            if "stress_increase" in insight_types:
                t_local = datetime.combine(tomorrow_local_date, datetime_time(14, 0), ISTANBUL_TZ)
                candidates.append({
                    "type": "short_walk",
                    "time_local": t_local,
                    "priority": "medium",
                    "source": "stress_increase"
                })
                
            # Rule 3: prolonged_sadness -> akşam social_connection (19:00)
            if "prolonged_sadness" in insight_types:
                t_local = datetime.combine(tomorrow_local_date, datetime_time(19, 0), ISTANBUL_TZ)
                candidates.append({
                    "type": "social_connection",
                    "time_local": t_local,
                    "priority": "medium",
                    "source": "prolonged_sadness"
                })
                
            # Rule 4: emotional_instability -> grounding_exercise (11:00)
            if "emotional_instability" in insight_types:
                t_local = datetime.combine(tomorrow_local_date, datetime_time(11, 0), ISTANBUL_TZ)
                candidates.append({
                    "type": "grounding_exercise",
                    "time_local": t_local,
                    "priority": "medium",
                    "source": "emotional_instability"
                })
                
            # Rule 5: positive_recovery -> positive_reflection (16:00)
            if "positive_recovery" in insight_types:
                t_local = datetime.combine(tomorrow_local_date, datetime_time(16, 0), ISTANBUL_TZ)
                candidates.append({
                    "type": "positive_reflection",
                    "time_local": t_local,
                    "priority": "low",
                    "source": "positive_recovery"
                })
                
            # Fallbacks: If no behavioral insights are generated (stable or insufficient history), schedule gentle fallbacks
            if not candidates:
                # Fallback 1: hydration_reminder (10:00)
                t_local1 = datetime.combine(tomorrow_local_date, datetime_time(10, 0), ISTANBUL_TZ)
                candidates.append({
                    "type": "hydration_reminder",
                    "time_local": t_local1,
                    "priority": "low",
                    "source": "fallback_hydration"
                })
                
                # Fallback 2: sleep_reminder (22:00)
                t_local2 = datetime.combine(tomorrow_local_date, datetime_time(22, 0), ISTANBUL_TZ)
                candidates.append({
                    "type": "sleep_reminder",
                    "time_local": t_local2,
                    "priority": "low",
                    "source": "fallback_sleep"
                })
                
            # Sort proposed interventions by priority: high -> medium -> low
            priority_order = {"high": 3, "medium": 2, "low": 1}
            candidates.sort(key=lambda x: priority_order.get(x["priority"], 0), reverse=True)
            
            # Keep at most 3 daily capped recommendations
            daily_limit = 3
            scheduled_for_day = 0
            
            for cand in candidates:
                if scheduled_for_day >= daily_limit:
                    break
                    
                time_local = cand["time_local"]
                time_utc = time_local.astimezone(timezone.utc).replace(tzinfo=None)
                
                # 3. Quiet Hours Check (23:00 - 08:00 user local time)
                if time_local.hour >= 23 or time_local.hour < 8:
                    skipped_due_to_quiet_hours += 1
                    logger.info(f"INTERVENTION_SCHEDULER | Skipped {cand['type']} due to Quiet Hours ({time_local.hour}:00).")
                    continue
                
                # 4. Cooldown Check (12 hours since last scheduled of same type)
                cooldown_start = time_utc - timedelta(hours=12)
                cooldown_end = time_utc + timedelta(hours=12)
                
                existing_duplicate = db.query(ScheduledIntervention).filter(
                    ScheduledIntervention.user_id == user_id,
                    ScheduledIntervention.intervention_type == cand["type"],
                    ScheduledIntervention.status.in_(["pending", "delivered"]),
                    ScheduledIntervention.scheduled_for >= cooldown_start,
                    ScheduledIntervention.scheduled_for <= cooldown_end
                ).first()
                
                if existing_duplicate:
                    skipped_due_to_cooldown += 1
                    logger.info(f"INTERVENTION_SCHEDULER | Skipped {cand['type']} due to 12h cooldown.")
                    continue
                
                # Commit to DB
                save_scheduled_intervention(
                    user_id=user_id,
                    intervention_type=cand["type"],
                    scheduled_for=time_utc,
                    status="pending",
                    priority=cand["priority"],
                    source_insight=cand["source"],
                    delivery_channel="in_app"
                )
                
                scheduled_count += 1
                scheduled_for_day += 1

    except Exception as e:
        logger.error(f"INTERVENTION_SCHEDULER | Error during scheduling logic: {e}")
    finally:
        db.close()
        
    duration_ms = (time.time() - start_time) * 1000
    
    # 5. Structured performance log
    logger.info(
        f"INTERVENTION_SCHEDULER | UserID: {user_id} | "
        f"scheduler_duration: {duration_ms:.2f}ms | "
        f"scheduled_count: {scheduled_count} | "
        f"skipped_due_to_quiet_hours: {skipped_due_to_quiet_hours} | "
        f"skipped_due_to_cooldown: {skipped_due_to_cooldown} | "
        f"crisis_override_active: {crisis_override_active}"
    )
    
    # Fetch final sorted list to return
    from src.services.database import get_scheduled_interventions_for_user
    return get_scheduled_interventions_for_user(user_id)
