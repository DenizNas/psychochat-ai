"""
memory_manager.py — Faz 5 Prompt 5
Privacy-Safe, User-Aware Memory Manager

Flow:
    User Input → Preprocessing → Emotion + Crisis
    → Context Builder → [Memory Lookup HERE]
    → Response Engine → Safety Layer → Formatter → Final Response

Memory Types:
    user_preferences      — response style, topic preferences
    recurring_emotions    — emotional patterns over time
    important_topics      — recurring life themes (work, family, exams...)
    coping_strategies     — techniques that help the user
    support_preferences   — how the user likes to be supported

Privacy Rules (STRICT):
    ✅ Recordable: patterns, preferences, coping strategies, recurring themes
    ❌ NOT recorded: PII (name, address, phone), raw crisis sentences,
                     self-harm methods, identity data, overly personal details

Design Constraints:
    - Crisis safety ALWAYS takes priority over memory injection
    - Raw sensitive data NEVER written to memory
    - Memory injection is SHORT and CONTROLLED (no context window bloat)
    - UTF-8 safe throughout (NFC normalization)
    - Runtime latency: O(n) where n = number of memories (<100ms target)
    - Extensible for future persistent storage (DB, Redis, etc.)
"""

import logging
import unicodedata
import re
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEMORY_TYPES = {
    "user_preferences",
    "recurring_emotions",
    "important_topics",
    "coping_strategies",
    "support_preferences",
}

# Absolute maximum number of memories stored per user (prevents unbounded growth)
MAX_MEMORIES_PER_USER = 50

# Max memories injected into a single GPT prompt
MAX_INJECTED_MEMORIES = 5

# Max characters for a single memory content field
MAX_MEMORY_CONTENT_CHARS = 200

# Max total characters contributed by memory injection to prompt
MAX_INJECTION_TOTAL_CHARS = 600

# Privacy guard: patterns that MUST NOT be stored verbatim
# These prevent raw crisis content, PII, and sensitive data from entering memory
_PRIVACY_BLOCK_PATTERNS = [
    r"\d{10,11}",                             # phone numbers (10-11 digit runs)
    r"\b\d{2}[\s./]\d{2}[\s./]\d{4}\b",      # dates as identity (DD/MM/YYYY)
    r"tc\s*kimlik",                            # Turkish national ID
    r"kimlik\s*no",
    r"pasaport\s*no",
    r"adres[im]?[\s:]+\w",                    # address fragments
    r"sokak|mahalle|ilçe|posta\s*kodu",       # address components
    r"kendim[ie]\s*zarar",                    # raw self-harm statements
    r"intihar\s*et",                          # raw suicide statements
    r"kendimi\s*öldür",
    r"hayatıma\s*son",
    r"yaşamak\s*istemiyorum",
    r"bıçak\s*kes",
    r"hap\s*iç",
    r"zehir\s*iç",
]

_PRIVACY_RE = re.compile(
    "|".join(_PRIVACY_BLOCK_PATTERNS),
    flags=re.IGNORECASE | re.UNICODE,
)

# Extraction patterns: what TO extract from user messages
# Each entry: (memory_type, regex_pattern, extraction_template)
_EXTRACTION_RULES: List[tuple] = [
    # Coping strategies
    (
        "coping_strategies",
        r"(nefes egzersiz|meditasyon|spor|yürüyüş|müzik|okumak|uyumak|dinlenmek)\s*(bana|iyi|işe yarıyor|yardımcı)",
        "Kullanıcı başa çıkma yöntemi olarak şunları ifade etti: {match}",
    ),
    # User preferences (response style)
    (
        "user_preferences",
        r"(kısa|uzun|net|detaylı|sade)\s*(cevap|yanıt|açıklama)\s*(istiyorum|tercih ediyorum|daha iyi|bana iyi geliyor)",
        "Kullanıcı yanıt tercihi: {match}",
    ),
    # Recurring topics: family
    (
        "important_topics",
        r"(aile|annem|babam|kardeşim|eşim|partnerim)\s*(beni|çok|sık|her zaman|sürekli)",
        "Aile konuları kullanıcı için tekrarlayan bir tema.",
    ),
    # Recurring topics: work/school stress
    (
        "important_topics",
        r"(sınav|iş|okul|kariyer|proje|toplantı)\s*(dönem|stres|baskı|bunaltıyor|zor geliyor)",
        "İş/okul stresi kullanıcı için tekrarlayan bir tema.",
    ),
    # Support preferences
    (
        "support_preferences",
        r"(sadece\s*(dinlenmek|anlaşılmak)|yargılanmadan|beni\s*anla|tavsiye\s*(istemiyorum|değil))",
        "Kullanıcı destek tercihi: dinlenmek ve anlaşılmak istiyor, tavsiye istemeyebilir.",
    ),
]


# ---------------------------------------------------------------------------
# Memory Schema (MemoryRecord)
# ---------------------------------------------------------------------------

class MemoryRecord:
    """
    A single memory entry with full metadata.

    Attributes:
        user_id        : Who this memory belongs to
        memory_type    : Category (see MEMORY_TYPES)
        content        : Privacy-sanitized content string (UTF-8 safe)
        created_at     : ISO 8601 UTC timestamp
        updated_at     : ISO 8601 UTC timestamp (updated on refresh)
        confidence     : Float 0.0–1.0 (extraction certainty)
        source         : How the memory was created ('auto_extraction' | 'explicit')
    """

    __slots__ = (
        "user_id", "memory_type", "content",
        "created_at", "updated_at", "confidence", "source"
    )

    def __init__(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        confidence: float = 0.7,
        source: str = "auto_extraction",
    ):
        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"Invalid memory_type: {memory_type!r}. Must be one of {MEMORY_TYPES}")

        now = datetime.now(timezone.utc).isoformat()
        self.user_id = user_id
        self.memory_type = memory_type
        self.content = _sanitize_content(content)
        self.created_at = now
        self.updated_at = now
        self.confidence = max(0.0, min(1.0, confidence))
        self.source = source

    def refresh(self, new_content: Optional[str] = None, confidence_boost: float = 0.05):
        """Update timestamp and optionally boost confidence on repeat observation."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if new_content:
            self.content = _sanitize_content(new_content)
        self.confidence = min(1.0, self.confidence + confidence_boost)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confidence": self.confidence,
            "source": self.source,
        }

    def __repr__(self) -> str:
        return (
            f"MemoryRecord(type={self.memory_type!r}, "
            f"confidence={self.confidence:.2f}, content={self.content[:60]!r})"
        )


# ---------------------------------------------------------------------------
# Privacy Utilities
# ---------------------------------------------------------------------------

def _nfc(text: str) -> str:
    """NFC normalize + strip for UTF-8 safety."""
    return unicodedata.normalize("NFC", text).strip()


def _sanitize_content(content: str) -> str:
    """
    Normalize and enforce content length. Does NOT redact privacy—
    that is done by _is_privacy_safe() before calling this.
    """
    content = _nfc(content)
    if len(content) > MAX_MEMORY_CONTENT_CHARS:
        content = content[: MAX_MEMORY_CONTENT_CHARS - 1] + "…"
    return content


def _is_privacy_safe(text: str) -> bool:
    """
    Returns True if text is SAFE to store in memory.
    Blocks: PII, raw crisis statements, self-harm details, phone, address.
    """
    if _PRIVACY_RE.search(text):
        return False
    return True


def _is_crisis_content(risk: str) -> bool:
    """Checks whether the current turn is a crisis turn."""
    return risk.strip().lower() in {"1", "crisis", "kriz"}


# ---------------------------------------------------------------------------
# In-Memory Store (Thread-safe via per-user list; extend with Redis/DB later)
# ---------------------------------------------------------------------------

# { user_id: List[MemoryRecord] }
_memory_store: Dict[str, List[MemoryRecord]] = {}

# Lock for thread-safe access to _memory_store under concurrent FastAPI workers.
# Granularity: global (not per-user) — acceptable for ≤50 memories/user workload.
_store_lock = threading.Lock()


def _get_user_memories(user_id: str) -> List[MemoryRecord]:
    return _memory_store.get(user_id, [])


def _deduplicate_and_trim(user_id: str):
    """
    Remove memories with identical (memory_type, content) pairs.
    Trim to MAX_MEMORIES_PER_USER by dropping lowest-confidence entries.
    Called after every write to keep the store lean.
    Must be called while _store_lock is held by the caller.
    """
    memories = _memory_store.get(user_id, [])
    seen: set = set()
    deduped: List[MemoryRecord] = []
    for m in memories:
        key = (m.memory_type, m.content)
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if len(deduped) > MAX_MEMORIES_PER_USER:
        deduped.sort(key=lambda m: (m.confidence, m.updated_at), reverse=True)
        deduped = deduped[:MAX_MEMORIES_PER_USER]

    _memory_store[user_id] = deduped


# ---------------------------------------------------------------------------
# Memory Extraction (Auto-extraction from user input)
# ---------------------------------------------------------------------------

def extract_and_store_memories(
    user_id: str,
    text: str,
    emotion: str,
    risk: str,
) -> Dict[str, Any]:
    """
    Analyses user text and stores extracted insights as memory records.

    Privacy Rules Enforced:
        - Crisis turns: NO extraction (crisis content must NEVER enter memory raw)
        - PII / harmful patterns: blocked by _is_privacy_safe()
        - Only pattern-matched, semantically abstract content is stored

    Returns:
        Extraction metadata dict for structured logging.
    """
    extracted_count = 0

    # ── RULE 1: Never extract during crisis turns ─────────────────────────
    if _is_crisis_content(risk):
        logger.info(
            "MEMORY_EXTRACT | UserID: %s | SKIPPED (crisis turn) | Risk: %s",
            user_id, risk,
        )
        return {
            "memory_count": len(_get_user_memories(user_id)),
            "extracted_count": 0,
            "skipped_reason": "crisis_turn",
            "memory_injected": False,
        }

    normalized_text = _nfc(text)

    for memory_type, pattern, template in _EXTRACTION_RULES:
        match = re.search(pattern, normalized_text, flags=re.IGNORECASE | re.UNICODE)
        if not match:
            continue

        matched_span = match.group(0)
        content = template.replace("{match}", matched_span)

        # ── RULE 2: Privacy safety gate ───────────────────────────────────
        if not _is_privacy_safe(content):
            logger.info(
                "MEMORY_EXTRACT | UserID: %s | BLOCKED (privacy gate) | Type: %s",
                user_id, memory_type,
            )
            continue

        # ── Check for existing same-type memory (refresh vs. insert) ─────
        existing_memories = _get_user_memories(user_id)
        existing = next(
            (m for m in existing_memories if m.memory_type == memory_type and m.content == _sanitize_content(content)),
            None,
        )

        if existing:
            existing.refresh(confidence_boost=0.05)
        else:
            record = MemoryRecord(
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                confidence=0.7,
                source="auto_extraction",
            )
            with _store_lock:
                if user_id not in _memory_store:
                    _memory_store[user_id] = []
                _memory_store[user_id].append(record)
            extracted_count += 1

    # ── Recurring emotion tracking (separate from text pattern matching) ──
    if emotion and emotion.lower() not in {"neutral", "normal", "nötr"}:
        emotion_content = f"Kullanıcı sık sık '{emotion}' duygusu bildirdi."
        if _is_privacy_safe(emotion_content):
            existing_memories = _get_user_memories(user_id)
            existing_emo = next(
                (m for m in existing_memories if m.memory_type == "recurring_emotions" and emotion.lower() in m.content.lower()),
                None,
            )
            if existing_emo:
                existing_emo.refresh(confidence_boost=0.1)
            else:
                record = MemoryRecord(
                    user_id=user_id,
                    memory_type="recurring_emotions",
                    content=emotion_content,
                    confidence=0.6,
                    source="auto_extraction",
                )
                with _store_lock:
                    if user_id not in _memory_store:
                        _memory_store[user_id] = []
                    _memory_store[user_id].append(record)
                extracted_count += 1

    with _store_lock:
        _deduplicate_and_trim(user_id)

    total_count = len(_get_user_memories(user_id))
    logger.info(
        "MEMORY_EXTRACT | UserID: %s | Extracted: %d | TotalStored: %d",
        user_id, extracted_count, total_count,
    )

    return {
        "memory_count": total_count,
        "extracted_count": extracted_count,
        "skipped_reason": None,
        "memory_injected": False,
    }


# ---------------------------------------------------------------------------
# Memory Lookup (Relevance-ranked retrieval)
# ---------------------------------------------------------------------------

def lookup_relevant_memories(
    user_id: str,
    emotion: str,
    risk: str,
    text: str = "",
) -> List[MemoryRecord]:
    """
    Retrieves relevant memories for the current turn.

    Priority order:
        1. support_preferences  (always most relevant)
        2. user_preferences     (affects response style)
        3. coping_strategies    (if emotional turn)
        4. recurring_emotions   (if matching current emotion)
        5. important_topics     (lowest priority)

    Crisis rule: never inject memories in crisis turns — safety layer takes over.

    Returns up to MAX_INJECTED_MEMORIES records.
    """
    # ── RULE: Never inject memories in crisis turns ────────────────────────
    if _is_crisis_content(risk):
        return []

    memories = _get_user_memories(user_id)
    if not memories:
        return []

    # Score each memory by type priority + confidence
    PRIORITY = {
        "support_preferences": 5,
        "user_preferences": 4,
        "coping_strategies": 3,
        "recurring_emotions": 2,
        "important_topics": 1,
    }

    current_emotion_lower = emotion.lower()

    def _score(m: MemoryRecord) -> float:
        priority_score = PRIORITY.get(m.memory_type, 0)
        confidence_score = m.confidence

        # Boost recurring_emotions if it matches current emotion
        emotion_boost = 0.0
        if m.memory_type == "recurring_emotions" and current_emotion_lower in m.content.lower():
            emotion_boost = 1.0

        # Boost if text keyword matches memory content
        text_boost = 0.0
        if text and any(
            word in m.content.lower()
            for word in _nfc(text).lower().split()
            if len(word) > 3
        ):
            text_boost = 0.5

        return priority_score + confidence_score + emotion_boost + text_boost

    scored = sorted(memories, key=_score, reverse=True)
    return scored[:MAX_INJECTED_MEMORIES]


# ---------------------------------------------------------------------------
# Memory Injection (Build prompt fragment)
# ---------------------------------------------------------------------------

def build_memory_injection(memories: List[MemoryRecord]) -> str:
    """
    Constructs a concise, controlled memory context block to prepend to
    the system or user prompt. Enforces MAX_INJECTION_TOTAL_CHARS limit.

    Returns empty string if no memories or if total budget exceeded.
    """
    if not memories:
        return ""

    lines: List[str] = ["[KULLANICI HAFIZASI — Kısa Bağlam]:"]
    total_chars = len(lines[0])

    for m in memories:
        line = f"• [{m.memory_type}] {m.content}"
        if total_chars + len(line) > MAX_INJECTION_TOTAL_CHARS:
            break
        lines.append(line)
        total_chars += len(line)

    if len(lines) == 1:
        # Only the header, no memories fit — return empty
        return ""

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API: Full Memory Pipeline Call
# ---------------------------------------------------------------------------

def process_memory(
    user_id: str,
    text: str,
    emotion: str,
    risk: str,
) -> Dict[str, Any]:
    """
    Main entry point called by the Response Engine.

    1. Extracts and stores new memories from the current turn
    2. Looks up relevant memories for injection
    3. Builds the injection string
    4. Returns metadata for structured logging

    Args:
        user_id:  Authenticated user identifier
        text:     Privacy-sanitized user input (already cleaned by input_validator)
        emotion:  Detected emotion label
        risk:     Detected crisis risk label

    Returns:
        {
            "injection_text":         str (empty if nothing relevant or crisis turn),
            "memory_count":           int (total stored memories for user),
            "selected_memory_count":  int (how many were selected for injection),
            "memory_injected":        bool,
        }
    """
    # Step 1: Extract
    extract_meta = extract_and_store_memories(user_id, text, emotion, risk)

    # Step 2: Lookup relevant
    relevant = lookup_relevant_memories(user_id, emotion, risk, text)
    selected_count = len(relevant)

    # Step 3: Build injection text
    injection_text = build_memory_injection(relevant)
    memory_injected = bool(injection_text)

    # Step 4: Structured log
    logger.info(
        "MEMORY_LOG | UserID: %s | memory_count: %d | selected_memory_count: %d | memory_injected: %s",
        user_id,
        extract_meta["memory_count"],
        selected_count,
        memory_injected,
    )

    return {
        "injection_text": injection_text,
        "memory_count": extract_meta["memory_count"],
        "selected_memory_count": selected_count,
        "memory_injected": memory_injected,
    }


# ---------------------------------------------------------------------------
# Memory Management (Future-extensible)
# ---------------------------------------------------------------------------

def clear_user_memory(user_id: str) -> int:
    """
    Deletes all memory records for a user.
    Returns the number of records deleted.
    (Extensible: replace with DB DELETE when persistent store is added.)
    """
    count = len(_memory_store.pop(user_id, []))
    logger.info("MEMORY_CLEAR | UserID: %s | Deleted: %d records", user_id, count)
    return count


def get_user_memory_summary(user_id: str) -> Dict[str, Any]:
    """
    Returns a privacy-safe summary of stored memories for a user.
    Excludes raw content — only counts per type and confidence stats.
    (Extensible: use for /memory/status API endpoint later.)
    """
    memories = _get_user_memories(user_id)
    by_type: Dict[str, int] = {t: 0 for t in MEMORY_TYPES}
    for m in memories:
        by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1

    avg_confidence = (
        round(sum(m.confidence for m in memories) / len(memories), 3)
        if memories else 0.0
    )

    return {
        "user_id": user_id,
        "total_memories": len(memories),
        "by_type": by_type,
        "avg_confidence": avg_confidence,
    }
