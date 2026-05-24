import logging
from prometheus_client import Counter, Histogram, CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
from src.core.config import settings

logger = logging.getLogger(__name__)

# Use a dedicated isolated registry for Psychochat-AI
REGISTRY = CollectorRegistry()

# 1. HTTP Request Metrics (low-cardinality labels only)
HTTP_REQUESTS_TOTAL = Counter(
    "psychochat_request_count",
    "Total count of HTTP requests",
    ["method", "path", "status_code"],
    registry=REGISTRY
)

HTTP_REQUEST_LATENCY = Histogram(
    "psychochat_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0, float('inf')),
    registry=REGISTRY
)

HTTP_ERRORS_TOTAL = Counter(
    "psychochat_error_count",
    "Total count of HTTP errors",
    ["method", "path", "status_code"],
    registry=REGISTRY
)

# 2. Security, Abuse & Safety Telemetry
RATE_LIMIT_EXCEEDED = Counter(
    "psychochat_rate_limit_exceeded_count",
    "Total count of rate limit exceeded events",
    ["path"],
    registry=REGISTRY
)

AUTH_FAILURES_TOTAL = Counter(
    "psychochat_auth_failure_count",
    "Total count of failed authentication attempts",
    ["type"],
    registry=REGISTRY
)

CRISIS_DETECTIONS_TOTAL = Counter(
    "psychochat_crisis_detection_count",
    "Total count of crisis safety events (secure, low-cardinality count)",
    registry=REGISTRY
)

PREDICTIONS_TOTAL = Counter(
    "psychochat_prediction_count",
    "Total count of emotion predictions",
    ["emotion", "risk"],
    registry=REGISTRY
)

# 3. Cache & DB Telemetry
CACHE_HIT_TOTAL = Counter(
    "psychochat_cache_hit_count",
    "Total count of cache hits",
    ["cache_type"],
    registry=REGISTRY
)

CACHE_MISS_TOTAL = Counter(
    "psychochat_cache_miss_count",
    "Total count of cache misses",
    ["cache_type"],
    registry=REGISTRY
)

REDIS_FALLBACK_TOTAL = Counter(
    "psychochat_redis_fallback_count",
    "Total count of Redis unavailability fallbacks",
    ["operation"],
    registry=REGISTRY
)

DATABASE_ERRORS_TOTAL = Counter(
    "psychochat_db_error_count",
    "Total count of database operational errors",
    ["operation"],
    registry=REGISTRY
)

# 4. Background Workers Telemetry
CELERY_TASK_SUCCESS = Counter(
    "psychochat_celery_task_success_count",
    "Total count of successfully executed Celery background tasks",
    ["task_name"],
    registry=REGISTRY
)

CELERY_TASK_FAILURE = Counter(
    "psychochat_celery_task_failure_count",
    "Total count of failed Celery background tasks",
    ["task_name"],
    registry=REGISTRY
)

# 5. Automated Backup & Recovery Telemetry
BACKUP_SUCCESS_GAUGE = Gauge(
    "psychochat_backup_success_count",
    "Total count of successfully completed backup jobs",
    ["backup_type"],
    registry=REGISTRY
)

BACKUP_FAILURE_GAUGE = Gauge(
    "psychochat_backup_failure_count",
    "Total count of failed backup jobs",
    ["backup_type"],
    registry=REGISTRY
)

LAST_BACKUP_TIMESTAMP = Gauge(
    "psychochat_last_backup_timestamp",
    "UNIX timestamp of the last successful backup execution",
    ["backup_type"],
    registry=REGISTRY
)

# 6. Multi-Model AI Orchestrator Telemetry
AI_REQUESTS_TOTAL = Counter(
    "psychochat_ai_request_count",
    "Total count of AI requests processed",
    ["provider", "model", "status"],
    registry=REGISTRY
)

AI_FALLBACKS_TOTAL = Counter(
    "psychochat_ai_fallback_count",
    "Total count of provider fallback switches",
    ["from_provider", "to_provider"],
    registry=REGISTRY
)

AI_COST_ESTIMATE_TOTAL = Counter(
    "psychochat_ai_cost_estimate_total",
    "Estimated total cost of AI provider requests in USD",
    ["provider", "model"],
    registry=REGISTRY
)

AI_LATENCY_MS = Histogram(
    "psychochat_ai_latency_ms",
    "AI provider request latency in milliseconds",
    ["provider", "model"],
    buckets=(50.0, 100.0, 250.0, 500.0, 1000.0, 2000.0, 5000.0, float('inf')),
    registry=REGISTRY
)

AI_PROVIDER_ERROR_TOTAL = Counter(
    "psychochat_ai_provider_error_count",
    "Total count of errors encountered per AI provider",
    ["provider", "error_type"],
    registry=REGISTRY
)

# 7. Enterprise Compliance Audit Telemetry
COMPLIANCE_AUDIT_EVENTS_TOTAL = Counter(
    "psychochat_compliance_audit_event_count",
    "Total count of compliance audit events labeled by event and severity",
    ["event_type", "severity"],
    registry=REGISTRY
)

DATA_EXPORTS_TOTAL = Counter(
    "psychochat_data_export_request_count",
    "Total count of GDPR data export requests",
    registry=REGISTRY
)

DATA_DELETIONS_TOTAL = Counter(
    "psychochat_data_delete_request_count",
    "Total count of GDPR data deletion/anonymization requests",
    registry=REGISTRY
)

# 8. Recommendation Engine Telemetry (Faz 10 Prompt 7)
RECOMMENDATION_GENERATED_TOTAL = Counter(
    "psychochat_recommendation_generated_count",
    "Total count of wellness recommendations generated",
    ["recommendation_type"],
    registry=REGISTRY
)

RECOMMENDATION_DISMISSED_TOTAL = Counter(
    "psychochat_recommendation_dismissed_count",
    "Total count of wellness recommendations dismissed by users",
    ["recommendation_type"],
    registry=REGISTRY
)

RECOMMENDATION_FEEDBACK_TOTAL = Counter(
    "psychochat_recommendation_feedback_count",
    "Total count of recommendation feedback events",
    ["feedback_type"],
    registry=REGISTRY
)

RECOMMENDATION_CRISIS_PRIORITY_TOTAL = Counter(
    "psychochat_recommendation_crisis_priority_count",
    "Total count of recommendations where crisis prioritization was applied",
    registry=REGISTRY
)

# 9. Real-Time WebSocket Observability Telemetry
WEBSOCKET_ACTIVE_CONNECTIONS = Gauge(
    "psychochat_websocket_connections_active",
    "Number of currently active WebSocket connections",
    registry=REGISTRY
)

WEBSOCKET_RECONNECTS_TOTAL = Counter(
    "psychochat_websocket_reconnects_total",
    "Total number of WebSocket reconnection events",
    registry=REGISTRY
)

WEBSOCKET_DISCONNECTS_TOTAL = Counter(
    "psychochat_websocket_disconnects_total",
    "Total number of WebSocket disconnection events labeled by reason",
    ["reason"],
    registry=REGISTRY
)

WEBSOCKET_HEARTBEAT_TIMEOUTS_TOTAL = Counter(
    "psychochat_websocket_heartbeat_timeouts_total",
    "Total number of WebSocket heartbeat timeout events",
    registry=REGISTRY
)


def generate_metrics_payload() -> bytes:
    """Serializes the metrics registry to standard Prometheus scrape format."""
    if not settings.METRICS_ENABLED:
        return b""
    try:
        from src.core.redis_client import redis_client
        r = redis_client.client
        if r:
            for btype in ["postgres", "sqlite", "uploads", "cleanup"]:
                success = r.get(f"metrics:backup:success_count:{btype}")
                if success is not None:
                    BACKUP_SUCCESS_GAUGE.labels(backup_type=btype).set(float(success))
                failure = r.get(f"metrics:backup:failure_count:{btype}")
                if failure is not None:
                    BACKUP_FAILURE_GAUGE.labels(backup_type=btype).set(float(failure))
                ts = r.get(f"metrics:backup:last_timestamp:{btype}")
                if ts is not None:
                    LAST_BACKUP_TIMESTAMP.labels(backup_type=btype).set(float(ts))
    except Exception:
        pass
    return generate_latest(REGISTRY)
