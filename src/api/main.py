from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, ORJSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import sys
import os
import time
from typing import Optional
from datetime import datetime, timezone
import uuid
from fastapi import File, UploadFile
from fastapi.staticfiles import StaticFiles

# 1. Merkezi Güvenlik Ayarlarını İçe Aktar
from src.core.security_config import security_config

# 2. Config and Startup Validation Checks
import sys
import logging

try:
    from src.core.config import settings
except Exception as e:
    print(f"\n======================================================\nFATAL STARTUP CONFIGURATION ERROR:\n{str(e)}\n======================================================\n", file=sys.stderr)
    sys.exit(1)

from src.core.brute_force_protection import brute_force_protector
from src.core.token_blacklist import token_blacklist_core
from src.core.input_validator import input_validator_core
from src.ai.preprocessing import prepare_model_input, turkish_lower
from src.core.logging_config import setup_logging
logger = logging.getLogger(__name__)
from src.core.middlewares import RequestLoggingMiddleware
from src.core.exceptions import custom_http_exception_handler, validation_exception_handler, global_exception_handler, json_decode_exception_handler
from fastapi.exceptions import RequestValidationError
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.inference.predict import EmotionCrisisPredictor
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput
from src.services.logger import log_interaction
from src.services.database import (
    init_db,
    get_chat_history,
    get_analytics_summary,
    get_analytics_timeline,
    save_emotion_event,
    get_user_emotion_timeline,
    get_user_emotion_summary,
    get_scheduled_interventions_for_user,
    save_mood_journal,
    get_mood_journals_for_user,
    delete_mood_journal,
    get_notification_events_for_user,
    mark_notification_as_delivered
)
from src.services.database import create_user, get_user_by_username, get_or_create_profile, update_user_profile
from src.services.database import get_active_memories_for_user, delete_memory_for_user
from src.response_engine.personal_context_engine import consolidate_memories
from src.response_engine.safety import check_safety
from src.services.notification_service import refresh_user_notifications
from src.services.reflection_engine import generate_reflection


from src.services.auth import verify_password, get_password_hash, create_access_token, decode_access_token, get_current_user, security_jwt
from src.services.gating import require_premium_user, AccessDeniedResponse
from src.services.behavioral_insights import generate_behavioral_insights
from src.services.smart_interventions import generate_smart_interventions
from src.services.intervention_scheduler import schedule_user_interventions, ISTANBUL_TZ
from src.services.wellness_reports import generate_wellness_report
from src.services.wellness_dashboard import generate_wellness_dashboard
from datetime import timezone, timedelta
from src.core.cache import cache_get, cache_set, invalidate_user_caches, TTL_DASHBOARD, TTL_SUMMARY, TTL_REPORTS

# ─── Real-Time WebSocket Services ────────────────────────────────────────────
from src.services.websocket_manager import connection_manager, register_pubsub_handler
from src.services.websocket_events import (
    WsEventType,
    EventValidationError,
    ChatMessagePayload,
    build_chat_response,
    build_typing_indicator,
    build_error,
    build_pong,
    encode_event,
    parse_inbound_event,
)
from src.services.redis_realtime import pubsub_manager
from src.services.presence_service import presence_service


limiter = Limiter(key_func=get_remote_address)

# Dynamically enable/disable Swagger/Redoc based on configuration
docs_url = "/docs" if not settings.DISABLE_DOCS else None
redoc_url = "/redoc" if not settings.DISABLE_DOCS else None
openapi_url = "/openapi.json" if not settings.DISABLE_DOCS else None

app = FastAPI(
    title="Psikochat-AI API",
    description="Empatik ve Krize Duyarlı Yapay Zeka Destek Asistanı",
    version="1.1.0",
    default_response_class=ORJSONResponse,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url
)

app.state.limiter = limiter

# Request Logging Middleware Entegrasyonu
app.add_middleware(RequestLoggingMiddleware)

# Secure HTTP Headers Middleware
from src.core.middlewares import SecureHeadersMiddleware, RequestSizeLimitMiddleware
app.add_middleware(SecureHeadersMiddleware)

# Request Body Size Limit Middleware (Abuse protection)
app.add_middleware(RequestSizeLimitMiddleware)

# Exception Handler Kayıt İşlemleri
app.add_exception_handler(HTTPException, custom_http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(json.JSONDecodeError, json_decode_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS Configuration
if settings.APP_ENV in ["production", "staging"]:
    # Strict CORS origins for production/staging environments
    origins = settings.CORS_ORIGINS
    
    # Reject wildcards in production/staging and apply standard secure fallback if invalid
    if not origins or "*" in origins:
        logger.warning("CORS Wildcard or empty origins is prohibited in production/staging! Applying fallback.")
        origins = ["https://app.psikochat.com"]
else:
    # Allow localhost and wildcard origins for local development environments
    origins = settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"]
    if not origins:
        origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

predictor = None

# Create uploads directory if not exists
UPLOAD_DIR = "uploads/profile_photos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files to serve profile photos
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

## Security schemes
security_basic = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security_basic)):
    correct_user = os.getenv("ADMIN_USER", "admin")
    correct_pass = os.getenv("ADMIN_PASS", "psiko_secret123")
    if credentials.username != correct_user or credentials.password != correct_pass:
        raise HTTPException(
            status_code=401,
            detail="Yanlış admin adı veya şifre",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

## Schemas
class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: str

class RegisterRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    password: str

class ChatRequest(BaseModel):
    text: str
    language: Optional[str] = "tr"

class ChatResponse(BaseModel):
    emotion: str
    risk: str
    response: str
    emergency_contact: Optional[str] = None

class MemoryResponse(BaseModel):
    id: int
    memory_type: str
    memory_text: str
    confidence: float
    sensitivity: str
    last_reinforced_at: Optional[str] = None

class MemoryConsolidationStatsResponse(BaseModel):
    status: str
    processed: int
    merged: int
    decayed: int
    contradicted: int

class ProfileResponse(BaseModel):
    username: str
    display_name: Optional[str]
    bio: Optional[str]
    profile_photo_url: Optional[str]
    preferred_language: str
    response_style: str
    theme_preference: str
    notifications_enabled: bool
    privacy_mode: bool
    answer_length_preference: str
    created_at: str
    updated_at: str
    id: Optional[int] = None
    email: Optional[str] = None
    full_name: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    preferred_language: Optional[str] = None
    response_style: Optional[str] = None
    theme_preference: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    privacy_mode: Optional[bool] = None
    answer_length_preference: Optional[str] = None

    # Validation constraints
    class Config:
        json_schema_extra = {
            "example": {
                "display_name": "Deniz Nas",
                "bio": "Sınav dönemlerinde destek almak istiyorum.",
                "preferred_language": "tr",
                "response_style": "supportive"
            }
        }

class EmotionTimelineItem(BaseModel):
    id: int
    message_id: str
    emotion: str
    risk: str
    created_at: str
    source: str

class DailyTrendItem(BaseModel):
    date: str
    emotions: dict
    total_count: int

class EmotionSummaryResponse(BaseModel):
    total_messages: int
    emotion_distribution: dict
    dominant_emotion: Optional[str]
    crisis_count: int
    daily_trend: list

class BehavioralInsightResponse(BaseModel):
    type: str
    severity: str
    confidence: float
    title: str
    description: str
    created_at: str

class SmartInterventionResponse(BaseModel):
    type: str
    severity: str
    title: str
    description: str
    created_at: str

class ScheduledInterventionResponse(BaseModel):
    type: str
    priority: str
    scheduled_for: str
    status: str
    title: str
    description: str

class WellnessReportResponse(BaseModel):
    period: str
    summary_title: str
    summary_text: str
    dominant_emotion: str
    total_messages: int
    crisis_count: int
    highlights: list[str]
    suggestions: list[str]
    created_at: str

class ReflectionResponse(BaseModel):
    period: str
    reflection_title: str
    reflection_text: str
    tone: str
    dominant_emotion: str
    generated_from: list[str]
    created_at: str

class NotificationResponse(BaseModel):
    id: int
    user_id: str
    notification_type: str
    title: str
    body: str
    scheduled_for: str
    status: str
    created_at: str
    delivered_at: Optional[str] = None
    source: str


class CreateMoodJournalRequest(BaseModel):
    mood: str
    intensity: int
    note: Optional[str] = None

class MoodJournalResponse(BaseModel):
    id: int
    user_id: str
    mood: str
    intensity: int
    note: Optional[str]
    created_at: str
    updated_at: str
    source: str


class DashboardOverview(BaseModel):
    total_messages: int
    dominant_emotion: str
    crisis_count: int
    journal_count: int
    scheduled_intervention_count: int
    notification_count: int


class DashboardScore(BaseModel):
    score: Optional[int]
    label: str
    description: str


class DashboardSections(BaseModel):
    emotion_distribution: dict
    daily_trend: list
    top_insights: list[BehavioralInsightResponse]
    active_interventions: list[SmartInterventionResponse]
    latest_reflection: dict
    latest_report: dict


class WellnessDashboardResponse(BaseModel):
    days: int
    overview: DashboardOverview
    wellness_score: DashboardScore
    sections: DashboardSections
    created_at: str


class UserConsentResponse(BaseModel):
    privacy_policy_version: str
    terms_version: str
    analytics_consent: bool
    wellness_insights_consent: bool
    notifications_consent: bool
    ai_processing_consent: bool


class UpdateConsentRequest(BaseModel):
    analytics_consent: bool
    wellness_insights_consent: bool
    notifications_consent: bool
    ai_processing_consent: bool


class DeleteDataRequest(BaseModel):
    confirm: str


@app.on_event("startup")
async def load_models():
    logger = setup_logging()
    logger.info("FastAPI uygulaması başlatılıyor. Log mekanizması aktif.")
    
    global predictor
    print("Initialize Database...")
    try:
        init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing DB: {e}")

    print("Loading AI Models... This might take a few seconds.")
    try:
        predictor = EmotionCrisisPredictor()
        logger.info("Models loaded successfully from absolute paths.")
        print("Models loaded successfully.")
    except Exception as e:
        if settings.APP_ENV == "production":
            logger.critical(f"FATAL STARTUP ERROR: Modeller yuklenemedi. Detay: {str(e)}")
            print(f"FATAL STARTUP ERROR: Modeller yuklenemedi. Detay: {str(e)}")
            sys.exit(1)
        else:
            logger.critical(f"STARTUP WARNING: Modeller yuklenemedi. Inference disabled. Detay: {str(e)}")
            print(f"STARTUP WARNING: Modeller yuklenemedi. Inference disabled. Detay: {str(e)}")

    # ─── Real-Time Infrastructure Startup ──────────────────────────────────
    import asyncio
    print("Starting Real-Time WebSocket infrastructure...")
    await presence_service.connect()
    await pubsub_manager.connect()
    await pubsub_manager.start_subscriber()
    register_pubsub_handler()
    logger.info("WebSocket gateway hazır. Redis Pub/Sub: %s", pubsub_manager.is_available)
    print(f"WebSocket gateway ready. Redis Pub/Sub: {pubsub_manager.is_available}")

@app.get("/")
def read_root():
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Kök (root) endpoint '/' çağrıldı.")
    return {"status": "ok", "message": "Psikochat-AI API Çalışıyor. /predict uç noktasını kullanın."}

## Auth Endpoints
@app.post("/register", status_code=201)
def register(user: RegisterRequest):
    # Backward compatibility: if email is not provided but username is, construct email and full_name from username
    email_val = user.email
    full_name_val = user.full_name
    
    if not email_val and user.username:
        email_val = f"{user.username}@example.com"
    if not full_name_val and user.username:
        full_name_val = user.username
        
    if not email_val or not user.password or not full_name_val:
        raise HTTPException(status_code=400, detail="Ad soyad, e-posta ve şifre gereklidir.")
    
    # Validate full name not empty
    full_name_clean = full_name_val.strip()
    if not full_name_clean:
        raise HTTPException(status_code=400, detail="Ad soyad boş bırakılamaz.")
    
    # Validate email format
    email_clean = turkish_lower(email_val.strip())
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Geçersiz e-posta formatı.")
        
    # Check duplicate email
    from src.services.database import get_user_by_email
    if get_user_by_email(email_clean):
        raise HTTPException(status_code=409, detail="Bu e-posta adresi zaten kayıtlı.")
        
    if len(user.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Şifre çok uzun (maksimum 72 byte olmalıdır).")
        
    # Determine or generate username
    if user.username:
        username_clean = turkish_lower(user.username.strip())
        from src.services.database import get_user_by_username
        if get_user_by_username(username_clean):
            raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten alınmış.")
    else:
        # Generate unique username from email prefix
        prefix = email_clean.split("@")[0]
        import re
        username_base = re.sub(r"[^a-zA-Z0-9]", "", prefix)
        if not username_base:
            username_base = "user"
            
        username_clean = username_base
        from src.services.database import get_user_by_username
        suffix_counter = 1
        while get_user_by_username(username_clean):
            username_clean = f"{username_base}{suffix_counter}"
            suffix_counter += 1
            
    hashed = get_password_hash(user.password)
    logger.info(f"REGISTER | Yeni kayıt denemesi. email='{email_clean}', username='{username_clean}'")
    
    try:
        success = create_user(username=username_clean, password_hash=hashed, email=email_clean, full_name=full_name_clean)
        if not success:
            logger.warning(f"REGISTER | Database error creating user: '{email_clean}'")
            raise HTTPException(status_code=400, detail="Kayıt işlemi başarısız oldu.")
            
        logger.info(f"REGISTER | Kullanıcı başarıyla oluşturuldu. email='{email_clean}'")
        return {"message": "Kayıt başarılı", "email": email_clean, "full_name": full_name_clean}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"REGISTER | Exception: {e}")
        raise HTTPException(status_code=500, detail=f"Sunucu hatası oluştu: {str(e)}")

@app.post("/login")
def login(request: Request, user: LoginRequest):
    from src.core.middlewares import get_client_ip
    client_ip = get_client_ip(request)
    
    if (not user.email and not user.username) or not user.password:
        raise HTTPException(status_code=400, detail="E-posta/kullanıcı adı ve şifre gereklidir.")
        
    db_user = None
    from src.services.database import get_user_by_email, get_user_by_username
    
    if user.email:
        email_clean = turkish_lower(user.email.strip())
        db_user = get_user_by_email(email_clean)
    elif user.username:
        username_clean = turkish_lower(user.username.strip())
        db_user = get_user_by_username(username_clean)
        if db_user:
            email_clean = db_user["email"] or "anonymous"
        else:
            email_clean = username_clean
    else:
        email_clean = "anonymous"
        
    # Combined IP + Email brute force lockout check
    if brute_force_protector.is_blocked(client_ip, email_clean):
        logger.error(f"Brute-force lockout active | IP: {client_ip} | User: {email_clean}")
        raise HTTPException(
            status_code=429, 
            detail="Çok fazla başarısız giriş denemesi. Lütfen 10 dakika sonra tekrar deneyin."
        )

    # Başarısız Senaryo Kontrolleri
    def _handle_failure(reason: str):
        brute_force_protector.register_failure(client_ip, email_clean)
        logger.warning(f"Failed login attempt | IP: {client_ip} | Email/Username: {email_clean} | Reason: {reason}")
        
        # Write login_failed audit log
        try:
            from src.services.database import SessionLocal
            from src.services.compliance_service import compliance_service
            db = SessionLocal()
            try:
                compliance_service.log_security_event(
                    db=db,
                    user_id=email_clean if email_clean != "anonymous" else None,
                    event_type="login_failed",
                    ip_address=client_ip,
                    user_agent=request.headers.get("User-Agent", "unknown_ua")[:200],
                    severity="WARNING",
                    metadata={"reason": reason}
                )
            finally:
                db.close()
        except Exception as audit_err:
            logger.error(f"AUDIT | Failed to write login_failed audit log: {audit_err}")
            
        raise HTTPException(status_code=400, detail="Geçersiz e-posta, kullanıcı adı veya şifre.")

    if len(user.password.encode("utf-8")) > 72:
        _handle_failure("Password string limits exceeded")

    if not db_user:
        logger.warning(f"LOGIN | Kullanıcı bulunamadı: email/username='{email_clean}'")
        _handle_failure("User not found in DB")
    
    if not verify_password(user.password, db_user["password_hash"]):
        logger.warning(f"LOGIN | Yanlış şifre: email/username='{email_clean}'")
        _handle_failure("Incorrect password")
    
    # Reset attempts counter
    brute_force_protector.register_success(client_ip, email_clean)
    logger.info(f"Successful login | IP: {client_ip} | Email/Username: {email_clean}")
    
    # Write login_success audit log
    try:
        from src.services.database import SessionLocal
        from src.services.compliance_service import compliance_service
        db = SessionLocal()
        try:
            compliance_service.log_security_event(
                db=db,
                user_id=db_user["username"],
                event_type="login_success",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent", "unknown_ua")[:200],
                severity="INFO"
            )
        finally:
            db.close()
    except Exception as audit_err:
        logger.error(f"AUDIT | Failed to write login_success audit log: {audit_err}")
        
    token_data = {
        "sub": db_user["username"],
        "user_id": db_user["id"],
        "email": db_user["email"],
        "full_name": db_user["full_name"]
    }
    token = create_access_token(data=token_data)
    logger.info(f"LOGIN | Token oluşturuldu ve döndürülüyor. email='{db_user['email']}'")
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": db_user["username"],
        "email": db_user["email"],
        "full_name": db_user["full_name"]
    }

@app.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security_jwt), username: str = Depends(get_current_user)):
    token = credentials.credentials
    
    # Expire bilgisini çekerek memory performansını optimize eder
    payload = decode_access_token(token)
    exp = payload.get("exp") if payload else None
    
    # Token sonsuza kadar ya da gerçek 'exp' bitene kadar engellenecek listesine eklenir
    token_blacklist_core.add(token, expires_at=exp)
    
    logger.info(f"Logout event for user: {username}")
    return {"status": "ok", "message": "Başarıyla çıkış yapıldı."}

@app.post("/predict", response_model=ChatResponse)
@limiter.limit(security_config.RATE_LIMIT_PREDICT)
async def predict(request: Request, body: ChatRequest, background_tasks: BackgroundTasks, username: str = Depends(get_current_user)):
    global predictor
    start_time = time.time()
    
    # 1. Validation & Sanitization Layer
    try:
        clean_text = input_validator_core.validate_and_sanitize(body.text, user_id=username)
        clean_text = prepare_model_input(clean_text)
    except ValueError as ve:
        # Note: input_validator_core zaten gerekli loglamayı (WARNING/ERROR) yapıyor
        raise HTTPException(status_code=400, detail=str(ve))
        
    if not predictor:
        raise HTTPException(status_code=500, detail="Modeller henüz yüklenmedi veya başlatılamadı.")

    user_text = clean_text  # Zırhlanmış ve temizlenmiş metni kullan
    analysis = predictor.predict_both(user_text)
    
    if "error" in analysis.get("emotion", {}) or "error" in analysis.get("crisis_detection", {}):
         emotion_label = "neutral"
         risk_label = "Normal"
         logger.warning("Local AI models not loaded, falling back to default labels and GPT.")
    else:
         raw_emotion = analysis["emotion"]["label"]
         emotion_confidence = analysis["emotion"].get("confidence", 1.0)
         # Confidence threshold: low-confidence emotion predictions are unreliable
         # on short/technical/greeting inputs. Force "neutral" below 0.55.
         _EMOTION_CONFIDENCE_THRESHOLD = 0.55
         if emotion_confidence < _EMOTION_CONFIDENCE_THRESHOLD:
             emotion_label = "neutral"
             logger.info(
                 "PREDICT | Emotion confidence %.3f < %.2f for user='%s' \u2014 forcing neutral (raw label: %s)",
                 emotion_confidence, _EMOTION_CONFIDENCE_THRESHOLD, username, raw_emotion
             )
         else:
             emotion_label = raw_emotion
         risk_label = analysis["crisis_detection"]["label"]

    emergency_msg = None
    if str(risk_label).lower() in ["kriz", "1", "crisis"]:
        emergency_msg = "Lütfen acil yardıma ihtiyacınız varsa 112'yi veya 114 Psikolojik Destek Hattını arayın."

    # Fetch User Profile Preferences
    from src.response_engine.models import UserPreferences
    try:
        profile = get_or_create_profile(username)
        user_prefs = UserPreferences(
            response_style=profile.get("response_style", "supportive"),
            preferred_language=profile.get("preferred_language", "tr"),
            privacy_mode=profile.get("privacy_mode", False),
            answer_length_preference=profile.get("answer_length_preference", "medium")
        )
    except Exception as e:
        logger.error(f"Error fetching profile for {username}, using defaults: {e}")
        user_prefs = UserPreferences()

    engine_input = EngineInput(
        text=user_text,
        emotion=emotion_label,
        risk=risk_label,
        user_id=username,
        language=user_prefs.preferred_language,
        preferences=user_prefs
    )
    engine_output = response_engine.generate_response(engine_input)
    chatgpt_response = engine_output.final_text

    # Align risk and emergency contact if rule-based safety layer triggered crisis fallback
    safety_meta = engine_output.metadata.get("safety", {})
    if not safety_meta.get("is_safe", True) and safety_meta.get("safety_reason") == "immediate_danger":
        risk_label = "kriz"
        emergency_msg = "Lütfen acil yardıma ihtiyacınız varsa 112'yi veya 114 Psikolojik Destek Hattını arayın."

    latency = (time.time() - start_time) * 1000

    # Generate unique message UUID for tracking emotion timeline event
    message_id = str(uuid.uuid4())
    
    # Securely save the emotion event to SQLite (totally raw-text free)
    save_emotion_event(
        user_id=username,
        message_id=message_id,
        emotion=emotion_label,
        risk=risk_label,
        source="predict"
    )

    # Invalidate analytical caches for immediate data consistency
    invalidate_user_caches(username)

    background_tasks.add_task(
        log_interaction, 
        user_id=username, 
        user_text=user_text, 
        emotion=emotion_label, 
        risk=risk_label, 
        language=body.language, 
        latency_ms=latency
    )

    return ChatResponse(
        emotion=emotion_label,
        risk=risk_label,
        response=chatgpt_response,
        emergency_contact=emergency_msg
    )

@app.get("/history")
def get_history(username: str = Depends(get_current_user)):
    raw_history = get_chat_history(username)
    formatted_history = []
    for item in raw_history:
        formatted_history.append({
            "id": item.get("id"),
            "role": item["role"],
            "text": item["content"],
            "timestamp": item.get("timestamp")
        })
    return formatted_history

@app.get("/profile", response_model=ProfileResponse)
def get_profile(username: str = Depends(get_current_user)):
    try:
        profile = get_or_create_profile(username)
        return profile
    except Exception as e:
        logger.error(f"Error fetching profile for {username}: {e}")
        raise HTTPException(status_code=500, detail="Profil bilgileri alınamadı.")

@app.put("/profile", response_model=ProfileResponse)
def update_profile(body: ProfileUpdateRequest, request: Request, username: str = Depends(get_current_user)):
    # Basic Validation
    if body.display_name is not None:
        name_clean = body.display_name.strip()
        if not name_clean:
            raise HTTPException(status_code=400, detail="Görünen ad boş bırakılamaz.")
        import re
        pattern = re.compile(r"^[a-zA-ZçğıöşüÇĞİÖŞÜ0-9._\-\s]+$")
        if not pattern.match(name_clean):
            raise HTTPException(status_code=400, detail="Görünen ad geçersiz karakterler içeriyor.")
        if len(name_clean) > 50:
            raise HTTPException(status_code=400, detail="Görünen ad 50 karakterden uzun olamaz.")
    
    if body.bio is not None:
        if len(body.bio) > 250:
            raise HTTPException(status_code=400, detail="Biyografi 250 karakterden uzun olamaz.")
    
    allowed_langs = ["tr", "en"]
    if body.preferred_language and body.preferred_language not in allowed_langs:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen dil. Şunlar olabilir: {allowed_langs}")
    
    allowed_styles = ["supportive", "direct", "empathetic"]
    if body.response_style and body.response_style not in allowed_styles:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen cevap stili. Şunlar olabilir: {allowed_styles}")

    allowed_themes = ["system", "light", "dark"]
    if body.theme_preference and body.theme_preference not in allowed_themes:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen tema. Şunlar olabilir: {allowed_themes}")

    allowed_lengths = ["short", "medium", "detailed"]
    if body.answer_length_preference and body.answer_length_preference not in allowed_lengths:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen cevap uzunluğu. Şunlar olabilir: {allowed_lengths}")

    try:
        # Check if privacy mode changed
        old_profile = get_or_create_profile(username)
        old_privacy = old_profile.get("privacy_mode", False)

        # Pydantic v2 compatible model_dump(exclude_unset=True)
        update_data = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
        updated_profile = update_user_profile(username, update_data)
        if not updated_profile:
            raise HTTPException(status_code=404, detail="Profil bulunamadı.")
        
        new_privacy = updated_profile.get("privacy_mode", False)

        # Write compliance audit logs
        try:
            from src.services.database import SessionLocal
            from src.services.compliance_service import compliance_service
            from src.core.middlewares import get_client_ip
            db = SessionLocal()
            try:
                # 1. Log profile update
                compliance_service.log_security_event(
                    db=db,
                    user_id=username,
                    event_type="profile_update",
                    ip_address=get_client_ip(request),
                    user_agent=request.headers.get("User-Agent", "unknown_ua")[:200],
                    severity="INFO"
                )
                # 2. Log privacy mode enable/disable if changed
                if old_privacy != new_privacy:
                    compliance_service.log_security_event(
                        db=db,
                        user_id=username,
                        event_type="privacy_mode_enabled" if new_privacy else "privacy_mode_disabled",
                        ip_address=get_client_ip(request),
                        user_agent=request.headers.get("User-Agent", "unknown_ua")[:200],
                        severity="INFO"
                    )
            finally:
                db.close()
        except Exception as audit_err:
            logger.error(f"AUDIT | Failed to write profile update audit logs: {audit_err}")

        # Invalidate cached analytics due to potential preference/privacy mode changes
        invalidate_user_caches(username)
        return updated_profile
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating profile for {username}: {e}")
        raise HTTPException(status_code=500, detail="Profil güncellenemedi.")

@app.post("/profile/photo", response_model=ProfileResponse)
async def upload_profile_photo(file: UploadFile = File(...), username: str = Depends(get_current_user)):
    # 1. Validation: File Type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Sadece JPEG, PNG veya WEBP dosyaları kabul edilir.")
    
    # 2. Validation: File Size (2MB)
    MAX_SIZE = 2 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Dosya boyutu 2 MB'dan büyük olamaz.")
    
    # 3. Secure Filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    unique_filename = f"{username}_{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # 4. Save File
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"File save error: {e}")
        raise HTTPException(status_code=500, detail="Dosya kaydedilemedi.")
    
    # 5. Update DB (Optionally delete old file logic can be added here)
    photo_url = f"/uploads/profile_photos/{unique_filename}"
    try:
        updated_profile = update_user_profile(username, {"profile_photo_url": photo_url})
        return updated_profile
    except Exception as e:
        logger.error(f"DB update error after photo upload: {e}")
        raise HTTPException(status_code=500, detail="Profil güncellenirken hata oluştu.")


@app.get("/analytics/summary")
def get_summary(admin: str = Depends(verify_admin)):
    try:
        return get_analytics_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/timeline")
def get_timeline(admin: str = Depends(verify_admin)):
    try:
        return get_analytics_timeline()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ENTERPRISE SECURITY & PRIVACY COMPLIANCE ENDPOINTS (JWT SECURED) ───────

@app.get("/privacy/consent", response_model=UserConsentResponse)
def get_user_consent(username: str = Depends(get_current_user)):
    """Retrieves or initializes explicit user KVKK/GDPR opt-in consents."""
    from src.services.database import SessionLocal, UserConsent
    db = SessionLocal()
    try:
        consent = db.query(UserConsent).filter(UserConsent.user_id == username).first()
        if not consent:
            # Opt-in Principle: Explicitly default all wellness/analytics consents to False!
            consent = UserConsent(
                user_id=username,
                privacy_policy_version="v1.0",
                terms_version="v1.0",
                analytics_consent=False,
                wellness_insights_consent=False,
                notifications_consent=False,
                ai_processing_consent=False
            )
            db.add(consent)
            db.commit()
            db.refresh(consent)
        return {
            "privacy_policy_version": consent.privacy_policy_version,
            "terms_version": consent.terms_version,
            "analytics_consent": consent.analytics_consent,
            "wellness_insights_consent": consent.wellness_insights_consent,
            "notifications_consent": consent.notifications_consent,
            "ai_processing_consent": consent.ai_processing_consent
        }
    finally:
        db.close()


@app.post("/privacy/consent", response_model=UserConsentResponse)
def update_user_consent(request: Request, body: UpdateConsentRequest, username: str = Depends(get_current_user)):
    """Updates explicit user consents and writes consent_updated secure audit logs."""
    from src.services.database import SessionLocal, UserConsent
    from src.services.compliance_service import compliance_service
    from src.core.middlewares import get_client_ip
    
    db = SessionLocal()
    try:
        consent = db.query(UserConsent).filter(UserConsent.user_id == username).first()
        if not consent:
            consent = UserConsent(user_id=username)
            db.add(consent)
        
        consent.analytics_consent = body.analytics_consent
        consent.wellness_insights_consent = body.wellness_insights_consent
        consent.notifications_consent = body.notifications_consent
        consent.ai_processing_consent = body.ai_processing_consent
        consent.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(consent)
        
        # Salted & masked audit logging
        meta_payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
        compliance_service.log_security_event(
            db=db,
            user_id=username,
            event_type="consent_updated",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent", "unknown_ua")[:200],
            severity="INFO",
            metadata=meta_payload
        )
        
        return {
            "privacy_policy_version": consent.privacy_policy_version,
            "terms_version": consent.terms_version,
            "analytics_consent": consent.analytics_consent,
            "wellness_insights_consent": consent.wellness_insights_consent,
            "notifications_consent": consent.notifications_consent,
            "ai_processing_consent": consent.ai_processing_consent
        }
    finally:
        db.close()


@app.get("/privacy/export")
def get_privacy_export(request: Request, username: str = Depends(get_current_user)):
    """Generates and downloads a complete, sanitized copy of user data conforming to GDPR Article 20."""
    from src.services.database import SessionLocal
    from src.services.compliance_service import compliance_service
    from src.core.middlewares import get_client_ip
    from src.core.metrics import DATA_EXPORTS_TOTAL
    
    db = SessionLocal()
    try:
        DATA_EXPORTS_TOTAL.inc()
        payload = compliance_service.export_user_data(db, username)
        
        compliance_service.log_security_event(
            db=db,
            user_id=username,
            event_type="data_export_requested",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent", "unknown_ua")[:200],
            severity="INFO"
        )
        return payload
    finally:
        db.close()


@app.delete("/privacy/delete")
def delete_privacy_account(request: Request, body: DeleteDataRequest, username: str = Depends(get_current_user)):
    """Performs permanent account deletion, soft-deleting memories, and anonymizing analytical histories."""
    if body.confirm != "DELETE_MY_DATA":
        raise HTTPException(
            status_code=400, 
            detail="Hesap silme işlemini onaylamak için lütfen gövdede 'DELETE_MY_DATA' metnini gönderin."
        )
        
    from src.services.database import SessionLocal
    from src.services.compliance_service import compliance_service
    from src.core.middlewares import get_client_ip
    from src.core.metrics import DATA_DELETIONS_TOTAL
    
    db = SessionLocal()
    try:
        compliance_service.log_security_event(
            db=db,
            user_id=username,
            event_type="data_delete_requested",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent", "unknown_ua")[:200],
            severity="CRITICAL"
        )
        
        success = compliance_service.delete_user_data(db, username)
        if not success:
            raise HTTPException(status_code=500, detail="Hesabınız silinirken teknik bir hata oluştu.")
            
        invalidate_user_caches(username)
        DATA_DELETIONS_TOTAL.inc()
        
        return {
            "status": "ok", 
            "message": "Hesabınız ve tüm kişisel verileriniz KVKK/GDPR kapsamında kalıcı olarak ve geri döndürülemez şekilde silinmiştir."
        }
    finally:
        db.close()


# ── ADVANCED PERSONAL CONTEXT ENGINE ENDPOINTS (JWT SECURED) ───────────────

@app.get("/memory", response_model=list[MemoryResponse], responses={403: {"model": AccessDeniedResponse}})
def get_user_memories_route(username: str = Depends(require_premium_user)):
    """
    Retrieves the active, transparent, structured memory profile of the user.
    Hides raw database columns and formats correctly for UI presentation.
    """
    try:
        memories = get_active_memories_for_user(username)
        response_data = []
        for r in memories:
            mtype = r.get("memory_type") or r.get("memory_key") or "preference"
            response_data.append(
                MemoryResponse(
                    id=r["id"],
                    memory_type=mtype,
                    memory_text=r["memory_value"],
                    confidence=r["confidence"],
                    sensitivity=r.get("sensitivity", "low"),
                    last_reinforced_at=r.get("last_reinforced_at")
                )
            )
        return response_data
    except Exception as e:
        logger.error(f"Error in GET /memory for user {username}: {e}")
        raise HTTPException(status_code=500, detail="Bellek listesi alınırken hata oluştu.")


@app.delete("/memory/{memory_id}", responses={403: {"model": AccessDeniedResponse}})
def delete_user_memory_route(memory_id: int, username: str = Depends(require_premium_user)):
    """
    Soft-deletes a single memory record with ownership validation (anti-IDOR).
    """
    try:
        success = delete_memory_for_user(memory_id, username)
        if not success:
            raise HTTPException(status_code=404, detail="Hafıza bulunamadı veya yetkiniz yok.")
        return {"status": "ok", "message": "Bellek başarıyla silindi."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in DELETE /memory/{memory_id} for user {username}: {e}")
        raise HTTPException(status_code=500, detail="Bellek silinirken hata oluştu.")


@app.post("/memory/refresh", response_model=MemoryConsolidationStatsResponse, responses={403: {"model": AccessDeniedResponse}})
def refresh_user_memories_route(username: str = Depends(require_premium_user)):
    """
    Triggers deterministic memory consolidation (outdated decay, Jaccard similarity merging,
    and contradiction resolution) for the user.
    """
    try:
        stats = consolidate_memories(username)
        return MemoryConsolidationStatsResponse(
            status=stats.get("status", "success"),
            processed=stats.get("processed", 0),
            merged=stats.get("merged", 0),
            decayed=stats.get("decayed", 0),
            contradicted=stats.get("contradicted", 0)
        )
    except Exception as e:
        logger.error(f"Error in POST /memory/refresh for user {username}: {e}")
        raise HTTPException(status_code=500, detail="Bellek konsolidasyonu çalıştırılırken hata oluştu.")


# ── NEW USER EMOTION TIMELINE ENDPOINTS (JWT SECURED) ──────────────────────

@app.get("/analytics/emotions/timeline", response_model=list[EmotionTimelineItem], responses={403: {"model": AccessDeniedResponse}})
def get_user_timeline(days: int = 7, username: str = Depends(require_premium_user)):
    """
    Fetches the authenticated user's chronological emotion event timeline.
    Guarantees isolation (users can only access their own timeline data).
    """
    try:
        # Basic parameter validation
        if days <= 0 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365.")
            
        return get_user_emotion_timeline(user_id=username, days=days)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in GET /analytics/emotions/timeline: {e}")
        raise HTTPException(status_code=500, detail="Hafıza/timeline yüklenirken sunucu hatası oluştu.")


@app.get("/analytics/emotions/summary", response_model=EmotionSummaryResponse, responses={403: {"model": AccessDeniedResponse}})
def get_user_summary(days: int = 7, username: str = Depends(require_premium_user)):
    """
    Fetches the authenticated user's aggregated emotional trend summary.
    Guarantees isolation (users can only access their own summary data).
    """
    try:
        # Basic parameter validation
        if days <= 0 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365.")
            
        # Try retrieving emotional summary from Redis Cache
        cached_summary = cache_get(username, "emotion_summary", days)
        if cached_summary is not None:
            logger.info(f"CACHE HIT | UserID: {username} | emotion_summary days: {days}")
            return cached_summary

        summary = get_user_emotion_summary(user_id=username, days=days)
        # Store aggregations in Redis cache (TTL: 15 minutes)
        cache_set(username, "emotion_summary", summary, TTL_SUMMARY, days)
        return summary
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in GET /analytics/emotions/summary: {e}")
        raise HTTPException(status_code=500, detail="Hafıza/summary yüklenirken sunucu hatası oluştu.")


@app.get("/analytics/insights", response_model=list[BehavioralInsightResponse], responses={403: {"model": AccessDeniedResponse}})
def get_user_insights(days: int = 7, username: str = Depends(require_premium_user)):
    """
    Analyzes the authenticated user's emotion timeline patterns to generate wellness insights.
    Guarantees strict isolation and privacy/crisis safe rule-based extraction.
    """
    try:
        # Parameter validation
        if days <= 0 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365.")
            
        return generate_behavioral_insights(user_id=username, days=days)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in GET /analytics/insights: {e}")
        raise HTTPException(status_code=500, detail="Davranışsal içgörüler hesaplanırken hata oluştu.")


@app.get("/analytics/interventions", response_model=list[SmartInterventionResponse], responses={403: {"model": AccessDeniedResponse}})
def get_user_interventions(days: int = 7, username: str = Depends(require_premium_user)):
    """
    Analyzes user behavioral pattern insights to generate supportive, non-diagnostic wellness interventions.
    Guarantees strict isolation and privacy/crisis safe overrides.
    """
    try:
        # Parameter validation
        if days <= 0 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365.")
            
        return generate_smart_interventions(user_id=username, days=days)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in GET /analytics/interventions: {e}")
        raise HTTPException(status_code=500, detail="Wellness müdahaleleri hesaplanırken hata oluştu.")


@app.get("/analytics/scheduled-interventions", response_model=list[ScheduledInterventionResponse], responses={403: {"model": AccessDeniedResponse}})
def get_scheduled_interventions(username: str = Depends(require_premium_user)):
    """
    Fetches the authenticated user's scheduled interventions.
    Dynamically maps DB records to non-authoritative wellness titles and descriptions.
    """
    try:
        raw_list = get_scheduled_interventions_for_user(user_id=username)
        enriched = []
        for item in raw_list:
            enriched.append(enrich_intervention(item))
        return enriched
    except Exception as e:
        logger.error(f"Error in GET /analytics/scheduled-interventions: {e}")
        raise HTTPException(status_code=500, detail="Planlanmış wellness önerileri yüklenirken hata oluştu.")


@app.post("/analytics/scheduled-interventions/refresh", response_model=list[ScheduledInterventionResponse], responses={403: {"model": AccessDeniedResponse}})
def refresh_scheduled_interventions(username: str = Depends(require_premium_user)):
    """
    Triggers the intervention scheduler engine for the user and returns the refreshed schedule list.
    Guarantees strict isolation and privacy/crisis safe overrides.
    """
    try:
        raw_list = schedule_user_interventions(user_id=username)
        enriched = []
        for item in raw_list:
            enriched.append(enrich_intervention(item))
        return enriched
    except Exception as e:
        logger.error(f"Error in POST /analytics/scheduled-interventions/refresh: {e}")
        raise HTTPException(status_code=500, detail="Planlanmış wellness önerileri yenilenirken hata oluştu.")


def enrich_intervention(item: dict) -> dict:
    itype = item["type"]
    mapping = {
        "breathing_break": {
            "title": "Sabah kısa bir nefes molası",
            "description": "Güne birkaç dakikalık sakin nefes egzersizi ile başlamak iyi gelebilir."
        },
        "short_walk": {
            "title": "Öğleden sonra tazeleyici bir yürüyüş",
            "description": "Temiz hava almak ve adımlamak zihninizi dinlendirmek için güzel bir fırsat olabilir."
        },
        "social_connection": {
            "title": "Akşam yumuşak bir sosyal bağlantı",
            "description": "Değer verdiğiniz bir arkadaşınızla veya sevdiğiniz bir yakınınızla kısa bir paylaşım yapmak kendinizi daha hafif hissettirebilir."
        },
        "grounding_exercise": {
            "title": "Şimdiki ana odaklanmak için ufak bir egzersiz",
            "description": "Bulunduğunuz ortamdaki renklere veya seslere odaklanmak, zihinsel bir çapa görevi görerek sakinleşmeyi kolaylaştırabilir."
        },
        "positive_reflection": {
            "title": "Günün olumlu anlarına tatlı bir bakış",
            "description": "Bugün yaşadığınız küçük de olsa güzel bir anı veya şükran duyduğunuz bir detayı fark etmek, içsel dengenizi besleyebilir."
        },
        "priority_support": {
            "title": "Kendinize şefkatle yaklaşma vakti",
            "description": "Son dönemde yoğun stres hissetmiş olabilirsiniz. Yalnız değilsiniz; ihtiyaç duyduğunuz her an ücretsiz 112 veya 114 Psikolojik Destek kanallarından uzman desteği alabilirsiniz."
        },
        "hydration_reminder": {
            "title": "Bedensel zindelik için küçük bir bardak su",
            "description": "Düzenli su içmek zihinsel yorgunluğu azaltmaya ve kendinizi daha enerjik hissetmenize yardımcı olabilir."
        },
        "sleep_reminder": {
            "title": "Sakin bir uyku rutini hazırlığı",
            "description": "Uykudan önce ekranlardan uzaklaşmak ve kendinize rahatlatıcı bir ortam hazırlamak uykunuzu daha verimli kılabilir."
        }
    }
    info = mapping.get(itype, {
        "title": "Zihinsel wellness önerisi",
        "description": "Kendinize odaklanmak ve zihninizi dinlendirmek için küçük bir an ayırın."
    })
    
    try:
        utc_dt = datetime.fromisoformat(item["scheduled_for"])
        local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(ISTANBUL_TZ)
        scheduled_for_str = local_dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        scheduled_for_str = item["scheduled_for"]
        
    return {
        "type": item["type"],
        "priority": item["priority"],
        "scheduled_for": scheduled_for_str,
        "status": item["status"],
        "title": info["title"],
        "description": info["description"]
    }


@app.get("/analytics/reports/wellness", response_model=WellnessReportResponse, responses={403: {"model": AccessDeniedResponse}})
def get_wellness_report_endpoint(
    period: str = "daily",
    days: int = 7,
    username: str = Depends(require_premium_user)
):
    """
    Exposes the observational mental wellness reports.
    Supports period=daily and period=weekly. Fully JWT authenticated and isolated.
    """
    if period not in ["daily", "weekly"]:
        raise HTTPException(status_code=400, detail="Period değeri 'daily' veya 'weekly' olmalıdır.")
    try:
        # Check if the report is cached
        cached_report = cache_get(username, "wellness_report", period, days)
        if cached_report is not None:
            logger.info(f"CACHE HIT | UserID: {username} | report period: {period} days: {days}")
            return cached_report

        report = generate_wellness_report(user_id=username, period=period, days=days)
        # Save pre-calculated report in cache (TTL: 30 minutes)
        cache_set(username, "wellness_report", report, TTL_REPORTS, period, days)
        return report
    except Exception as e:
        logger.error(f"Error in GET /analytics/reports/wellness: {e}")
        raise HTTPException(status_code=500, detail="Wellness raporu oluşturulurken hata oluştu.")


@app.get("/analytics/reflections", response_model=ReflectionResponse, responses={403: {"model": AccessDeniedResponse}})
def get_reflections_endpoint(
    period: str = "daily",
    username: str = Depends(require_premium_user)
):
    """
    Exposes the personalized mental wellness reflection summaries.
    Supports period=daily and period=weekly. Fully JWT authenticated and isolated.
    """
    if period not in ["daily", "weekly"]:
        raise HTTPException(status_code=400, detail="Period değeri 'daily' veya 'weekly' olmalıdır.")
    try:
        reflection = generate_reflection(user_id=username, period=period)
        return reflection
    except Exception as e:
        logger.error(f"Error in GET /analytics/reflections: {e}")
        raise HTTPException(status_code=500, detail="Zihinsel refleksiyon özeti oluşturulurken hata oluştu.")


@app.get("/analytics/dashboard", response_model=WellnessDashboardResponse, responses={403: {"model": AccessDeniedResponse}})
def get_wellness_dashboard_endpoint(
    days: int = 7,
    username: str = Depends(require_premium_user)
):
    """
    Exposes the unified Mental Wellness Reporting Dashboard metrics.
    Accepts days=7 or days=30. Fully JWT authenticated and isolated.
    """
    if days not in [7, 30]:
        raise HTTPException(status_code=400, detail="Gün parametresi 7 veya 30 olmalıdır.")
    try:
        # Check cache
        cached_dashboard = cache_get(username, "dashboard", days)
        if cached_dashboard is not None:
            logger.info(f"CACHE HIT | UserID: {username} | dashboard days: {days}")
            return cached_dashboard

        dashboard = generate_wellness_dashboard(user_id=username, days=days)
        # Store in Redis cache (TTL: 10 minutes)
        cache_set(username, "dashboard", dashboard, TTL_DASHBOARD, days)
        return dashboard
    except Exception as e:
        logger.error(f"Error in GET /analytics/dashboard: {e}")
        raise HTTPException(status_code=500, detail="Wellness Dashboard verileri oluşturulurken hata oluştu.")


@app.post("/journal/mood", response_model=MoodJournalResponse)
def post_mood_journal_endpoint(
    request: CreateMoodJournalRequest,
    username: str = Depends(get_current_user)
):
    """
    Creates a new manual user Mood Journal entry.
    Secured with JWT, enforces local regex safety checks, and implements privacy-safe note masking.
    """
    valid_moods = ["happy", "calm", "anxious", "sad", "angry", "tired", "neutral"]
    if turkish_lower(request.mood) not in valid_moods:
        raise HTTPException(status_code=400, detail="Geçersiz mood değeri. Geçerli değerler: " + ", ".join(valid_moods))
    if not (1 <= request.intensity <= 5):
        raise HTTPException(status_code=400, detail="Yoğunluk 1 ile 5 arasında olmalıdır.")
    if request.note and len(request.note) > 500:
        raise HTTPException(status_code=400, detail="Not alanı en fazla 500 karakter olmalıdır.")

    note_text = request.note
    crisis_override = False

    # 1. Local Safety Regex Check
    if note_text and note_text.strip():
        is_safe, category = check_safety(note_text, mode="user_input")
        if not is_safe:
            crisis_override = True
            # Mask note securely
            note_text = "[Güvenlik Yönlendirmesi: İhtiyaç halinde ücretsiz 112 veya 114 Psikolojik Destek kanallarından uzman yardımı alabilirsiniz]"
            # Register immediate timeline crisis warning
            save_emotion_event(
                user_id=username,
                message_id=f"journal_safety_{int(time.time())}",
                emotion="Kriz",
                risk="kriz",
                source="journal"
            )

    # 2. Privacy Mode Check
    try:
        profile = get_or_create_profile(username)
        if profile and getattr(profile, "privacy_mode", False):
            # Mask note for total confidentiality
            note_text = "[Gizlilik Modu Aktif - Not Kaydedilmedi]"
    except Exception as e:
        logger.error(f"Error checking profile privacy mode: {e}")

    # 3. Save normal Emotion Timeline event if not crisis overridden
    if not crisis_override:
        mood_mapping = {
            "happy": "Mutluluk",
            "calm": "Sakin",
            "anxious": "Kaygı",
            "sad": "Üzüntü",
            "angry": "Öfke",
            "tired": "Yorgun",
            "neutral": "Nötr"
        }
        mapped_emotion = mood_mapping.get(turkish_lower(request.mood), "Nötr")
        save_emotion_event(
            user_id=username,
            message_id=f"journal_{int(time.time())}",
            emotion=mapped_emotion,
            risk="düşük",
            source="journal"
        )

    # 4. Save journal entry
    try:
        entry = save_mood_journal(
            user_id=username,
            mood=turkish_lower(request.mood),
            intensity=request.intensity,
            note=note_text,
            source="journal"
        )
        # Evict cache to refresh calculations on the dashboard/reports
        invalidate_user_caches(username)
        return {
            "id": entry.id,
            "user_id": entry.user_id,
            "mood": entry.mood,
            "intensity": entry.intensity,
            "note": entry.note,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "source": entry.source
        }
    except Exception as e:
        logger.error(f"Error saving mood journal entry: {e}")
        raise HTTPException(status_code=500, detail="Mood günlüğü kaydedilirken sunucu hatası oluştu.")


@app.get("/journal/mood", response_model=list[MoodJournalResponse])
def get_mood_journals_endpoint(
    days: int = 7,
    username: str = Depends(get_current_user)
):
    """
    Retrieves logged mood journals for the authenticated user in the requested timeframe.
    """
    try:
        entries = get_mood_journals_for_user(username, days=days)
        return entries
    except Exception as e:
        logger.error(f"Error fetching mood journal list: {e}")
        raise HTTPException(status_code=500, detail="Mood günlüğü listesi alınırken hata oluştu.")


@app.delete("/journal/mood/{journal_id}")
def delete_mood_journal_endpoint(
    journal_id: int,
    username: str = Depends(get_current_user)
):
    """
    Deletes a specific mood journal entry ensuring secure ownership validation.
    """
    success = delete_mood_journal(username, journal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı veya bu kaydı silme yetkiniz yok.")
    
    # Evict cache to refresh calculations on the dashboard/reports
    invalidate_user_caches(username)
    return {"detail": "Kayıt başarıyla silindi."}


@app.get("/notifications", response_model=list[NotificationResponse])
def get_notifications_endpoint(
    username: str = Depends(get_current_user)
):
    """
    Retrieves all planned push notifications for the authenticated user.
    """
    try:
        events = get_notification_events_for_user(username)
        return events
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        raise HTTPException(status_code=500, detail="Bildirim geçmişi alınırken hata oluştu.")


@app.post("/notifications/refresh", response_model=list[NotificationResponse])
def post_notifications_refresh_endpoint(
    username: str = Depends(get_current_user)
):
    """
    Refreshes the push notification planning schedule based on preferences, cooldowns, 
    and daily cap limits.
    """
    try:
        events = refresh_user_notifications(username)
        return events
    except Exception as e:
        logger.error(f"Error refreshing notifications: {e}")
        raise HTTPException(status_code=500, detail="Bildirim planlama takvimi yenilenirken hata oluştu.")


@app.post("/notifications/{notification_id}/mark-delivered")
def post_notification_delivered_endpoint(
    notification_id: int,
    username: str = Depends(get_current_user)
):
    """
    Marks a planned notification event as successfully delivered.
    """
    success = mark_notification_as_delivered(username, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bildirim kaydı bulunamadı veya yetkiniz yok.")
    
    # Evict cache to refresh calculations on the dashboard/reports
    invalidate_user_caches(username)
    return {"detail": "Bildirim başarıyla iletildi olarak işaretlendi."}





@app.get("/admin", response_class=HTMLResponse)
def read_admin(admin: str = Depends(verify_admin)):
    admin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "admin.html")
    if not os.path.exists(admin_path):
        raise HTTPException(status_code=404, detail="admin.html not found.")
    with open(admin_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
def health_check():
    import src.services.database as db
    from src.api.main import predictor
    
    # 1. DB check
    db_status = True
    try:
        with db.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = False
        
    # 2. Redis check
    from src.core.redis_client import redis_client
    redis_status = redis_client.ping()
    
    # 3. Worker check
    worker_status = False
    try:
        from src.workers.celery_app import celery_app
        if settings.CELERY_BROKER_URL:
            inspect = celery_app.control.inspect(timeout=0.5)
            if inspect:
                pings = inspect.ping()
                if pings:
                    worker_status = True
    except Exception:
        worker_status = False
        
    model_status = predictor is not None
    
    # Service is up if DB is connected
    status = "ok" if db_status else "error"
    
    return {
        "status": status,
        "environment": settings.APP_ENV,
        "version": "1.1.0",
        "database": db_status,
        "redis": redis_status,
        "worker": worker_status,
        "models": model_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/metrics")
def get_metrics():
    from fastapi import Response
    from src.core.metrics import generate_metrics_payload
    payload = generate_metrics_payload()
    return Response(content=payload, media_type="text/plain; version=0.0.4; charset=utf-8")

# ─── WebSocket Gateway ───────────────────────────────────────────────────────
@app.websocket("/ws/chat")
async def websocket_chat_endpoint(ws: WebSocket, token: Optional[str] = None):
    """
    Real-time chat WebSocket endpoint.

    Handshake: GET /ws/chat?token=<JWT>

    Güvenlik:
    - Token query param ile alınır; header desteği yok (WS spec gereği)
    - Token invalid/missing ise bağlantı 4001 koduyla reddedilir
    - Token, ham metin ve journal verisi loglanmaz
    - Payload > 64 KB ise bağlantı 4002 koduyla kapatılır
    - Rate limit aşılırsa bağlantı 4003 koduyla kapatılır
    """
    # ── JWT Doğrulama ──────────────────────────────────────────────────────
    if not token:
        await ws.close(code=4001, reason="Token gerekli")
        logger.warning("WS bağlantı reddedildi: token yok")
        return

    # Token blacklist kontrolü
    if security_config.TOKEN_BLACKLIST_ENABLED:
        if token_blacklist_core.is_blacklisted(token):
            await ws.close(code=4001, reason="Oturumunuz kapatılmış")
            logger.warning("WS: Blacklisted token kullanım girişimi")
            return

    payload = decode_access_token(token)
    if not payload:
        await ws.close(code=4001, reason="Geçersiz token")
        logger.warning("WS bağlantı reddedildi: geçersiz token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await ws.close(code=4001, reason="Token hatası")
        return

    # ── Bağlantı Kur ──────────────────────────────────────────────────────
    await connection_manager.connect(ws, user_id)

    import asyncio
    disconnect_reason = "client_close"

    try:
        while True:
            # ── Heartbeat Timeout (90s) Control ────────────────────────
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=90.0)
            except asyncio.TimeoutError:
                from src.core.metrics import WEBSOCKET_HEARTBEAT_TIMEOUTS_TOTAL
                WEBSOCKET_HEARTBEAT_TIMEOUTS_TOTAL.inc()
                disconnect_reason = "heartbeat_timeout"
                try:
                    await ws.send_text(encode_event(build_error("HEARTBEAT_TIMEOUT", "Bağlantı aktif olmadığından kapatıldı.")))
                    await ws.close(code=4004, reason="Heartbeat timeout")
                except Exception:
                    pass
                logger.warning("WS: Heartbeat timeout. Bağlantı kapatılıyor.")
                break

            # ── Payload boyut kontrolü (64 KB) ──────────────────────────
            if connection_manager.check_payload_size(raw):
                await ws.send_text(encode_event(build_error("PAYLOAD_TOO_LARGE", "Mesaj boyutu 64KB sınırını aşıyor")))
                await ws.close(code=4002, reason="Payload too large")
                disconnect_reason = "payload_too_large"
                logger.warning("WS: 64KB payload sınırı aşıldı. Bağlantı kapatıldı.")
                break

            # ── Rate limit kontrolü ──────────────────────────────────────
            if connection_manager.check_rate_limit(ws):
                await ws.send_text(encode_event(build_error("RATE_LIMITED", "Çok fazla istek. Lütfen bekleyin.")))
                await ws.close(code=4003, reason="Rate limited")
                disconnect_reason = "rate_limited"
                break

            # ── Event parse & validate ───────────────────────────────────
            try:
                event_type, event_payload = parse_inbound_event(raw)
            except EventValidationError as e:
                await ws.send_text(encode_event(build_error(e.code, e.message)))
                continue

            # ── Presence refresh (heartbeat) ─────────────────────────────
            await presence_service.refresh(user_id)

            # ── Event Handler ────────────────────────────────────────────
            if event_type == WsEventType.PING:
                await ws.send_text(encode_event(build_pong()))

            elif event_type == WsEventType.TYPING_START:
                await connection_manager.handle_typing_start(user_id)

            elif event_type == WsEventType.TYPING_STOP:
                await connection_manager.handle_typing_stop(user_id)

            elif event_type == WsEventType.CHAT_MESSAGE:
                assert isinstance(event_payload, ChatMessagePayload)

                if predictor is None:
                    await ws.send_text(encode_event(
                        build_error("SERVICE_UNAVAILABLE", "AI modeli henüz yüklenemedi")
                    ))
                    continue

                # Güvenlik: mesaj içeriği loglanmaz
                text = event_payload.text
                lang = event_payload.language or "tr"

                # Safety check
                safety = check_safety(text)
                if not safety.get("is_safe", True):
                    emergency = safety.get("emergency_contact")
                    # Crisis event — response engine devreye girer
                    response_data = await _process_ws_message(user_id, text, lang)
                    response_data["emergency_contact"] = emergency
                else:
                    response_data = await _process_ws_message(user_id, text, lang)

                # Typing indicator: assistant yazıyor
                await connection_manager.send_to_user(
                    user_id, build_typing_indicator(True)
                )

                resp_event = build_chat_response(
                    emotion=response_data.get("emotion", "neutral"),
                    risk=response_data.get("risk", "low"),
                    response_text=response_data.get("response", ""),
                    emergency_contact=response_data.get("emergency_contact"),
                )

                # Typing indicator kapat
                await connection_manager.send_to_user(
                    user_id, build_typing_indicator(False)
                )

                await connection_manager.send_to_user(user_id, resp_event)

    except WebSocketDisconnect as e:
        logger.info("WS bağlantı client tarafından kapatıldı. Code: %d", e.code)
        disconnect_reason = f"client_disconnect_{e.code}"
    except Exception as exc:
        logger.error("WS beklenmedik hata: %s", type(exc).__name__)
        disconnect_reason = f"exception_{type(exc).__name__}"
    finally:
        await connection_manager.disconnect(ws, user_id, reason=disconnect_reason)


async def _process_ws_message(user_id: str, text: str, lang: str) -> dict:
    """
    REST /predict ile aynı inference mantığını çalıştırır.
    Metin içeriği loglanmaz.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = await loop.run_in_executor(pool, _sync_process_message, user_id, text, lang)
    return result


def _sync_process_message(user_id: str, text: str, lang: str) -> dict:
    """Sync wrapper — predictor inference (thread-safe)."""
    try:
        import uuid
        import time

        start_time = time.time()
        
        # 1. Preprocess & Validate input
        model_input = prepare_model_input(text)
        
        # 2. Local AI Model prediction
        analysis = predictor.predict_both(model_input)
        if "error" in analysis.get("emotion", {}) or "error" in analysis.get("crisis_detection", {}):
            emotion_label = "neutral"
            risk_label = "Normal"
            logger.warning("Local AI models not loaded, falling back to default labels and GPT.")
        else:
            emotion_label = analysis["emotion"]["label"]
            risk_label = analysis["crisis_detection"]["label"]

        # 3. User Preferences Fetching
        from src.response_engine.models import UserPreferences
        try:
            profile = get_or_create_profile(user_id)
            user_prefs = UserPreferences(
                response_style=profile.get("response_style", "supportive"),
                preferred_language=profile.get("preferred_language", "tr"),
                privacy_mode=profile.get("privacy_mode", False),
                answer_length_preference=profile.get("answer_length_preference", "medium")
            )
        except Exception as e:
            logger.error(f"Error fetching profile for WS {user_id}, using defaults: {e}")
            user_prefs = UserPreferences()

        # 4. Invoke Response Engine
        engine_input = EngineInput(
            text=model_input,
            emotion=emotion_label,
            risk=risk_label,
            user_id=user_id,
            language=user_prefs.preferred_language,
            preferences=user_prefs
        )
        engine_output = response_engine.generate_response(engine_input)
        chatgpt_response = engine_output.final_text

        # 5. Safety alignment
        safety_meta = engine_output.metadata.get("safety", {})
        emergency_msg = None
        if not safety_meta.get("is_safe", True) and safety_meta.get("safety_reason") == "immediate_danger":
            risk_label = "kriz"
            emergency_msg = "Lütfen acil yardıma ihtiyacınız varsa 112'yi veya 114 Psikolojik Destek Hattını arayın."
        elif str(risk_label).lower() in ["kriz", "1", "crisis"]:
            emergency_msg = "Lütfen acil yardıma ihtiyacınız varsa 112'yi veya 114 Psikolojik Destek Hattını arayın."

        # 6. Save emotion event
        message_id = str(uuid.uuid4())
        save_emotion_event(
            user_id=user_id,
            message_id=message_id,
            emotion=emotion_label,
            risk=risk_label,
            source="websocket"
        )

        # 7. Invalidate analytics cache
        invalidate_user_caches(user_id)

        # 8. Log interaction (synchronously in ThreadPoolExecutor thread)
        latency = (time.time() - start_time) * 1000
        log_interaction(
            user_id=user_id, 
            user_text=model_input, 
            emotion=emotion_label, 
            risk=risk_label, 
            language=lang, 
            latency_ms=latency
        )

        return {
            "emotion": emotion_label,
            "risk": risk_label,
            "response": chatgpt_response,
            "emergency_contact": emergency_msg,
        }
    except Exception as exc:
        logger.exception("WS inference hatası")
        return {"emotion": "neutral", "risk": "low", "response": "Bir hata oluştu, lütfen tekrar deneyin.", "emergency_contact": None}


@app.get("/ws/status")
async def websocket_status(current_user: str = Depends(get_current_user)):
    """WebSocket bağlantı durumu ve metrikler (admin/debug)."""
    return {
        "total_connections": connection_manager.total_connections,
        "connected_users": connection_manager.connected_users,
        "redis_pubsub_available": pubsub_manager.is_available,
        "presence_redis_available": presence_service.is_redis_available,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Faz 10 Prompt 7 — Advanced Analytics & Recommendation Engine Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

class RecommendationActionItem(BaseModel):
    label: str
    action_type: str

class RecommendationResponse(BaseModel):
    id: str
    recommendation_type: str
    title: str
    description: str
    priority: str
    confidence: float
    reason: str
    actions: list
    status: str
    created_at: Optional[str]
    expires_at: Optional[str]
    source: str

class RecommendationFeedbackRequest(BaseModel):
    feedback: str  # "helpful" | "not_helpful" | "dismissed"


@app.get(
    "/analytics/recommendations",
    summary="Kişiselleştirilmiş wellness önerilerini getir",
    tags=["Recommendations"],
    responses={403: {"model": AccessDeniedResponse}}
)
def get_recommendations(username: str = Depends(require_premium_user)):
    """
    Returns currently active (non-expired) wellness recommendations for the authenticated user.

    Privacy guarantees:
      - No raw chat text is used or returned
      - No medical diagnosis language
      - All reasons are wellness-safe metadata-derived explanations

    Returns cached active recommendations. Use POST /refresh to regenerate.
    """
    try:
        from src.services.recommendation_engine import get_active_recommendations, expire_old_recommendations
        # First expire stale ones
        expire_old_recommendations(user_id=username)
        recs = get_active_recommendations(user_id=username)
        logger.info(
            "RECOMMENDATION_ENGINE | get_active | user=%s | count=%d",
            username, len(recs),
        )
        return recs
    except Exception as e:
        logger.error("RECOMMENDATION_ENGINE | get_error | user=%s | %s", username, e)
        raise HTTPException(status_code=500, detail="Öneriler alınamadı.")


@app.post(
    "/analytics/recommendations/refresh",
    summary="Wellness önerilerini yenile",
    tags=["Recommendations"],
    responses={403: {"model": AccessDeniedResponse}}
)
def refresh_recommendations(username: str = Depends(require_premium_user)):
    """
    Generates fresh personalised recommendations for the authenticated user.

    Checks consent (wellness_insights_consent) and privacy_mode before generation.
    Duplicate guard: will not re-create recommendation types already active within 48h.

    Privacy guarantees:
      - Metadata-driven only (emotion summary, mood intensity, intervention history)
      - No raw chat text accessed
      - No raw journal note accessed
    """
    try:
        # Load user profile for privacy/consent signals
        profile = get_or_create_profile(username)
        privacy_mode = profile.get("privacy_mode", False)

        # Load consent record
        from src.services.database import SessionLocal, UserConsent
        db = SessionLocal()
        try:
            consent = db.query(UserConsent).filter(UserConsent.user_id == username).first()
            wellness_consent = consent.wellness_insights_consent if consent else False
        finally:
            db.close()

        from src.services.recommendation_engine import (
            generate_recommendations,
            expire_old_recommendations,
        )
        from src.core.metrics import (
            RECOMMENDATION_GENERATED_TOTAL,
            RECOMMENDATION_CRISIS_PRIORITY_TOTAL,
        )

        # Expire stale first
        expire_old_recommendations(user_id=username)

        recs = generate_recommendations(
            user_id=username,
            privacy_mode=privacy_mode,
            wellness_insights_consent=wellness_consent,
        )

        # Instrument metrics
        for rec in recs:
            RECOMMENDATION_GENERATED_TOTAL.labels(
                recommendation_type=rec.get("recommendation_type", "unknown")
            ).inc()
            if rec.get("recommendation_type") == "professional_support":
                RECOMMENDATION_CRISIS_PRIORITY_TOTAL.inc()

        logger.info(
            "RECOMMENDATION_ENGINE | refreshed | user=%s | generated=%d | privacy=%s | consent=%s",
            username, len(recs), privacy_mode, wellness_consent,
        )

        return {
            "generated": len(recs),
            "recommendations": recs,
            "privacy_mode": privacy_mode,
            "wellness_insights_consent": wellness_consent,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "RECOMMENDATION_ENGINE | refresh_error | user=%s | %s", username, e
        )
        raise HTTPException(status_code=500, detail="Öneriler yenilenemedi.")


@app.post(
    "/analytics/recommendations/{rec_id}/feedback",
    summary="Öneri için geri bildirim gönder",
    tags=["Recommendations"],
    responses={403: {"model": AccessDeniedResponse}}
)
def submit_recommendation_feedback(
    rec_id: str,
    body: RecommendationFeedbackRequest,
    username: str = Depends(require_premium_user),
):
    """
    Records user feedback on a recommendation.

    Allowed feedback values:
      - "helpful"       → marks as completed, stored for future scoring
      - "not_helpful"   → marks as completed with negative signal
      - "dismissed"     → marks as dismissed

    Ownership enforced: users can only feedback their own recommendations.
    """
    allowed = {"helpful", "not_helpful", "dismissed"}
    if body.feedback not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz feedback değeri. Şunlar olabilir: {sorted(allowed)}",
        )

    try:
        from src.services.recommendation_engine import record_feedback
        from src.core.metrics import RECOMMENDATION_FEEDBACK_TOTAL, RECOMMENDATION_DISMISSED_TOTAL

        success = record_feedback(
            user_id=username,
            rec_id=rec_id,
            feedback=body.feedback,
        )
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Öneri bulunamadı veya bu öneri size ait değil.",
            )

        # Instrument metrics
        RECOMMENDATION_FEEDBACK_TOTAL.labels(feedback_type=body.feedback).inc()
        if body.feedback == "dismissed":
            # We don't know rec_type here without a DB lookup; use generic label
            RECOMMENDATION_DISMISSED_TOTAL.labels(recommendation_type="unknown").inc()

        logger.info(
            "RECOMMENDATION_ENGINE | feedback | user=%s | rec_id=%s | feedback=%s",
            username, rec_id, body.feedback,
        )
        return {"status": "ok", "rec_id": rec_id, "feedback": body.feedback}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "RECOMMENDATION_ENGINE | feedback_error | user=%s | %s", username, e
        )
        raise HTTPException(status_code=500, detail="Geri bildirim kaydedilemedi.")


# ── Subscription and Payment Endpoints ─────────────────────────────────────
from decimal import Decimal
from fastapi import Header
from src.services.database import (
    SessionLocal,
    SubscriptionPlan,
    UserSubscription,
    PaymentTransaction,
    SubscriptionStatus,
    PaymentStatus
)
from src.services.payment_provider import get_payment_provider, ProviderNotConfigured

class PlanResponseItem(BaseModel):
    id: int
    name: str
    price_lira: Decimal
    billing_interval: str
    description: Optional[str] = None

class CheckoutRequest(BaseModel):
    plan_id: int

class CheckoutResponse(BaseModel):
    checkout_url: str
    transaction_id: str
    status: str

class SubscriptionStatusResponse(BaseModel):
    has_premium: bool
    plan_name: str
    status: str
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool

class PaymentHistoryItem(BaseModel):
    transaction_id: str
    amount: Decimal
    currency: str
    status: str
    created_at: str

@app.get("/subscriptions/plans", response_model=list[PlanResponseItem])
def get_plans():
    db = SessionLocal()
    try:
        plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()
        return [
            PlanResponseItem(
                id=p.id,
                name=p.name,
                price_lira=p.price_lira,
                billing_interval=p.billing_interval,
                description=p.description
            ) for p in plans
        ]
    finally:
        db.close()

@app.get("/subscriptions/me", response_model=SubscriptionStatusResponse)
def get_my_subscription(username: str = Depends(get_current_user)):
    db = SessionLocal()
    try:
        sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == username,
            UserSubscription.status == SubscriptionStatus.ACTIVE
        ).first()
        
        if not sub:
            return SubscriptionStatusResponse(
                has_premium=False,
                plan_name="free",
                status="inactive",
                current_period_end=None,
                cancel_at_period_end=False
            )
        
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
        plan_name = plan.name if plan else "free"
        has_premium = plan_name in ["premium", "professional_support"]
        
        return SubscriptionStatusResponse(
            has_premium=has_premium,
            plan_name=plan_name,
            status=sub.status.value,
            current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
            cancel_at_period_end=sub.cancel_at_period_end
        )
    finally:
        db.close()

@app.post("/subscriptions/checkout", response_model=CheckoutResponse)
def checkout(
    body: CheckoutRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
    username: str = Depends(get_current_user)
):
    if not x_idempotency_key or x_idempotency_key.strip() == "":
        raise HTTPException(status_code=400, detail="X-Idempotency-Key header is required.")
        
    try:
        uuid.UUID(x_idempotency_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Idempotency-Key is not a valid UUID.")

    db = SessionLocal()
    try:
        existing_tx = db.query(PaymentTransaction).filter(
            PaymentTransaction.idempotency_key == x_idempotency_key
        ).first()
        
        if existing_tx:
            if existing_tx.user_id != username:
                raise HTTPException(status_code=403, detail="Bu işlem anahtarı başka bir kullanıcıya ait.")
            
            if existing_tx.status == PaymentStatus.PENDING:
                plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.id == body.plan_id
                ).first()
                if not plan:
                    raise HTTPException(status_code=404, detail="Geçersiz plan seçildi.")
                
                provider = get_payment_provider()
                token = existing_tx.provider_transaction_id
                if token and token.startswith("mock_token_"):
                    tx_id = token[11:]
                else:
                    tx_id = token or f"TX_{uuid.uuid4().hex[:12].upper()}"
                
                checkout_session = provider.create_checkout_session(
                    username=username,
                    plan_name=plan.name,
                    price=float(plan.price_lira),
                    transaction_id=tx_id
                )
                
                existing_tx.provider_transaction_id = checkout_session.get("token") or tx_id
                db.commit()
                
                return CheckoutResponse(
                    checkout_url=checkout_session["checkout_url"],
                    transaction_id=tx_id,
                    status="pending"
                )
            else:
                raise HTTPException(status_code=409, detail="Bu işlem zaten tamamlanmış.")

        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == body.plan_id,
            SubscriptionPlan.is_active == True
        ).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Geçersiz plan seçildi.")

        tx_id = f"TX_{uuid.uuid4().hex[:12].upper()}"
        
        user_sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == username,
            UserSubscription.plan_id == plan.id
        ).first()
        if not user_sub:
            user_sub = UserSubscription(
                user_id=username,
                plan_id=plan.id,
                status=SubscriptionStatus.PENDING
            )
            db.add(user_sub)
            db.commit()
            db.refresh(user_sub)

        new_tx = PaymentTransaction(
            user_id=username,
            subscription_id=user_sub.id,
            provider_transaction_id=None,
            amount=plan.price_lira,
            currency="TRY",
            status=PaymentStatus.PENDING,
            idempotency_key=x_idempotency_key
        )
        db.add(new_tx)
        db.commit()
        db.refresh(new_tx)

        provider = get_payment_provider()
        try:
            checkout_session = provider.create_checkout_session(
                username=username,
                plan_name=plan.name,
                price=float(plan.price_lira),
                transaction_id=tx_id
            )
            
            new_tx.provider_transaction_id = checkout_session.get("token") or tx_id
            db.commit()
            
            return CheckoutResponse(
                checkout_url=checkout_session["checkout_url"],
                transaction_id=tx_id,
                status="pending"
            )
        except ProviderNotConfigured as e:
            db.delete(new_tx)
            db.commit()
            raise HTTPException(
                status_code=503,
                detail=f"Ödeme altyapısı henüz yapılandırılmamış. Lütfen yöneticiye başvurun. Hata: {str(e)}"
            )
    finally:
        db.close()

@app.get("/payments/history", response_model=list[PaymentHistoryItem], responses={403: {"model": AccessDeniedResponse}})
def get_payment_history(username: str = Depends(require_premium_user)):
    db = SessionLocal()
    try:
        txs = db.query(PaymentTransaction).filter(
            PaymentTransaction.user_id == username
        ).order_by(PaymentTransaction.created_at.desc()).all()
        
        return [
            PaymentHistoryItem(
                transaction_id=t.provider_transaction_id or f"TX_{t.id}",
                amount=t.amount,
                currency=t.currency,
                status=t.status.value,
                created_at=t.created_at.isoformat()
            ) for t in txs
        ]
    finally:
        db.close()

@app.post("/payments/webhook/iyzico")
async def iyzico_webhook(request: Request):
    headers = dict(request.headers)
    raw_body = await request.body()
    
    # 1. Perform signature verification
    provider = get_payment_provider()
    sig_verified = provider.verify_webhook_signature(headers, raw_body)
    
    sig_header = (
        headers.get("X-Iyzico-Signature") or
        headers.get("x-iyzico-signature") or
        headers.get("X-IYZ-SIGNATURE-V3") or
        headers.get("x-iyz-signature-v3")
    )
    has_sig = sig_header is not None
    
    # If signature is present but invalid, reject the request immediately
    if has_sig and not sig_verified:
        logger.error("WEBHOOK_VERIFY_FAILED | Webhook signature check failed. Rejecting request.")
        raise HTTPException(status_code=400, detail="Geçersiz imza doğrulanamadı.")
        
    # 2. Parse event payload and check provider validation verification status
    event_data = provider.parse_webhook_event(raw_body, signature_verified=sig_verified, has_signature=has_sig)
    
    if not event_data.get("verified", False):
        logger.error("WEBHOOK_VERIFY_FAILED | Webhook event is unverifiable (invalid signature or retrieve API validation failed).")
        raise HTTPException(status_code=400, detail="Geçersiz veya doğrulanamayan işlem.")

    idempotency_key = event_data.get("idempotency_key")
    provider_tx_id = event_data.get("provider_transaction_id")
    status_str = event_data.get("status")
    
    if not idempotency_key:
        logger.error("WEBHOOK_PARSE_ERROR | Missing idempotency_key / transaction correlation details.")
        raise HTTPException(status_code=400, detail="İşlem anahtarı bulunamadı.")

    # 3. Safeguard: block mock payments in production/staging environments
    is_mock = (
        (idempotency_key and str(idempotency_key).startswith("mock_token_")) or
        (provider_tx_id and str(provider_tx_id).startswith("mock_token_"))
    )
    if is_mock and (settings.APP_ENV in ["production", "staging"] or os.getenv("APP_ENV", "").lower() in ["production", "staging"]):
        logger.error(f"WEBHOOK_PROCESS_REJECT | Mock token received in non-dev env: {settings.APP_ENV}.")
        raise HTTPException(status_code=400, detail="Geçersiz işlem.")

    db = SessionLocal()
    try:
        tx = db.query(PaymentTransaction).filter(
            (PaymentTransaction.idempotency_key == idempotency_key) |
            (PaymentTransaction.provider_transaction_id == provider_tx_id)
        ).first()

        if not tx:
            logger.error(f"WEBHOOK_PROCESS_ERROR | Transaction not found in local DB. IdempotencyKey: {idempotency_key}")
            raise HTTPException(status_code=404, detail="Eşleşen işlem bulunamadı.")

        current_status = tx.status
        target_status = None
        if status_str == "success":
            target_status = PaymentStatus.SUCCESS
        elif status_str in ["failed", "failure"]:
            target_status = PaymentStatus.FAILED
        elif status_str == "refunded":
            target_status = PaymentStatus.REFUNDED
        elif status_str == "canceled":
            target_status = PaymentStatus.CANCELED

        if current_status == target_status:
            logger.info(f"WEBHOOK_PROCESS_DUPLICATE | Webhook status matches current transaction status: {tx.id} ({current_status}). Skipping.")
            return {"status": "already_processed"}

        # Define allowed state transitions:
        # pending -> success
        # pending -> failed
        # pending -> canceled
        # success -> refunded
        # success -> canceled
        # Others are invalid (terminal states)
        allowed = False
        if current_status == PaymentStatus.PENDING:
            if target_status in [PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.CANCELED]:
                allowed = True
        elif current_status == PaymentStatus.SUCCESS:
            if target_status in [PaymentStatus.REFUNDED, PaymentStatus.CANCELED]:
                allowed = True

        if not allowed:
            logger.warning(f"WEBHOOK_INVALID_TRANSITION | Invalid transition attempted: {current_status} -> {target_status} for transaction {tx.id}")
            raise HTTPException(status_code=400, detail="Geçersiz işlem durum geçişi.")

        # Apply state transition
        tx.status = target_status
        if provider_tx_id:
            tx.provider_transaction_id = provider_tx_id

        if target_status == PaymentStatus.SUCCESS:
            if tx.subscription_id:
                sub = db.query(UserSubscription).filter(UserSubscription.id == tx.subscription_id).first()
                if sub:
                    # Deactivate other subscriptions
                    db.query(UserSubscription).filter(
                        UserSubscription.user_id == tx.user_id,
                        UserSubscription.id != sub.id
                    ).update({"status": SubscriptionStatus.INACTIVE})
                    
                    sub.status = SubscriptionStatus.ACTIVE
                    sub.current_period_start = datetime.now(timezone.utc)
                    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
                    sub.cancel_at_period_end = False
                    sub.provider_subscription_id = f"SUB_{uuid.uuid4().hex[:12].upper()}"
            
            # Safe logging: Only log transaction_id, user_id, status, provider result code
            logger.info(
                "WEBHOOK_PROCESS | TransactionID: %s | UserID: %s | Status: SUCCESS | ProviderResultCode: %s",
                tx.provider_transaction_id, tx.user_id, status_str
            )
        elif target_status == PaymentStatus.FAILED:
            if tx.subscription_id:
                sub = db.query(UserSubscription).filter(UserSubscription.id == tx.subscription_id).first()
                if sub:
                    sub.status = SubscriptionStatus.PAYMENT_FAILED
            
            # Safe logging: Only log transaction_id, user_id, status, provider result code
            logger.warning(
                "WEBHOOK_PROCESS | TransactionID: %s | UserID: %s | Status: FAILED | ProviderResultCode: %s",
                tx.provider_transaction_id, tx.user_id, status_str
            )
        elif target_status == PaymentStatus.REFUNDED:
            if tx.subscription_id:
                sub = db.query(UserSubscription).filter(UserSubscription.id == tx.subscription_id).first()
                if sub:
                    sub.status = SubscriptionStatus.INACTIVE
                    sub.current_period_end = datetime.now(timezone.utc)
            
            # Safe logging: Only log transaction_id, user_id, status, provider result code
            logger.info(
                "WEBHOOK_PROCESS | TransactionID: %s | UserID: %s | Status: REFUNDED | ProviderResultCode: %s",
                tx.provider_transaction_id, tx.user_id, status_str
            )
        elif target_status == PaymentStatus.CANCELED:
            if tx.subscription_id:
                sub = db.query(UserSubscription).filter(UserSubscription.id == tx.subscription_id).first()
                if sub:
                    now = datetime.now(timezone.utc)
                    current_end = sub.current_period_end
                    if current_end and current_end.tzinfo is None:
                        current_end = current_end.replace(tzinfo=timezone.utc)
                    if current_end and current_end > now:
                        sub.cancel_at_period_end = True
                        sub.status = SubscriptionStatus.CANCELED
                    else:
                        sub.status = SubscriptionStatus.CANCELED
                        sub.current_period_end = now
            
            # Safe logging: Only log transaction_id, user_id, status, provider result code
            logger.info(
                "WEBHOOK_PROCESS | TransactionID: %s | UserID: %s | Status: CANCELED | ProviderResultCode: %s",
                tx.provider_transaction_id, tx.user_id, status_str
            )
            
        db.commit()
        return {"status": "processed"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"WEBHOOK_PROCESS_EXCEPTION | Exception: {e}")
        raise HTTPException(status_code=500, detail="Webhook işleme hatası.")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

