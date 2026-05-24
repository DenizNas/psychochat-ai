import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar
from src.core.config import settings

import json
from datetime import datetime, timezone

# ContextVar to store Request ID for async threads
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    """Logs'a dinamik olarak aktif request_id değerini enjekte eden filtre."""
    def filter(self, record):
        record.request_id = request_id_ctx_var.get("-")
        return True

class JSONFormatter(logging.Formatter):
    """
    Standardized production-grade structured JSON log formatter.
    Guarantees no raw user payload, token, or sensitive context is leaked.
    """
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "request_id": getattr(record, "request_id", "-"),
            "environment": settings.APP_ENV,
            "message": record.getMessage()
        }
        
        # Attach request-specific telemetry details safely if present
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
            
        return json.dumps(log_entry)

def setup_logging():
    # Proje kök dizininde logs klasörünün yolunu belirle ve oluştur
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "app.log")

    logger = logging.getLogger()
    
    # settings üzerinden dinamik log level ataması yap
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Mevcut handler'ları temizle ki double log atmasın
    if logger.handlers:
        logger.handlers.clear()
        
    # Choose standard or structured JSON formatting
    if settings.JSON_LOGS_ENABLED and settings.APP_ENV in ["production", "staging"]:
        formatter = JSONFormatter()
    else:
        # Formatter pattern: timestamp | LEVEL | module | [ReqID: ...] | message
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(module)-15s | [ReqID: %(request_id)s] | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # 2. Rotating File Handler (5 MB sınır, 3 yedek)
    file_handler = RotatingFileHandler(
        log_file_path, 
        maxBytes=5 * 1024 * 1024, 
        backupCount=3, 
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Request ID enjeksiyonu için filtreyi handler'lara ekle
    req_id_filter = RequestIdFilter()
    console_handler.addFilter(req_id_filter)
    file_handler.addFilter(req_id_filter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    logger.info(f"Logging initialized with level: {settings.LOG_LEVEL} (Env: {settings.APP_ENV})")
    return logger
