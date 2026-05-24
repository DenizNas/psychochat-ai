import time
import logging
from datetime import datetime, timedelta, timezone, time as datetime_time
from typing import List, Dict

from src.services.database import (
    SessionLocal,
    UserProfile,
    ScheduledIntervention,
    NotificationEvent,
    get_user_emotion_summary,
    save_notification_event,
    cancel_pending_notifications_for_type
)

logger = logging.getLogger(__name__)

# Enforce permanent Europe/Istanbul (UTC+3) timezone
ISTANBUL_TZ = timezone(timedelta(hours=3))

NOTIFICATION_TEMPLATES = {
    "breathing_break": {
        "title": "Nefes Mola Vakti 🌿",
        "body": "Küçük bir mola iyi gelebilir. Birlikte 1 dakika derin nefes alalım mı?"
    },
    "short_walk": {
        "title": "Kısa Bir Adım 🚶",
        "body": "Şöyle bir esnemek ve temiz hava almak zihninizi tazeleyebilir."
    },
    "social_connection": {
        "title": "Bağ Kurma Zamanı ✨",
        "body": "Sevdiğiniz birine küçük bir selam yazmak bugün size çok iyi gelebilir."
    },
    "grounding_exercise": {
        "title": "Şimdi ve Burada 🌸",
        "body": "Çevrenizdeki 5 şeyi fark ederek ana dönmeye ne dersiniz?"
    },
    "positive_reflection": {
        "title": "Günün Güzel Anı 📝",
        "body": "Bugün yaşadığınız küçük de olsa güzel bir detayı hatırlamak ister misiniz?"
    },
    "hydration_reminder": {
        "title": "Küçük Bir Yudum Su 💧",
        "body": "Vücudunuza ve zihninize iyi bakmak için küçük bir yudum su alabilirsiniz."
    },
    "sleep_reminder": {
        "title": "Dinlenme Zamanı Yaklaşıyor 💤",
        "body": "Zihninizi dinlendirmek için ekranı kapatıp sakin bir hazırlık yapmaya ne dersiniz?"
    },
    "daily_report": {
        "title": "Günlük Raporunuz Hazır 📊",
        "body": "Gününüzün duygusal yansımalarını incelemek için raporunuza göz atabilirsiniz."
    },
    "weekly_report": {
        "title": "Haftalık Wellness Raporu 📅",
        "body": "Geçen haftanın duygu eğilimlerini ve destekleyici önerilerini keşfedin."
    },
    "mood_journal_reminder": {
        "title": "Duygu Günlüğü Hatırlatıcısı ✍️",
        "body": "Bugün nasıl hissettiğinizi kendinize fısıldamak için küçük bir not bırakabilirsiniz."
    },
    "crisis": {
        "title": "Öncelikli Destek ve Yanındayız 💜",
        "body": "Çok zor anlarda yalnız değilsiniz. Destek kanallarımıza her an göz atabilirsiniz."
    }
}


def refresh_user_notifications(user_id: str) -> List[Dict]:
    """
    Main Push Notification Planning Service for Phase 8.
    Analyzes preferences, scheduled interventions, and reports, then plans a daily-capped, 
    quiet-hours-safe, cooldown-compliant notification schedule.
    """
    start_time = time.time()
    db = SessionLocal()
    
    scheduled_count = 0
    skipped_due_to_preference = False
    skipped_due_to_quiet_hours = 0
    skipped_due_to_cooldown = 0
    crisis_override_active = False

    try:
        # 1. Preferences Validation
        profile = db.query(UserProfile).filter(UserProfile.username == user_id).first()
        notifications_enabled = profile.notifications_enabled if profile else True

        if not notifications_enabled:
            skipped_due_to_preference = True
            # Cancel all existing pending notification events
            pending_events = db.query(NotificationEvent).filter(
                NotificationEvent.user_id == user_id,
                NotificationEvent.status == "pending"
            ).all()
            for pev in pending_events:
                pev.status = "cancelled"
            db.commit()
            logger.info(f"NOTIFICATION_PLANNER | Notifications disabled for user: {user_id}. Cleaned pending items.")
            return []

        # 2. Check for Crisis Active states
        summary = get_user_emotion_summary(user_id=user_id, days=7)
        if summary.get("crisis_count", 0) >= 1:
            crisis_override_active = True

        # Clean previous pending notifications to recreate tomorrow's clean schedule
        db.query(NotificationEvent).filter(
            NotificationEvent.user_id == user_id,
            NotificationEvent.status == "pending"
        ).delete()
        db.commit()

        if crisis_override_active:
            # CRISIS PATH: schedule supportive warning immediate notification (bypasses quiet hours)
            now_utc = datetime.now(timezone.utc)
            scheduled_time = now_utc + timedelta(minutes=1)
            
            save_notification_event(
                user_id=user_id,
                notification_type="crisis",
                title=NOTIFICATION_TEMPLATES["crisis"]["title"],
                body=NOTIFICATION_TEMPLATES["crisis"]["body"],
                scheduled_for=scheduled_time,
                status="pending",
                source="crisis_system"
            )
            scheduled_count += 1
            logger.warning(f"NOTIFICATION_PLANNER | Crisis registered for user {user_id}. Scheduled immediate safety guidance.")

        else:
            # NORMAL WELLNESS PATH
            now_local = datetime.now(ISTANBUL_TZ)
            tomorrow_local_date = (now_local + timedelta(days=1)).date()

            # Retrieve tomorrow's scheduled interventions
            tomorrow_start_utc = datetime.combine(tomorrow_local_date, datetime_time(0, 0)).astimezone(timezone.utc).replace(tzinfo=None)
            tomorrow_end_utc = datetime.combine(tomorrow_local_date, datetime_time(23, 59)).astimezone(timezone.utc).replace(tzinfo=None)

            interventions = db.query(ScheduledIntervention).filter(
                ScheduledIntervention.user_id == user_id,
                ScheduledIntervention.scheduled_for >= tomorrow_start_utc,
                ScheduledIntervention.scheduled_for <= tomorrow_end_utc,
                ScheduledIntervention.status == "pending"
            ).all()

            candidates = []
            
            # Map ScheduledInterventions to candidates
            for iv in interventions:
                # convert UTC back to Europe/Istanbul timezone
                local_time = iv.scheduled_for.replace(tzinfo=timezone.utc).astimezone(ISTANBUL_TZ)
                templates = NOTIFICATION_TEMPLATES.get(iv.intervention_type, {
                    "title": "Zaman Ayırma Zamanı 🌸",
                    "body": "Kendiniz için küçük bir mola verip günlüğünüze göz atın."
                })
                candidates.append({
                    "type": "scheduled_intervention",
                    "title": templates["title"],
                    "body": templates["body"],
                    "time_local": local_time
                })

            # Add a Mood Journal Reminder candidate for tomorrow at 20:00 (quiet-hours-safe slot)
            mood_time = datetime.combine(tomorrow_local_date, datetime_time(20, 0), ISTANBUL_TZ)
            candidates.append({
                "type": "mood_journal_reminder",
                "title": NOTIFICATION_TEMPLATES["mood_journal_reminder"]["title"],
                "body": NOTIFICATION_TEMPLATES["mood_journal_reminder"]["body"],
                "time_local": mood_time
            })

            # Sort by time local
            candidates.sort(key=lambda x: x["time_local"])

            # Cap at max 3 daily notifications
            daily_limit = 3
            scheduled_today = 0

            for cand in candidates:
                if scheduled_today >= daily_limit:
                    break

                time_local = cand["time_local"]
                time_utc = time_local.astimezone(timezone.utc).replace(tzinfo=None)

                # 3. Quiet Hours Check (23:00 - 08:00 local time)
                if time_local.hour >= 23 or time_local.hour < 8:
                    skipped_due_to_quiet_hours += 1
                    logger.info(f"NOTIFICATION_PLANNER | Skipped due to Quiet Hours: {cand['title']}")
                    continue

                # 4. 12-Hour Cooldown Check
                cooldown_start = time_utc - timedelta(hours=12)
                cooldown_end = time_utc + timedelta(hours=12)

                existing_dup = db.query(NotificationEvent).filter(
                    NotificationEvent.user_id == user_id,
                    NotificationEvent.notification_type == cand["type"],
                    NotificationEvent.status.in_(["pending", "delivered"]),
                    NotificationEvent.scheduled_for >= cooldown_start,
                    NotificationEvent.scheduled_for <= cooldown_end
                ).first()

                if existing_dup:
                    skipped_due_to_cooldown += 1
                    logger.info(f"NOTIFICATION_PLANNER | Skipped due to Cooldown: {cand['title']}")
                    continue

                save_notification_event(
                    user_id=user_id,
                    notification_type=cand["type"],
                    title=cand["title"],
                    body=cand["body"],
                    scheduled_for=time_utc,
                    status="pending",
                    source="scheduler"
                )
                scheduled_count += 1
                scheduled_today += 1

    except Exception as e:
        logger.error(f"NOTIFICATION_PLANNER | Error during refresh: {e}")
    finally:
        db.close()

    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        f"NOTIFICATION_PLANNER | UserID: {user_id} | "
        f"planner_duration: {duration_ms:.2f}ms | "
        f"scheduled_count: {scheduled_count} | "
        f"skipped_due_to_preference: {skipped_due_to_preference} | "
        f"skipped_due_to_quiet_hours: {skipped_due_to_quiet_hours} | "
        f"skipped_due_to_cooldown: {skipped_due_to_cooldown} | "
        f"crisis_override_active: {crisis_override_active}"
    )

    from src.services.database import get_notification_events_for_user
    return get_notification_events_for_user(user_id)
