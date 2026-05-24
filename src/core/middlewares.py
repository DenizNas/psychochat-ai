import time
import logging
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

from src.services.auth import decode_access_token
from src.core.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_LATENCY,
    HTTP_ERRORS_TOTAL,
    RATE_LIMIT_EXCEEDED
)
from src.core.rate_limiter import rate_limiter_core
from src.core.logging_config import request_id_ctx_var
from src.core.config import settings
from src.core.redis_client import redis_client

logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    """Safely extracts client IP address behind reverse proxies."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # X-Forwarded-For can contain multiple IPs, the first one is the client
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown_ip"

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Abuse protection middleware that rejects requests with body payloads 
    larger than settings.MAX_REQUEST_BODY_BYTES returning 413 Payload Too Large.
    """
    async def dispatch(self, request: Request, call_next):
        # We only validate Content-Length on body-carrying HTTP methods
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
                        logger.warning(
                            f"SECURITY_AUDIT | Rejected large request body | "
                            f"IP: {get_client_ip(request)} | Size: {content_length} bytes"
                        )
                        return JSONResponse(
                            status_code=413,
                            content={
                                "status": "error",
                                "message": "İstek gövdesi çok büyük. Maksimum izin verilen sınır aşıldı.",
                                "error_code": "PAYLOAD_TOO_LARGE"
                            }
                        )
                except ValueError:
                    pass
        return await call_next(request)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Security-hardened Request logger with integrated user-level rate limiting,
    reverse proxy IP resolution, and suspicious security audit tracking.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 1. Request ID assignment
        req_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        token = request_id_ctx_var.set(req_id)
        
        client_ip = get_client_ip(request)
        path = request.url.path
        
        # 2. Extract user identity securely from JWT to track authenticated rate limits
        user_id = "anonymous"
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token_str = auth_header.split(" ")[1]
            try:
                payload = decode_access_token(token_str)
                if payload and "sub" in payload:
                    user_id = payload["sub"]
                else:
                    logger.warning(f"SECURITY_AUDIT | JWT signature validation failed or expired | IP: {client_ip}")
            except Exception as e:
                logger.warning(f"SECURITY_AUDIT | JWT decode error ({str(e)}) | IP: {client_ip}")

        # 3. Dynamic Rate Limiting Policy Resolution
        # Match endpoint path to correct rate limit rule and key (IP or username)
        limit_type = "default"
        rate_limit_key = client_ip  # Fallback key

        if path == "/login":
            limit_type = "login"
            rate_limit_key = client_ip
        elif path == "/register":
            limit_type = "register"
            rate_limit_key = client_ip
        elif path == "/predict":
            limit_type = "predict"
            rate_limit_key = user_id if user_id != "anonymous" else client_ip
        elif path == "/journal/mood":
            limit_type = "journal"
            rate_limit_key = user_id if user_id != "anonymous" else client_ip
        elif path.startswith("/analytics/"):
            limit_type = "analytics"
            rate_limit_key = user_id if user_id != "anonymous" else client_ip
        elif path == "/health":
            limit_type = None  # health is bypass / unlimited

        # Evaluate rate limiting (if not health endpoint)
        if limit_type and not rate_limiter_core.is_allowed(rate_limit_key, limit_type):
            logger.warning(f"RATE_LIMIT_EXCEEDED | IP: {client_ip} | User: {user_id} | Path: {path} | Policy: {limit_type}")
            
            # Increment rate limit exceeded metrics
            RATE_LIMIT_EXCEEDED.labels(path=path).inc()

            # Log suspicious repeated 429
            self._log_repeated_abuse(client_ip, "429")

            # Write audit log for rate limit exceeded
            try:
                from src.services.database import SessionLocal
                from src.services.compliance_service import compliance_service
                db = SessionLocal()
                try:
                    compliance_service.log_security_event(
                        db=db,
                        user_id=user_id if user_id != "anonymous" else None,
                        event_type="rate_limit_exceeded",
                        ip_address=client_ip,
                        user_agent=user_agent if 'user_agent' in locals() else request.headers.get("User-Agent", "unknown_ua")[:200],
                        request_id=req_id,
                        severity="WARNING",
                        metadata={"path": path, "policy": limit_type}
                    )
                finally:
                    db.close()
            except Exception as audit_err:
                logger.error(f"AUDIT | Failed to write rate limit audit log: {audit_err}")

            response = JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "message": "Çok fazla istek gönderildi. Lütfen biraz sonra tekrar deneyin.",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            )
            response.headers["X-Request-ID"] = req_id
            request_id_ctx_var.reset(token)
            return response

        # Extract user agent securely (capped to prevent overflow)
        user_agent = request.headers.get("User-Agent", "unknown_ua")[:200]
        session_id = request.headers.get("X-Session-ID", "none")

        # Process the request
        try:
            response = await call_next(request)
        except Exception as e:
            request_id_ctx_var.reset(token)
            raise e
            
        end_time = time.time()
        process_time_ms = (end_time - start_time) * 1000
        status_code = response.status_code
        
        # Track Prometheus Metrics (low-cardinality labels only)
        try:
            HTTP_REQUESTS_TOTAL.labels(method=request.method, path=path, status_code=str(status_code)).inc()
            HTTP_REQUEST_LATENCY.labels(method=request.method, path=path, status_code=str(status_code)).observe(process_time_ms / 1000.0)
            if status_code >= 400:
                HTTP_ERRORS_TOTAL.labels(method=request.method, path=path, status_code=str(status_code)).inc()
        except Exception as me:
            logger.warning(f"METRICS | Failed to increment Prometheus registry counters. Details: {me}")

        # Security Auditing: Track suspicious 401s
        if status_code == 401:
            logger.warning(f"SECURITY_AUDIT | Unauthorized access attempt | IP: {client_ip} | Path: {path} | User: {user_id}")
            self._log_repeated_abuse(client_ip, "401")
            
            # Write audit log for unauthorized access (401)
            try:
                from src.services.database import SessionLocal
                from src.services.compliance_service import compliance_service
                db = SessionLocal()
                try:
                    compliance_service.log_security_event(
                        db=db,
                        user_id=user_id if user_id != "anonymous" else None,
                        event_type="login_failed" if path == "/login" else "suspicious_activity",
                        ip_address=client_ip,
                        user_agent=user_agent,
                        request_id=req_id,
                        severity="WARNING",
                        metadata={"path": path, "detail": "Unauthorized HTTP 401"}
                    )
                finally:
                    db.close()
            except Exception as audit_err:
                logger.error(f"AUDIT | Failed to write 401 audit log: {audit_err}")

        # Create secure log entry (absolutely raw-text free)
        log_message = (
            f"Method: {request.method} | "
            f"Path: {path} | "
            f"Status: {status_code} | "
            f"Duration: {process_time_ms:.2f}ms | "
            f"IP: {client_ip} | "
            f"UserID: {user_id} | "
            f"UA: {user_agent}"
        )
        
        # extra details will be captured dynamically by JSONFormatter in production/staging
        extra_data = {
            "method": request.method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(process_time_ms, 2)
        }
        
        if status_code >= 500:
            logger.error(log_message, extra=extra_data)
        else:
            logger.info(log_message, extra=extra_data)
            
        response.headers["X-Request-ID"] = req_id
        request_id_ctx_var.reset(token)
        return response

    def _log_repeated_abuse(self, ip: str, abuse_type: str):
        """Monitors and logs repeated 401/429 status violations per IP address."""
        try:
            r = redis_client.client
            if r:
                key = f"security:audit:{abuse_type}:{ip}"
                count = r.incr(key)
                if count == 1:
                    r.expire(key, 300) # 5 minutes window
                if count >= 5:
                    logger.critical(
                        f"SECURITY_ALERT | Repeated suspicious {abuse_type} status detected | "
                        f"IP: {ip} | Count: {count} in 5 mins"
                    )
                    # Write critical suspicious activity log
                    try:
                        from src.services.database import SessionLocal
                        from src.services.compliance_service import compliance_service
                        db = SessionLocal()
                        try:
                            compliance_service.log_security_event(
                                db=db,
                                user_id=None,
                                event_type="suspicious_activity",
                                ip_address=ip,
                                user_agent="unknown",
                                request_id=None,
                                severity="CRITICAL",
                                metadata={"abuse_type": abuse_type, "count": count, "detail": "Brute force / repeated abuse alarm"}
                            )
                        finally:
                            db.close()
                    except Exception as audit_err:
                        logger.error(f"AUDIT | Failed to write critical suspicious activity audit log: {audit_err}")
        except Exception:
            pass # Failsafe fallback

class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """
    Güvenlik zafiyetlerini önlemek için tarayıcı / istemci seviyesinde
    güvenli HTTP header'larını enjekte eden Middleware.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Clickjacking koruması
        response.headers["X-Frame-Options"] = "DENY"
        
        # MIME sniffing koruması
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS koruması
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy (FastAPI endpointleri için)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        
        # Referrer kontrolü
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Strict-Transport-Security (Sadece staging/production modunda zorunlu kılar)
        if settings.APP_ENV in ["production", "staging"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
        return response
