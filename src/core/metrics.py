import threading

class AppMetrics:
    """
    Lightweight, thread-safe in-memory metrics tracker for Prometheus-ready upgrade.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.request_count = 0
        self.error_count = 0
        self.total_latency = 0.0
        self.active_sessions = set()

    def record_request(self, latency_ms: float, is_error: bool, session_id: str):
        with self._lock:
            self.request_count += 1
            self.total_latency += latency_ms
            if is_error:
                self.error_count += 1
            if session_id and session_id != "none":
                self.active_sessions.add(session_id)

    def get_snapshot(self) -> dict:
        with self._lock:
            avg_latency = 0.0
            if self.request_count > 0:
                avg_latency = self.total_latency / self.request_count
                
            return {
                "total_requests": self.request_count,
                "error_count": self.error_count,
                "active_sessions_count": len(self.active_sessions),
                "average_response_time_ms": round(avg_latency, 2)
            }

# Global singleton
metrics_tracker = AppMetrics()
