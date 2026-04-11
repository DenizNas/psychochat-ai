from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def custom_http_exception_handler(request: Request, exc: HTTPException):
    session_id = request.headers.get("X-Session-ID", "none")
    path = request.url.path
    log_msg = f"HTTPException on {path} | Status: {exc.status_code} | SessionID: {session_id} | Detail: {exc.detail}"
    
    # 400 ve 401 hataları WARNING, diğerleri ERROR seviyesinde loglanır
    if exc.status_code in [400, 401, 403, 404]:
        logger.warning(log_msg)
    else:
        logger.error(log_msg)
    
    # 401 Authentication hataları için özel error code belirleme
    error_code = "UNAUTHORIZED" if exc.status_code == 401 else f"HTTP_ERROR_{exc.status_code}"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": str(exc.detail),
            "error_code": error_code,
            "timestamp": datetime.utcnow().isoformat(),
            "path": path
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    session_id = request.headers.get("X-Session-ID", "none")
    path = request.url.path
    log_msg = f"ValidationError on {path} | SessionID: {session_id} | Detail: {exc.errors()}"
    
    # Validation genelde kullanıcı kaynaklı olduğu için WARNING seviyesi uygundur
    logger.warning(log_msg)
    
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Geçersiz veya eksik veri gönderildi.",
            "error_code": "VALIDATION_ERROR",
            "timestamp": datetime.utcnow().isoformat(),
            "path": path
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    session_id = request.headers.get("X-Session-ID", "none")
    path = request.url.path
    log_msg = f"Unhandled Exception on {path} | SessionID: {session_id} | Error: {str(exc)}"
    
    # 500 çöküşleri mutlaka ERROR seviyesinde Stack Trace ile birlikte (exc_info) tutulmalı
    logger.error(log_msg, exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Beklenmeyen bir sunucu hatası oluştu.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "timestamp": datetime.utcnow().isoformat(),
            "path": path
        }
    )
