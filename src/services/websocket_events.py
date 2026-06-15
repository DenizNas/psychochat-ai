"""
WebSocket Event Schemas & Validators
=====================================
Tüm WebSocket event tipleri, payload doğrulama ve
sanitize edilmiş loglama buradan yönetilir.

Güvenlik Notları:
- Raw mesaj içeriği loglanmaz (privacy-safe)
- 64KB payload sınırı uygulanır
- Bilinmeyen event tipler reddedilir
"""

import json
import logging
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_PAYLOAD_BYTES = 64 * 1024  # 64 KB — event payload sınırı


# ─── Event Type Enum ──────────────────────────────────────────────────────────
class WsEventType(str, Enum):
    """Tüm geçerli WebSocket event tipleri."""
    # Client → Server
    CHAT_MESSAGE  = "chat_message"
    TYPING_START  = "typing_start"
    TYPING_STOP   = "typing_stop"
    PING          = "ping"

    # Server → Client
    CHAT_RESPONSE    = "chat_response"
    TYPING_INDICATOR = "typing_indicator"
    PRESENCE_UPDATE  = "presence_update"
    INTERVENTION     = "intervention"
    ERROR            = "error"
    PONG             = "pong"
    CONNECTED        = "connected"


# ─── Inbound Payload Schemas ──────────────────────────────────────────────────
@dataclass
class ChatMessagePayload:
    """client → server: kullanıcı mesajı."""
    text: str
    language: str = "tr"

    def validate(self) -> Optional[str]:
        if not self.text or not isinstance(self.text, str):
            return "text alanı boş olamaz"
        if len(self.text.strip()) == 0:
            return "text alanı boş string olamaz"
        if len(self.text) > 1000:
            return "text alanı 1000 karakteri aşamaz"
        return None


@dataclass
class TypingPayload:
    """client → server: typing indicator (raw mesaj içermez)."""
    # Sadece event tipi iletilir; mesaj içeriği taşınmaz (privacy-safe)
    pass


@dataclass
class PingPayload:
    """client → server: heartbeat ping."""
    pass


# ─── Outbound Payload Builders ────────────────────────────────────────────────
def build_chat_response(
    emotion: str,
    risk: str,
    response_text: str,
    emergency_contact: Optional[str] = None,
    is_crisis: Optional[bool] = None,
    crisis_level: Optional[str] = None,
    show_emergency_support: Optional[bool] = None,
    emergency_phone: Optional[str] = None,
    emergency_title: Optional[str] = None,
    emergency_message: Optional[str] = None,
) -> dict:
    """Server-to-client chat cevabı olayı."""
    payload = {
        "emotion": emotion,
        "risk": risk,
        "response": response_text,
        "emergency_contact": emergency_contact,
    }
    if is_crisis is not None:
        payload["is_crisis"] = is_crisis
    if crisis_level is not None:
        payload["crisis_level"] = crisis_level
    if show_emergency_support is not None:
        payload["show_emergency_support"] = show_emergency_support
    if emergency_phone is not None:
        payload["emergency_phone"] = emergency_phone
    if emergency_title is not None:
        payload["emergency_title"] = emergency_title
    if emergency_message is not None:
        payload["emergency_message"] = emergency_message
        
    return {
        "type": WsEventType.CHAT_RESPONSE,
        "payload": payload,
    }


def build_typing_indicator(is_typing: bool) -> dict:
    """Server-to-client typing durumu (assistant typing)."""
    return {
        "type": WsEventType.TYPING_INDICATOR,
        "payload": {"is_typing": is_typing},
    }


def build_presence_update(user_id: str, is_online: bool) -> dict:
    """Server-to-client presence değişikliği (user_id hash'lenir)."""
    return {
        "type": WsEventType.PRESENCE_UPDATE,
        "payload": {
            "user_id": _safe_uid(user_id),
            "online": is_online,
        },
    }


def build_intervention(title: str, body: str, severity: str) -> dict:
    """Server-to-client live intervention push."""
    return {
        "type": WsEventType.INTERVENTION,
        "payload": {
            "title": title,
            "body": body,
            "severity": severity,
        },
    }


def build_error(code: str, message: str) -> dict:
    """Server-to-client hata eventi."""
    return {"type": WsEventType.ERROR, "payload": {"code": code, "message": message}}


def build_pong() -> dict:
    return {"type": WsEventType.PONG, "payload": {}}


def build_connected(user_id: str) -> dict:
    return {
        "type": WsEventType.CONNECTED,
        "payload": {"user_id": _safe_uid(user_id), "status": "connected"},
    }


# ─── Inbound Parser ───────────────────────────────────────────────────────────
class EventValidationError(Exception):
    """Geçersiz event tipi veya payload."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def parse_inbound_event(raw: str) -> tuple[WsEventType, Any]:
    """
    Ham WebSocket mesajını parse edip (type, payload) döndürür.
    Hata durumunda EventValidationError fırlatır.

    Güvenlik:
    - Raw içerik loglanmaz
    - 64KB limit dışarıda uygulanır; burada sadece içerik validate edilir
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise EventValidationError("INVALID_JSON", "Geçersiz JSON formatı")

    if not isinstance(data, dict):
        raise EventValidationError("INVALID_SHAPE", "Event bir JSON object olmalı")

    raw_type = data.get("type")
    if not raw_type:
        raise EventValidationError("MISSING_TYPE", "'type' alanı zorunlu")

    try:
        event_type = WsEventType(raw_type)
    except ValueError:
        # Bilinmeyen event tipi — loglama yaparken tipin kendisini log'a yazmak güvenli
        logger.warning("Bilinmeyen WebSocket event tipi alındı: %s", raw_type)
        raise EventValidationError("UNKNOWN_TYPE", f"Bilinmeyen event tipi: {raw_type}")

    payload_raw = data.get("payload", {})

    # İzin verilen inbound event tipleri kontrolü
    allowed_inbound = {WsEventType.CHAT_MESSAGE, WsEventType.TYPING_START, WsEventType.TYPING_STOP, WsEventType.PING}
    if event_type not in allowed_inbound:
        raise EventValidationError("FORBIDDEN_TYPE", f"Bu event client'tan gönderilemez: {event_type}")

    # Payload parse
    if event_type == WsEventType.CHAT_MESSAGE:
        if not isinstance(payload_raw, dict):
            raise EventValidationError("INVALID_PAYLOAD", "chat_message payload bir object olmalı")
        payload = ChatMessagePayload(
            text=str(payload_raw.get("text", "")),
            language=str(payload_raw.get("language", "tr")),
        )
        err = payload.validate()
        if err:
            raise EventValidationError("INVALID_PAYLOAD", err)
        return event_type, payload

    elif event_type in (WsEventType.TYPING_START, WsEventType.TYPING_STOP):
        # Typing event payload taşımamalı — raw içeriği yok sayıyoruz (privacy-safe)
        return event_type, TypingPayload()

    elif event_type == WsEventType.PING:
        return event_type, PingPayload()

    # Buraya ulaşılmamalı
    raise EventValidationError("INTERNAL", "Beklenmedik parse durumu")


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _safe_uid(user_id: str) -> str:
    """user_id'yi log/payload'a yazılabilir kısa hash'e dönüştürür."""
    import hashlib
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


def encode_event(event: dict) -> str:
    """Dict'i JSON string'e encode eder."""
    return json.dumps(event, ensure_ascii=False)
