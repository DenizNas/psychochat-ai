import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from src.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_EXPIRE_MINUTES

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # bcrypt.checkpw expects bytes for both arguments
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    # bcrypt.hashpw expects bytes and returns bytes. Decode to store as string in DB.
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_token
    except JWTError:
        return None

import logging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.core.security_config import security_config
from src.core.token_blacklist import token_blacklist_core

logger = logging.getLogger(__name__)
security_jwt = HTTPBearer()

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

