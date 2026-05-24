from celery.schedules import crontab

# Defined crontab schedules using local time (Europe/Istanbul)
beat_schedule = {
    "refresh-scheduled-interventions-every-3-hours": {
        "task": "src.workers.tasks.refresh_scheduled_interventions_task",
        "schedule": crontab(minute=0, hour="*/3"),  # Runs every 3 hours local time
    },
    "refresh-notification-events-every-4-hours": {
        "task": "src.workers.tasks.refresh_notification_events_task",
        "schedule": crontab(minute=0, hour="*/4"),  # Runs every 4 hours local time
    },
    "prepare-daily-wellness-reports-daily": {
        "task": "src.workers.tasks.prepare_daily_wellness_reports_task",
        "schedule": crontab(minute=30, hour=2),  # Runs daily at 02:30 AM local time
    },
    "prepare-weekly-wellness-reports-weekly": {
        "task": "src.workers.tasks.prepare_weekly_wellness_reports_task",
        "schedule": crontab(minute=0, hour=3, day_of_week="monday"),  # Runs every Monday at 03:00 AM local time
    },
    "refresh-dashboard-aggregation-cache-hourly": {
        "task": "src.workers.tasks.refresh_dashboard_aggregation_cache_task",
        "schedule": crontab(minute=0, hour="*"),  # Runs hourly local time
    },
    "cleanup-old-emotion-events-daily": {
        "task": "src.workers.tasks.cleanup_old_emotion_events_task",
        "schedule": crontab(minute=0, hour=4),  # Runs daily at 04:00 AM local time
    },
    "run-automated-backup-daily": {
        "task": "src.workers.tasks.run_automated_backup_task",
        "schedule": crontab(minute=30, hour=3),  # Runs daily at 03:30 AM local time (Europe/Istanbul)
    },
    "cleanup-expired-audit-logs-daily": {
        "task": "src.workers.tasks.cleanup_expired_audit_logs_task",
        "schedule": crontab(minute=0, hour=5),  # Runs daily at 05:00 AM local time (Europe/Istanbul)
    }
}
