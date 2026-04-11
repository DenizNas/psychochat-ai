import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from datetime import datetime

from src.services.auth import decode_access_token
from src.core.metrics import metrics_tracker
from src.core.rate_limiter import rate_limiter_core

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        client_ip = request.client.host if request.client else "unknown_ip"
        path = request.url.path
        
        # 1. Rate Limiting Entegrasyonu (En önde kontrol)
        if not rate_limiter_core.is_allowed(client_ip, path):
            logger.warning(f"Rate Limit Exceeded | IP: {client_ip} | Path: {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "message": "Çok fazla istek gönderdiniz. Lütfen bir süre bekleyip tekrar deneyin.",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "timestamp": datetime.utcnow().isoformat(),
                    "path": path
                }
            )
        
        # Extract user_id securely without breaking the request if token is invalid
        user_id = "anonymous"
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_access_token(token)
            if payload and "sub" in payload:
                user_id = payload["sub"]

        # Extract session_id securely (usually sent via header like 'X-Session-ID')
        session_id = request.headers.get("X-Session-ID", "none")

        # Process the request
        response = await call_next(request)
        
        # Calculate performance
        end_time = time.time()
        process_time_ms = (end_time - start_time) * 1000
        status_code = response.status_code
        
        # In-memory metrics takibi
        is_error = status_code >= 500
        metrics_tracker.record_request(process_time_ms, is_error, session_id)
        
        # Create structured log message
        log_message = (
            f"Method: {request.method} | "
            f"Path: {request.url.path} | "
            f"Status: {status_code} | "
            f"Duration: {process_time_ms:.2f}ms | "
            f"SessionID: {session_id} | "
            f"UserID: {user_id}"
        )
        
        # Determine log level based on response code
        if status_code >= 500:
            logger.error(log_message)
        else:
            logger.info(log_message)
            
        return response
