import logging
from src.workers.celery_app import celery_app
from src.core.redis_client import redis_client
from src.core.cache import cache_set, TTL_DASHBOARD, TTL_REPORTS
from src.services.database import get_all_usernames, cleanup_old_emotion_events
from src.services.intervention_scheduler import schedule_user_interventions
from src.services.notification_service import refresh_user_notifications
from src.services.wellness_reports import generate_wellness_report
from src.services.wellness_dashboard import generate_wellness_dashboard

logger = logging.getLogger(__name__)

def acquire_redis_lock(lock_name: str, timeout: int = 120) -> bool:
    """
    Acquires a simple distributed lock in Redis to ensure task idempotency
    and prevent overlapping scheduler execution.
    If Redis is unavailable, prints a warning and proceeds to execute (graceful fallback).
    """
    try:
        r = redis_client.client
        if r:
            # Set key only if it doesn't exist (NX) with an expiration timeout (EX)
            acquired = r.set(f"lock:task:{lock_name}", "1", nx=True, ex=timeout)
            return bool(acquired)
    except Exception as e:
        logger.warning(f"REDIS_LOCK | Error checking lock {lock_name}. Falling back to default execution. Details: {e}")
    return True  # Fallback gracefully by letting the task run

def release_redis_lock(lock_name: str):
    """Releases the lock to allow subsequent scheduled runs."""
    try:
        r = redis_client.client
        if r:
            r.delete(f"lock:task:{lock_name}")
    except Exception as e:
        logger.warning(f"REDIS_LOCK | Failed to release lock {lock_name}. Details: {e}")

@celery_app.task
def refresh_scheduled_interventions_task():
    """Refreshes scheduled wellness interventions for all active users."""
    if not acquire_redis_lock("refresh_scheduled_interventions", timeout=300):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: refresh_scheduled_interventions_task")
        return "skipped"
    try:
        users = get_all_usernames()
        logger.info(f"WORKER_TASK | Starting interventions refresh for {len(users)} users.")
        for username in users:
            try:
                schedule_user_interventions(user_id=username)
            except Exception as e:
                logger.error(f"WORKER_TASK | Failed to schedule interventions for {username}. Details: {e}")
        return "completed"
    finally:
        release_redis_lock("refresh_scheduled_interventions")

@celery_app.task
def refresh_notification_events_task():
    """Refreshes planned push notifications for all active users."""
    if not acquire_redis_lock("refresh_notification_events", timeout=300):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: refresh_notification_events_task")
        return "skipped"
    try:
        users = get_all_usernames()
        logger.info(f"WORKER_TASK | Starting push notifications plan refresh for {len(users)} users.")
        for username in users:
            try:
                refresh_user_notifications(user_id=username)
            except Exception as e:
                logger.error(f"WORKER_TASK | Failed to refresh notification plan for {username}. Details: {e}")
        return "completed"
    finally:
        release_redis_lock("refresh_notification_events")

@celery_app.task
def prepare_daily_wellness_reports_task():
    """Pre-generates and caches daily wellness reports for all active users (cache warming)."""
    if not acquire_redis_lock("prepare_daily_wellness_reports", timeout=600):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: prepare_daily_wellness_reports_task")
        return "skipped"
    try:
        users = get_all_usernames()
        logger.info(f"WORKER_TASK | Pre-generating Daily Reports for {len(users)} users.")
        for username in users:
            try:
                report = generate_wellness_report(user_id=username, period="daily", days=7)
                cache_set(username, "wellness_report", report, TTL_REPORTS, "daily", 7)
            except Exception as e:
                logger.error(f"WORKER_TASK | Failed to pre-generate Daily Report for {username}. Details: {e}")
        return "completed"
    finally:
        release_redis_lock("prepare_daily_wellness_reports")

@celery_app.task
def prepare_weekly_wellness_reports_task():
    """Pre-generates and caches weekly wellness reports for all active users (cache warming)."""
    if not acquire_redis_lock("prepare_weekly_wellness_reports", timeout=600):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: prepare_weekly_wellness_reports_task")
        return "skipped"
    try:
        users = get_all_usernames()
        logger.info(f"WORKER_TASK | Pre-generating Weekly Reports for {len(users)} users.")
        for username in users:
            try:
                report = generate_wellness_report(user_id=username, period="weekly", days=7)
                cache_set(username, "wellness_report", report, TTL_REPORTS, "weekly", 7)
            except Exception as e:
                logger.error(f"WORKER_TASK | Failed to pre-generate Weekly Report for {username}. Details: {e}")
        return "completed"
    finally:
        release_redis_lock("prepare_weekly_wellness_reports")

@celery_app.task
def refresh_dashboard_aggregation_cache_task():
    """Warms up the dashboard caches (7 days and 30 days) hourly for all users."""
    if not acquire_redis_lock("refresh_dashboard_aggregation_cache", timeout=600):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: refresh_dashboard_aggregation_cache_task")
        return "skipped"
    try:
        users = get_all_usernames()
        logger.info(f"WORKER_TASK | Warming up Dashboards (7 and 30 days) for {len(users)} users.")
        for username in users:
            for days in [7, 30]:
                try:
                    dashboard = generate_wellness_dashboard(user_id=username, days=days)
                    cache_set(username, "dashboard", dashboard, TTL_DASHBOARD, days)
                except Exception as e:
                    logger.error(f"WORKER_TASK | Failed to warm dashboard for {username} ({days} days). Details: {e}")
        return "completed"
    finally:
        release_redis_lock("refresh_dashboard_aggregation_cache")

@celery_app.task
def cleanup_old_emotion_events_task():
    """Purges emotion timeline records older than 30 days from the database securely."""
    if not acquire_redis_lock("cleanup_old_emotion_events", timeout=300):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: cleanup_old_emotion_events_task")
        return "skipped"
    try:
        logger.info("WORKER_TASK | Purging emotion events older than 30 days.")
        deleted = cleanup_old_emotion_events(days=30)
        logger.info(f"WORKER_TASK | Purged {deleted} old emotion timeline records securely.")
        return f"purged {deleted} events"
    finally:
        release_redis_lock("cleanup_old_emotion_events")

@celery_app.task
def run_automated_backup_task():
    """
    Executes nightly SRE-grade database, uploads, and cleanup backup operations.
    Idempotency is guaranteed via distributed Redis lock.
    """
    if not acquire_redis_lock("run_automated_backup", timeout=1800):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: run_automated_backup_task")
        return "skipped"
    try:
        from src.core.config import settings
        logger.info("WORKER_TASK | Starting SRE Automated Backup Task Suite...")
        
        # 1. Back up database
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite"):
            from scripts.backup_sqlite import run_sqlite_backup
            success_db = run_sqlite_backup(db_path=db_url, backup_dir=settings.BACKUP_DIR)
        else:
            from scripts.backup_postgres import run_backup as run_pg_backup
            success_db = run_pg_backup(env_name=settings.APP_ENV, backup_dir=settings.BACKUP_DIR)
            
        # 2. Back up uploads
        from scripts.backup_uploads import run_uploads_backup
        success_uploads = run_uploads_backup(uploads_dir="uploads/profile_photos", backup_dir=settings.BACKUP_DIR)
        
        # 3. Clean up expired files
        from scripts.cleanup_backups import run_cleanup
        success_cleanup = run_cleanup(backup_dir=settings.BACKUP_DIR, retention_days=settings.BACKUP_RETENTION_DAYS, dry_run=False)
        
        status = "completed" if (success_db and success_uploads and success_cleanup) else "partial_failure"
        logger.info(f"WORKER_TASK | SRE Backup Task Suite finished. Status: {status}")
        return status
    except Exception as e:
        logger.error(f"WORKER_TASK | Backup task failed with exception. Details: {e}")
        return "failed"
    finally:
        release_redis_lock("run_automated_backup")

@celery_app.task
def cleanup_expired_audit_logs_task():
    """Celery task to purge security audit logs older than the retention limit (180 days)."""
    if not acquire_redis_lock("cleanup_expired_audit_logs", timeout=300):
        logger.warning("WORKER_TASK | Duplicate lock skip | Task: cleanup_expired_audit_logs_task")
        return "skipped"
    try:
        logger.info("WORKER_TASK | Purging expired security audit logs (180 days retention).")
        from src.services.database import SessionLocal
        from src.services.compliance_service import compliance_service
        db = SessionLocal()
        try:
            deleted = compliance_service.cleanup_old_audit_logs(db, retention_days=180)
            logger.info(f"WORKER_TASK | Purged {deleted} expired security audit logs securely.")
            return f"purged {deleted} audit logs"
        finally:
            db.close()
    except Exception as err:
        logger.error(f"WORKER_TASK | Expired audit logs purge failed. Details: {err}")
        return "failed"
    finally:
        release_redis_lock("cleanup_expired_audit_logs")
