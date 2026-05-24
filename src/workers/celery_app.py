import os
import logging
from celery import Celery
from src.core.config import settings

logger = logging.getLogger(__name__)

# Enforce strict European/Istanbul local timezone logic for worker crontabs
TIMEZONE_ISTANBUL = "Europe/Istanbul"

# Retrieve Celery broker and result backend parameters
broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND
concurrency = settings.WORKER_CONCURRENCY

# Handle production fallback or SQLite local environments gracefully
if not broker_url or not broker_url.startswith("redis://"):
    broker_url = "redis://localhost:6379/0"
if not result_backend or not result_backend.startswith("redis://"):
    result_backend = "redis://localhost:6379/0"

logger.info(f"CELERY_APP | Initialization. Broker: {broker_url} | Backend: {result_backend} | Concurrency: {concurrency}")

celery_app = Celery(
    "psychochat_workers",
    broker=broker_url,
    backend=result_backend,
    include=["src.workers.tasks"]
)

# Apply settings
celery_app.conf.update(
    timezone=TIMEZONE_ISTANBUL,
    enable_utc=False,  # Enforces that Beat schedule checks respect the configured timezone local time
    worker_concurrency=concurrency,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_connection_retry_on_startup=True
)

# Import and attach beat scheduler from schedules.py
from src.workers.schedules import beat_schedule
celery_app.conf.beat_schedule = beat_schedule

# ---------------------------------------------------------------------------
# Celery Worker Signals Telemetry & Standardized Logging
# ---------------------------------------------------------------------------
import time
from celery.signals import task_prerun, task_postrun, task_failure

@task_prerun.connect
def on_task_prerun(task_id, task, *args, **kwargs):
    task._start_time = time.time()
    logger.info(f"WORKER_TASK | Start | Task: {task.name} | ID: {task_id}")

@task_postrun.connect
def on_task_postrun(task_id, task, retval, state, exception, *args, **kwargs):
    duration_ms = 0
    if hasattr(task, "_start_time"):
        duration_ms = (time.time() - task._start_time) * 1000
    
    if state == "SUCCESS":
        logger.info(f"WORKER_TASK | Success | Task: {task.name} | ID: {task_id} | Duration: {duration_ms:.2f}ms")
        try:
            from src.core.metrics import CELERY_TASK_SUCCESS
            CELERY_TASK_SUCCESS.labels(task_name=task.name).inc()
        except Exception:
            pass
    elif state == "FAILURE":
        logger.error(f"WORKER_TASK | Failure | Task: {task.name} | ID: {task_id} | State: {state} | Duration: {duration_ms:.2f}ms")
        try:
            from src.core.metrics import CELERY_TASK_FAILURE
            CELERY_TASK_FAILURE.labels(task_name=task.name).inc()
        except Exception:
            pass

@task_failure.connect
def on_task_failure(task_id, exception, traceback, sender, *args, **kwargs):
    logger.error(f"WORKER_TASK | Error | Task: {sender.name} | ID: {task_id} | Exception: {str(exception)}")
    try:
        from src.core.metrics import CELERY_TASK_FAILURE
        CELERY_TASK_FAILURE.labels(task_name=sender.name).inc()
    except Exception:
        pass

