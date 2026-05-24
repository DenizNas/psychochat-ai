import os
from typing import List, Union
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from dotenv import load_dotenv

# 1. Determine active environment (defaulting to development if unset or invalid)
APP_ENV = os.getenv("APP_ENV", "development").lower()
if APP_ENV not in ["development", "staging", "production"]:
    APP_ENV = "development"

# 2. Select and load environment-specific .env file
env_file = f".env.{APP_ENV}"
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), env_file)

if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
else:
    # Fallback to loading standard .env if environment specific is missing
    load_dotenv(override=True)

class Settings(BaseModel):
    """
    Empatik ve Krize Duyarlı Asistan Yapılandırma ve Çevre Sistemi.
    Pydantic tabanlı modern doğrulama ve veri tipleri sağlar.
    """
    APP_ENV: str = Field(default=APP_ENV)
    DEBUG: bool = Field(default=True)
    SECRET_KEY: str = Field(default="temporary_weak_secret_key_change_me_immediately_for_production")
    DATABASE_URL: str = Field(default="sqlite:///data/psikochat.db")
    REDIS_URL: str = Field(default="redis://localhost:6379")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")
    WORKER_CONCURRENCY: int = Field(default=2)
    OPENAI_API_KEY: str = Field(default="")
    JWT_EXPIRE_MINUTES: int = Field(default=10080)  # 7 Gün (10080 dakika) varsayılan
    CORS_ORIGINS: List[str] = Field(default_factory=list)
    LOG_LEVEL: str = Field(default="DEBUG")
    DISABLE_DOCS: bool = Field(default=False)
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    LOGIN_RATE_LIMIT: str = Field(default="5/minute")
    REGISTER_RATE_LIMIT: str = Field(default="3/minute")
    PREDICT_RATE_LIMIT: str = Field(default="20/minute")
    ANALYTICS_RATE_LIMIT: str = Field(default="60/minute")
    MAX_REQUEST_BODY_BYTES: int = Field(default=2097152)
    METRICS_ENABLED: bool = Field(default=True)
    JSON_LOGS_ENABLED: bool = Field(default=True)
    PROMETHEUS_ENABLED: bool = Field(default=True)
    BACKUP_DIR: str = Field(default="backups")
    BACKUP_RETENTION_DAYS: int = Field(default=7)
    
    # ── Multi-Model AI Orchestration Config ─────────────────────────────────
    AI_PRIMARY_PROVIDER: str = Field(default="openai")
    AI_FALLBACK_PROVIDER: str = Field(default="local")
    AI_PRIMARY_MODEL: str = Field(default="gpt-4o")
    AI_FALLBACK_MODEL: str = Field(default="gpt-3.5-turbo")
    AI_TIMEOUT_SECONDS: float = Field(default=5.0)
    AI_MAX_RETRIES: int = Field(default=3)
    AI_COST_LIMIT_DAILY: float = Field(default=5.0)
    AI_ENABLE_LOCAL_FALLBACK: bool = Field(default=True)

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    @field_validator("DISABLE_DOCS", mode="before")
    @classmethod
    def parse_disable_docs(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    @field_validator("JWT_EXPIRE_MINUTES", mode="before")
    @classmethod
    def parse_jwt_expire(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 10080
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return []

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v, info: ValidationInfo):
        env = os.getenv("APP_ENV", "development").lower()
        if env in ["production", "staging"]:
            # Minimum length check (at least 32 characters for secure JWT signing)
            if len(v) < 32:
                raise ValueError(
                    f"SECRET_KEY production/staging ortamında en az 32 karakter olmalıdır (Mevcut uzunluk: {len(v)})."
                )
            
            # Default fallback key check to avoid accidentally leaving the weak default
            if v == "temporary_weak_secret_key_change_me_immediately_for_production":
                raise ValueError(
                    "SECRET_KEY production/staging ortamında varsayılan zayıf değerinde bırakılamaz."
                )
            
            # Entropy check: check if it's too simple (e.g., all same characters or extremely low character variety)
            if len(set(v)) < 8:
                raise ValueError(
                    "SECRET_KEY zayıf entropy tespit edildi. Lütfen daha karmaşık ve güvenli bir anahtar belirleyin."
                )
        return v

def get_settings() -> Settings:
    """Settings modelini çevre değişkenleri ile doldurup doğrular."""
    raw_debug = os.getenv("DEBUG")
    if raw_debug is None:
        debug_default = APP_ENV not in ["production", "staging"]
    else:
        debug_default = raw_debug.lower() in ("true", "1", "yes")

    raw_disable_docs = os.getenv("DISABLE_DOCS")
    if raw_disable_docs is None:
        disable_docs_default = APP_ENV in ["production", "staging"]
    else:
        disable_docs_default = raw_disable_docs.lower() in ("true", "1", "yes")

    raw_log_level = os.getenv("LOG_LEVEL")
    if raw_log_level is None:
        log_level_default = "INFO" if APP_ENV in ["production", "staging"] else "DEBUG"
    else:
        log_level_default = raw_log_level

    # Instantiate Settings
    return Settings(
        APP_ENV=APP_ENV,
        DEBUG=debug_default,
        SECRET_KEY=os.getenv("SECRET_KEY", os.getenv("JWT_SECRET_KEY", "temporary_weak_secret_key_change_me_immediately_for_production")),
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///data/psikochat.db"),
        REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379"),
        CELERY_BROKER_URL=os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
        CELERY_RESULT_BACKEND=os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
        WORKER_CONCURRENCY=int(os.getenv("WORKER_CONCURRENCY", "2")),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        JWT_EXPIRE_MINUTES=os.getenv("JWT_EXPIRE_MINUTES", "10080"),
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "*"),
        LOG_LEVEL=log_level_default,
        DISABLE_DOCS=disable_docs_default,
        RATE_LIMIT_ENABLED=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        LOGIN_RATE_LIMIT=os.getenv("LOGIN_RATE_LIMIT", "5/minute"),
        REGISTER_RATE_LIMIT=os.getenv("REGISTER_RATE_LIMIT", "3/minute"),
        PREDICT_RATE_LIMIT=os.getenv("PREDICT_RATE_LIMIT", "20/minute"),
        ANALYTICS_RATE_LIMIT=os.getenv("ANALYTICS_RATE_LIMIT", "60/minute"),
        MAX_REQUEST_BODY_BYTES=int(os.getenv("MAX_REQUEST_BODY_BYTES", "2097152")),
        METRICS_ENABLED=os.getenv("METRICS_ENABLED", "true").lower() == "true",
        JSON_LOGS_ENABLED=os.getenv("JSON_LOGS_ENABLED", "true").lower() == "true",
        PROMETHEUS_ENABLED=os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true",
        BACKUP_DIR=os.getenv("BACKUP_DIR", "backups"),
        BACKUP_RETENTION_DAYS=int(os.getenv("BACKUP_RETENTION_DAYS", "7")),
        # AI Orchestrator bindings
        AI_PRIMARY_PROVIDER=os.getenv("AI_PRIMARY_PROVIDER", "openai"),
        AI_FALLBACK_PROVIDER=os.getenv("AI_FALLBACK_PROVIDER", "local"),
        AI_PRIMARY_MODEL=os.getenv("AI_PRIMARY_MODEL", "gpt-4o"),
        AI_FALLBACK_MODEL=os.getenv("AI_FALLBACK_MODEL", "gpt-3.5-turbo"),
        AI_TIMEOUT_SECONDS=float(os.getenv("AI_TIMEOUT_SECONDS", "5.0")),
        AI_MAX_RETRIES=int(os.getenv("AI_MAX_RETRIES", "3")),
        AI_COST_LIMIT_DAILY=float(os.getenv("AI_COST_LIMIT_DAILY", "5.0")),
        AI_ENABLE_LOCAL_FALLBACK=os.getenv("AI_ENABLE_LOCAL_FALLBACK", "true").lower() == "true"
    )

# Global settings singleton
settings = get_settings()
