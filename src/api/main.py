from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
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
from datetime import datetime

# 1. Merkezi Güvenlik Ayarlarını İçe Aktar
from src.core.security_config import security_config

from src.core.metrics import metrics_tracker
from src.core.brute_force_protection import brute_force_protector
from src.core.token_blacklist import token_blacklist_core
from src.core.input_validator import input_validator_core
from src.ai.preprocessing import prepare_model_input
from src.core.logging_config import setup_logging
import logging
logger = logging.getLogger(__name__)
from src.core.middlewares import RequestLoggingMiddleware
from src.core.exceptions import custom_http_exception_handler, validation_exception_handler, global_exception_handler
from fastapi.exceptions import RequestValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.inference.predict import EmotionCrisisPredictor
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput
from src.services.logger import log_interaction
from src.services.database import init_db, get_chat_history, get_analytics_summary, get_analytics_timeline
from src.services.database import create_user, get_user_by_username
from src.services.auth import verify_password, get_password_hash, create_access_token, decode_access_token

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Psikochat-AI API",
    description="Empatik ve Krize Duyarlı Yapay Zeka Destek Asistanı",
    version="1.1.0",
    default_response_class=ORJSONResponse
)

app.state.limiter = limiter

# Request Logging Middleware Entegrasyonu
app.add_middleware(RequestLoggingMiddleware)

# Exception Handler Kayıt İşlemleri
app.add_exception_handler(HTTPException, custom_http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

predictor = None

## Security schemes
security_jwt = HTTPBearer()
security_basic = HTTPBasic()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_jwt)) -> str:
    token = credentials.credentials
    
    # 1. Blacklist Zırhı (Config üzerinden yönetilir)
    if security_config.TOKEN_BLACKLIST_ENABLED:
        if token_blacklist_core.is_blacklisted(token):
            logger.error(f"Blacklisted token reuse attempt! Token signature: {token[:15]}...")
            raise HTTPException(status_code=401, detail="Oturumunuz kapatılmış. Lütfen tekrar giriş yapın.")
    
    # 2. Native Validation
    payload = decode_access_token(token)
    if not payload:
        logger.warning(f"Invalid token use attempt! Token signature: {token[:15]}...")
        raise HTTPException(status_code=401, detail="Geçersiz token.")
    
    username = payload.get("sub")
    if not username:
        logger.warning("Token parsed but missing 'sub' identifier.")
        raise HTTPException(status_code=401, detail="Token hatası.")
    return username

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
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    text: str
    language: Optional[str] = "tr"

class ChatResponse(BaseModel):
    emotion: str
    risk: str
    response: str
    emergency_contact: Optional[str] = None

@app.on_event("startup")
def load_models():
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
        if os.getenv("APP_ENV", "development").lower() == "production":
            logger.critical(f"FATAL STARTUP ERROR: Modeller yuklenemedi. Detay: {str(e)}")
            print(f"FATAL STARTUP ERROR: Modeller yuklenemedi. Detay: {str(e)}")
            sys.exit(1)
        else:
            logger.critical(f"STARTUP WARNING: Modeller yuklenemedi. Inference disabled. Detay: {str(e)}")
            print(f"STARTUP WARNING: Modeller yuklenemedi. Inference disabled. Detay: {str(e)}")

@app.get("/")
def read_root():
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Kök (root) endpoint '/' çağrıldı.")
    return {"status": "ok", "message": "Psikochat-AI API Çalışıyor. /predict uç noktasını kullanın."}

## Auth Endpoints
@app.post("/register", status_code=201)
def register(user: RegisterRequest):
    if not user.username or not user.password:
        raise HTTPException(status_code=400, detail="Kullanıcı adı ve şifre gereklidir.")
    
    if len(user.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Şifre çok uzun (maksimum 72 byte olmalıdır).")
    
    hashed = get_password_hash(user.password)
    
    try:
        # API ve DB artık 'username' bazlı çalışıyor
        success = create_user(user.username, hashed)
        if not success:
            raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten alınmış.")
        
        return {"message": "Kayıt başarılı, giriş yapabilirsiniz."}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Register Exception: {e}")
        raise HTTPException(status_code=500, detail=f"Sunucu hatası oluştu: {str(e)}")

@app.post("/login")
def login(request: Request, user: LoginRequest):
    client_ip = request.client.host if request.client else "unknown_ip"
    
    # Blokaj kontrolü
    if brute_force_protector.is_blocked(client_ip):
        logger.error(f"Brute-force block active | IP: {client_ip}")
        raise HTTPException(
            status_code=429, 
            detail="Çok fazla başarısız giriş denemesi. Lütfen 5 dakika sonra tekrar deneyin."
        )

    # Başarısız Senaryo Kontrolleri
    def _handle_failure(reason: str):
        brute_force_protector.register_failure(client_ip)
        logger.warning(f"Failed login attempt | IP: {client_ip} | Reason: {reason}")
        raise HTTPException(status_code=400, detail="Geçersiz e-posta veya şifre.")

    if not user.username or not user.password:
        _handle_failure("Missing fields")
    
    if len(user.password.encode("utf-8")) > 72:
        _handle_failure("Password string limits exceeded")

    # API ve DB artık 'username' bazlı çalışıyor
    db_user = get_user_by_username(user.username)
    if not db_user:
        _handle_failure("User not found in DB")
    
    if not verify_password(user.password, db_user["password_hash"]):
        _handle_failure("Incorrect password")
    
    # Başarılı Giriş Senaryosu
    if brute_force_protector.register_success(client_ip):
        logger.info(f"Successful login for previously failing IP: {client_ip}")
        
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "username": user.username}

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
         emotion_label = analysis["emotion"]["label"]
         risk_label = analysis["crisis_detection"]["label"]

    emergency_msg = None
    if str(risk_label).lower() in ["kriz", "1", "crisis"]:
        emergency_msg = "Lütfen acil yardıma ihtiyacınız varsa 112'yi veya 114 Psikolojik Destek Hattını arayın."

    engine_input = EngineInput(
        text=user_text,
        emotion=emotion_label,
        risk=risk_label,
        user_id=username,
        language=body.language
    )
    engine_output = response_engine.generate_response(engine_input)
    chatgpt_response = engine_output.final_text

    latency = (time.time() - start_time) * 1000

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
    
    db_status = True
    try:
        # engine is defined in database.py
        with db.engine.connect() as conn:
            pass
    except Exception:
        db_status = False
        
    model_status = predictor is not None
    status = "ok" if db_status and model_status else "error"
    
    return {
        "status": status,
        "database": db_status,
        "models": model_status,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/metrics")
def get_metrics():
    return metrics_tracker.get_snapshot()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
