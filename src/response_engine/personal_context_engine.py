"""
personal_context_engine.py — Faz 10 Prompt 2
Advanced AI Memory & Personal Context Engine

Mevcut memory_manager.py'ye EK olarak çalışır (backward-compatible).
engine.py bu modülü primary olarak kullanır.

Mimari:
    User Turn
        ├── privacy_mode=True  → tümü devre dışı
        ├── risk=crisis        → extraction ve injection devre dışı
        ├── extract()          → 8 tip, safety gate, consolidation
        ├── retrieve()         → multi-factor hybrid scoring
        └── inject()           → max 600 char, sensitivity filtresi

Memory Types (8):
    preference, recurring_stressor, coping_strategy,
    important_person, routine, goal, boundary, wellness_pattern

Scoring (çok faktörlü):
    score = recency(0.30) + confidence(0.25) + relevance(0.25)
          + importance(0.15) + sensitivity_penalty(0.05)

Privacy/Crisis Garantileri:
    - privacy_mode → sıfır extraction, sıfır injection
    - crisis/risk  → sıfır extraction, sıfır injection
    - sensitivity=high → hiçbir zaman prompt'a inject edilmez
    - raw user text, PII, self-harm, teşhis loglanmaz
    - max injection 600 karakter

Decay (lazy evaluation):
    retrieved_at sırasında hesaplanır, DB'ye yansıtılır.
    days_since_reinforced > 30 → decay agresif
    Her erişimde DB'ye yazılmaz; sadece retrieval skoru etkiler.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.services.database import (
    create_memory,
    get_active_memories_for_user,
    delete_memory_for_user,
    refresh_memory_reinforcement,
    update_memory_decay,
    cleanup_old_memories,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEMORY_TYPES = {
    "preference",
    "recurring_stressor",
    "coping_strategy",
    "important_person",
    "routine",
    "goal",
    "boundary",
    "wellness_pattern",
}

# Legacy types mapped to new types for backward compat
_LEGACY_TYPE_MAP = {
    "user_preferences":    "preference",
    "recurring_emotions":  "wellness_pattern",
    "important_topics":    "recurring_stressor",
    "coping_strategies":   "coping_strategy",
    "support_preferences": "boundary",
}

# Sensitivity levels
SENSITIVITY_LOW    = "low"
SENSITIVITY_MEDIUM = "medium"
SENSITIVITY_HIGH   = "high"

# Injection / storage limits
MAX_MEMORY_CONTENT_CHARS = 250
MAX_INJECTION_TOTAL_CHARS = 600
MAX_MEMORIES_PER_USER     = 60
MAX_INJECTED_MEMORIES     = 6
MIN_CONFIDENCE_THRESHOLD  = 0.35  # below this, memory is not injected

# Scoring weights (must sum to 1.0)
_W_RECENCY      = 0.30
_W_CONFIDENCE   = 0.25
_W_RELEVANCE    = 0.25
_W_IMPORTANCE   = 0.15
_W_SENSITIVITY  = 0.05  # penalty deducted for high sensitivity

# Importance ranking per type (higher = more important to inject)
_TYPE_IMPORTANCE = {
    "boundary":           5,
    "coping_strategy":    4,
    "goal":               4,
    "preference":         3,
    "recurring_stressor": 3,
    "important_person":   2,
    "wellness_pattern":   2,
    "routine":            1,
}

# Decay half-life in days
_DECAY_HALF_LIFE_DAYS = 30.0

# ---------------------------------------------------------------------------
# Privacy Safety Gate
# ---------------------------------------------------------------------------

_PRIVACY_BLOCK_PATTERNS = [
    # PII
    r"\d{10,11}",                             # phone numbers
    r"\b\d{2}[\s./]\d{2}[\s./]\d{4}\b",      # dates as identity
    r"tc\s*kimlik",
    r"kimlik\s*no",
    r"pasaport\s*no",
    r"adres[im]?[\s:]+\w",
    r"sokak|mahalle|ilçe|posta\s*kodu",
    r"e.?posta\s*adresi",
    # Self-harm / crisis (must never enter memory)
    r"kendim[ie]\s*zarar",
    r"intihar\s*et",
    r"kendimi\s*öldür",
    r"hayatıma\s*son",
    r"yaşamak\s*istemiyorum",
    r"bıçak\s*kes",
    r"hap\s*iç",
    r"zehir\s*iç",
    r"kendime\s*zarar",
    # Medical diagnoses (exact clinical terms stored verbatim is sensitive)
    r"tanı\s*aldım",
    r"bipolar\s*(bozukluk|tanısı)",
    r"şizofreni",
    r"major\s*depresyon\s*tanısı",
    r"borderline\s*kişilik",
    # Secrets / credentials (prompt injection vector)
    r"api\s*key",
    r"secret\s*key",
    r"password|şifre\s*şu",
    r"token\s*değerim",
]

_PRIVACY_RE = re.compile(
    "|".join(_PRIVACY_BLOCK_PATTERNS),
    flags=re.IGNORECASE | re.UNICODE,
)

# High-sensitivity keywords → classify as medium/high if matched
_HIGH_SENSITIVITY_KEYWORDS = re.compile(
    r"(intihar|kriz|kendine zarar|ölmek istiyorum|bipolar|şizofreni|tanı)",
    flags=re.IGNORECASE | re.UNICODE,
)

_MEDIUM_SENSITIVITY_KEYWORDS = re.compile(
    r"(kaygı|panik|depresyon|ayrılık|boşanma|kayıp|yalnızlık|yas|travma)",
    flags=re.IGNORECASE | re.UNICODE,
)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def _is_privacy_safe(text: str) -> bool:
    """Returns True if text is safe to store in memory (no PII or harmful content)."""
    return not bool(_PRIVACY_RE.search(text))


def _classify_sensitivity(content: str) -> str:
    """Classifies a memory content's sensitivity level."""
    if _HIGH_SENSITIVITY_KEYWORDS.search(content):
        return SENSITIVITY_HIGH
    if _MEDIUM_SENSITIVITY_KEYWORDS.search(content):
        return SENSITIVITY_MEDIUM
    return SENSITIVITY_LOW


def _is_crisis(risk: str) -> bool:
    return risk.strip().lower() in {"1", "crisis", "kriz"}


def _sanitize(content: str) -> str:
    content = _nfc(content)
    if len(content) > MAX_MEMORY_CONTENT_CHARS:
        content = content[:MAX_MEMORY_CONTENT_CHARS - 1] + "…"
    return content


# ---------------------------------------------------------------------------
# Extraction Rules (Pattern → Memory)
# ---------------------------------------------------------------------------

# Each rule: (memory_type, sensitivity, regex, template, confidence)
_EXTRACTION_RULES: List[Tuple[str, str, str, str, float]] = [
    # Coping strategies
    (
        "coping_strategy", SENSITIVITY_LOW,
        r"(nefes egzersiz|meditasyon|spor|yürüyüş|müzik|okumak|uyumak|dinlenmek|nefes al)"
        r"\s*(bana|iyi|işe yarıyor|yardımcı|geliyor)",
        "Kullanıcının işe yarayan bir başa çıkma yöntemi: {match}",
        0.75,
    ),
    # Preferences (response style)
    (
        "preference", SENSITIVITY_LOW,
        r"(kısa|uzun|net|detaylı|sade|basit)\s*(cevap|yanıt|açıklama)"
        r"\s*(istiyorum|tercih ediyorum|daha iyi|bana iyi geliyor)",
        "Kullanıcı yanıt tercihi: {match}",
        0.80,
    ),
    # Boundaries
    (
        "boundary", SENSITIVITY_LOW,
        r"(sadece\s*(dinlenmek|anlaşılmak)|yargılanmadan|beni\s*anla"
        r"|tavsiye\s*(istemiyorum|değil)|çözüm\s*değil\s*dinle)",
        "Kullanıcı destek sınırı: dinlenmek ve anlaşılmak istiyor, tavsiye istemeyebilir.",
        0.82,
    ),
    # Recurring stressors — family
    (
        "recurring_stressor", SENSITIVITY_LOW,
        r"(aile|annem|babam|kardeşim|eşim|partnerim)\s*(beni|çok|sık|her zaman|sürekli|stres)",
        "Aile dinamikleri tekrarlayan bir stres kaynağı olarak gözlemlendi.",
        0.65,
    ),
    # Recurring stressors — work/school
    (
        "recurring_stressor", SENSITIVITY_LOW,
        r"(sınav|iş|okul|kariyer|proje|toplantı)\s*(dönem|stres|baskı|bunaltıyor|zor geliyor|eziyorum)",
        "İş/okul stresi tekrarlayan bir tema.",
        0.65,
    ),
    # Goals
    (
        "goal", SENSITIVITY_LOW,
        r"(hedefim|amacım|istiyorum|planım|yapmak istiyorum|olmak istiyorum)\s+\w{4,}",
        "Kullanıcı bir hedef veya istek ifade etti: {match}",
        0.60,
    ),
    # Routines
    (
        "routine", SENSITIVITY_LOW,
        r"(her sabah|her akşam|günlük rutinm|alışkanlığım|her gün)\s*(yapıyorum|yapıyorum|var)",
        "Kullanıcının bir rutini gözlemlendi: {match}",
        0.60,
    ),
    # Important people
    (
        "important_person", SENSITIVITY_LOW,
        r"(en iyi arkadaşım|yakın arkadaşım|hocam|terapistim|danışmanım|mentorim)\s*\w*",
        "Kullanıcı için önemli bir kişi: {match}",
        0.55,
    ),
    # Wellness patterns
    (
        "wellness_pattern", SENSITIVITY_LOW,
        r"(hafta sonu|sabahları|akşamları|doğada|yalnız kaldığımda)\s*(daha iyi|rahatlarım|iyi geliyor|hissediyorum)",
        "Kullanıcının bir refah örüntüsü: {match}",
        0.65,
    ),
]


# ---------------------------------------------------------------------------
# Decay Calculator (lazy evaluation)
# ---------------------------------------------------------------------------

def _compute_decay(last_reinforced_at: Optional[str], created_at: Optional[str]) -> float:
    """Computes lazy decay score based on days since last reinforcement.

    Uses exponential decay: score = exp(-ln2 * days / half_life)
    Fresh memory (0 days) = 1.0
    After half_life days = 0.5
    After 2*half_life days ≈ 0.25

    Returns value in [0.01, 1.0].
    """
    try:
        reference_str = last_reinforced_at or created_at
        if not reference_str:
            return 1.0
        # Handle both naive and timezone-aware
        reference_str = reference_str.replace("Z", "+00:00")
        ref_dt = datetime.fromisoformat(reference_str)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)
        days_elapsed = (datetime.now(timezone.utc) - ref_dt).total_seconds() / 86400.0
        decay = math.exp(-math.log(2) * days_elapsed / _DECAY_HALF_LIFE_DAYS)
        return max(0.01, min(1.0, decay))
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Consolidation (Duplicate Merge & Contradiction)
# ---------------------------------------------------------------------------

def _text_similarity(a: str, b: str) -> float:
    """Simple token-overlap based similarity (no external libs)."""
    tokens_a = set(_nfc(a).lower().split())
    tokens_b = set(_nfc(b).lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)  # Jaccard


def _find_duplicate(
    candidate_content: str,
    candidate_type: str,
    existing_memories: List[Dict],
    threshold: float = 0.75,
) -> Optional[Dict]:
    """Finds an existing memory that is likely a duplicate (same type + high similarity).

    Returns the existing record dict, or None.
    """
    for mem in existing_memories:
        if mem.get("memory_type") != candidate_type and mem.get("memory_key") != candidate_type:
            continue
        existing_content = mem.get("memory_value", "")
        if _text_similarity(candidate_content, existing_content) >= threshold:
            return mem
    return None


def _detect_contradiction(
    candidate_content: str,
    candidate_type: str,
    existing_memories: List[Dict],
) -> Optional[Dict]:
    """Detects direct contradictions (e.g., boundary says both wants/doesn't want advice).

    Simple heuristic: same type, moderate similarity but opposite keywords.
    Returns conflicting record or None.
    """
    negation_pairs = [
        (r"(tavsiye\s*istiyor)", r"(tavsiye\s*istemiyor)"),
        (r"(kısa\s*yanıt)", r"(uzun\s*yanıt)"),
        (r"(sık\s*iletişim)", r"(az\s*iletişim)"),
    ]
    for mem in existing_memories:
        if mem.get("memory_type") != candidate_type and mem.get("memory_key") != candidate_type:
            continue
        existing_content = mem.get("memory_value", "")
        for pat_a, pat_b in negation_pairs:
            new_has_a = bool(re.search(pat_a, candidate_content, re.I))
            new_has_b = bool(re.search(pat_b, candidate_content, re.I))
            old_has_a = bool(re.search(pat_a, existing_content, re.I))
            old_has_b = bool(re.search(pat_b, existing_content, re.I))
            if (new_has_a and old_has_b) or (new_has_b and old_has_a):
                return mem
    return None


# ---------------------------------------------------------------------------
# Multi-Factor Scoring
# ---------------------------------------------------------------------------

def _score_memory(
    mem: Dict,
    current_emotion: str,
    current_text: str,
) -> float:
    """Computes retrieval score for a memory record.

    score = recency(0.30) + confidence(0.25) + relevance(0.25)
          + importance(0.15) - sensitivity_penalty(0.05)
    All components normalized to [0, 1] before weighting.
    """
    memory_type = mem.get("memory_type") or mem.get("memory_key", "preference")
    content     = mem.get("memory_value", "")
    sensitivity = mem.get("sensitivity", SENSITIVITY_LOW)
    confidence  = float(mem.get("confidence", 0.7))

    # 1. Recency score (lazy decay)
    recency = _compute_decay(
        mem.get("last_reinforced_at"),
        mem.get("created_at"),
    )

    # 2. Confidence score (clamped)
    conf_score = max(0.0, min(1.0, confidence))

    # 3. Relevance score (keyword + emotion + type match)
    relevance = 0.0
    if current_emotion and current_emotion.lower() in content.lower():
        relevance += 0.4
    if current_text:
        words = [w for w in _nfc(current_text).lower().split() if len(w) > 3]
        matched = sum(1 for w in words if w in content.lower())
        if words:
            relevance += 0.6 * min(1.0, matched / max(1, len(words)))
    relevance = min(1.0, relevance)

    # 4. Type importance score (normalized to [0, 1])
    max_imp   = max(_TYPE_IMPORTANCE.values())
    imp_score = _TYPE_IMPORTANCE.get(memory_type, 2) / max_imp

    # 5. Sensitivity penalty (high sensitivity reduces score)
    sens_penalty = {
        SENSITIVITY_LOW:    0.0,
        SENSITIVITY_MEDIUM: 0.3,
        SENSITIVITY_HIGH:   1.0,  # effectively excluded
    }.get(sensitivity, 0.0)

    score = (
        _W_RECENCY    * recency
        + _W_CONFIDENCE * conf_score
        + _W_RELEVANCE  * relevance
        + _W_IMPORTANCE * imp_score
        - _W_SENSITIVITY * sens_penalty
    )
    return max(0.0, score)


# ---------------------------------------------------------------------------
# PersonalContextEngine — Main Class
# ---------------------------------------------------------------------------

class PersonalContextEngine:
    """Advanced AI Memory & Personal Context Engine.

    Designed to be a drop-in replacement for the process_memory() call
    in engine.py. All privacy/crisis rules are enforced internally.
    """

    # ── Extraction ────────────────────────────────────────────────────────

    def extract(
        self,
        user_id: str,
        text: str,
        emotion: str,
        risk: str,
        privacy_mode: bool = False,
    ) -> Dict[str, Any]:
        """Extracts memories from current user turn and stores them.

        Returns structured metadata for logging.
        """
        extracted_count    = 0
        filtered_privacy   = 0
        filtered_crisis    = 0

        if privacy_mode:
            logger.info("PCE_EXTRACT | user=%s | SKIPPED | reason=privacy_mode", user_id)
            return self._meta(0, 0, 0, 0, "privacy_mode")

        if _is_crisis(risk):
            logger.info("PCE_EXTRACT | user=%s | SKIPPED | reason=crisis_turn", user_id)
            return self._meta(0, 0, 0, 0, "crisis_turn")

        normalized = _nfc(text)
        existing   = get_active_memories_for_user(user_id)

        if not _is_privacy_safe(normalized):
            logger.info("PCE_EXTRACT | user=%s | SKIPPED | reason=raw_text_not_privacy_safe", user_id)
            return self._meta(len(existing), 0, 1, 0, "raw_text_not_privacy_safe")

        for mem_type, sensitivity, pattern, template, base_conf in _EXTRACTION_RULES:
            match = re.search(pattern, normalized, flags=re.IGNORECASE | re.UNICODE)
            if not match:
                continue

            matched_span = match.group(0)
            content = template.replace("{match}", matched_span)
            content = _sanitize(content)

            # Privacy gate
            if not _is_privacy_safe(content):
                filtered_privacy += 1
                logger.debug("PCE_EXTRACT | user=%s | BLOCKED_PRIVACY | type=%s", user_id, mem_type)
                continue

            # Re-classify sensitivity (content may upgrade)
            actual_sensitivity = _classify_sensitivity(content)
            if actual_sensitivity == SENSITIVITY_HIGH:
                filtered_privacy += 1
                logger.debug("PCE_EXTRACT | user=%s | BLOCKED_HIGH_SENS | type=%s", user_id, mem_type)
                continue

            # Duplicate check → reinforce instead of insert
            dup = _find_duplicate(content, mem_type, existing)
            if dup:
                refresh_memory_reinforcement(dup["id"], user_id)
                logger.debug("PCE_EXTRACT | user=%s | REINFORCED | id=%d", user_id, dup["id"])
                continue

            # Contradiction check → lower conflicting memory confidence
            conflict = _detect_contradiction(content, mem_type, existing)
            if conflict:
                # Contradicted memory gets confidence penalty (deterministic)
                old_conf = float(conflict.get("confidence", 0.7))
                new_conf = max(0.1, old_conf * 0.6)
                # We update via update_memory_decay as a proxy (keeps confidence intact)
                # Use refresh_memory_reinforcement with a negative boost workaround:
                try:
                    from src.services.database import SessionLocal, UserMemory
                    db = SessionLocal()
                    try:
                        rec = db.query(UserMemory).filter(
                            UserMemory.id == conflict["id"],
                            UserMemory.user_id == user_id,
                        ).first()
                        if rec:
                            rec.confidence = new_conf
                            db.commit()
                    finally:
                        db.close()
                except Exception:
                    pass
                logger.debug(
                    "PCE_EXTRACT | user=%s | CONTRADICTION | existing_id=%d | new_conf=%.2f",
                    user_id, conflict["id"], new_conf,
                )

            # Store
            ok = create_memory(
                user_id=user_id,
                memory_key=mem_type,
                memory_value=content,
                emotion=emotion,
                source_message=None,  # privacy: never store raw user text
                confidence=base_conf,
                source="auto_extraction",
            )
            # Tag with memory_type + sensitivity (update extra columns)
            if ok:
                self._tag_memory(user_id, mem_type, content, mem_type, actual_sensitivity)
                extracted_count += 1

        # Wellness pattern from emotion
        if emotion and emotion.lower() not in {"neutral", "normal", "nötr", ""}:
            emotion_content = f"Kullanıcı '{emotion}' duygusunu tekrar bildirdi."
            if _is_privacy_safe(emotion_content) and _classify_sensitivity(emotion_content) != SENSITIVITY_HIGH:
                ok = create_memory(
                    user_id=user_id,
                    memory_key="wellness_pattern",
                    memory_value=_sanitize(emotion_content),
                    emotion=emotion,
                    source_message=None,
                    confidence=0.55,
                    source="auto_extraction",
                )
                if ok:
                    self._tag_memory(user_id, "wellness_pattern", _sanitize(emotion_content), "wellness_pattern", SENSITIVITY_LOW)
                    extracted_count += 1

        cleanup_old_memories(user_id, max_limit=MAX_MEMORIES_PER_USER)
        total = len(get_active_memories_for_user(user_id))

        logger.info(
            "PCE_EXTRACT | user=%s | extracted=%d | filtered_privacy=%d | total=%d",
            user_id, extracted_count, filtered_privacy, total,
        )
        return self._meta(total, extracted_count, filtered_privacy, filtered_crisis, None)

    # ── Retrieval ─────────────────────────────────────────────────────────

    def retrieve(
        self,
        user_id: str,
        emotion: str,
        risk: str,
        text: str = "",
        privacy_mode: bool = False,
    ) -> Tuple[List[Dict], int, int]:
        """Retrieves relevant memories for current turn using multi-factor scoring.

        Returns: (selected_memories, total_candidates, filtered_count)
        """
        if privacy_mode or _is_crisis(risk):
            return [], 0, 0

        memories = get_active_memories_for_user(user_id)
        if not memories:
            return [], 0, 0

        filtered_count = 0
        scored = []

        for mem in memories:
            sensitivity = mem.get("sensitivity", SENSITIVITY_LOW)
            confidence  = float(mem.get("confidence", 0.7))

            # Hard filter: high sensitivity never injected
            if sensitivity == SENSITIVITY_HIGH:
                filtered_count += 1
                continue

            # Confidence threshold
            if confidence < MIN_CONFIDENCE_THRESHOLD:
                filtered_count += 1
                continue

            score = _score_memory(mem, emotion, text)
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [mem for _, mem in scored[:MAX_INJECTED_MEMORIES]]

        logger.info(
            "PCE_RETRIEVE | user=%s | candidates=%d | selected=%d | filtered=%d",
            user_id, len(memories), len(selected), filtered_count,
        )
        return selected, len(memories), filtered_count

    # ── Injection Builder ────────────────────────────────────────────────

    def build_injection(self, memories: List[Dict]) -> str:
        """Builds a concise memory context block for the prompt.

        Strictly enforces MAX_INJECTION_TOTAL_CHARS (600).
        Returns empty string if nothing selected.
        """
        if not memories:
            return ""

        header = "[KULLANICI HAFIZASI — Kişisel Bağlam]:"
        lines   = [header]
        total   = len(header)

        for mem in memories:
            mem_type = mem.get("memory_type") or mem.get("memory_key", "")
            content  = mem.get("memory_value", "")
            line     = f"• [{mem_type}] {content}"
            if total + len(line) + 1 > MAX_INJECTION_TOTAL_CHARS:
                break
            lines.append(line)
            total += len(line) + 1

        if len(lines) == 1:
            return ""

        return "\n".join(lines)

    # ── Main Entry Point ──────────────────────────────────────────────────

    def process_turn(
        self,
        user_id: str,
        text: str,
        emotion: str,
        risk: str,
        privacy_mode: bool = False,
    ) -> Dict[str, Any]:
        """Main entry point for the Response Engine.

        1. Extract + store memories from current turn
        2. Retrieve relevant memories (scored)
        3. Build injection string
        4. Return structured metadata for logging

        Maintains the same return shape as legacy process_memory() for
        backward compatibility with engine.py.
        """
        # Step 1: Extract
        extract_meta = self.extract(user_id, text, emotion, risk, privacy_mode)

        # Step 2: Retrieve
        selected, candidates, filtered = self.retrieve(
            user_id, emotion, risk, text, privacy_mode
        )

        # Step 3: Build injection
        injection_text = self.build_injection(selected)
        memory_injected = bool(injection_text)

        # Step 4: Structured log (privacy-safe — no raw text)
        logger.info(
            "PCE_PROCESS | user=%s | "
            "memory_candidates=%d | memory_selected=%d | memory_injected=%s | "
            "memory_filtered_privacy=%d | memory_filtered_crisis=%d | "
            "extracted=%d | skipped_reason=%s",
            user_id,
            candidates,
            len(selected),
            memory_injected,
            extract_meta.get("filtered_privacy", 0),
            extract_meta.get("filtered_crisis", 0),
            extract_meta.get("extracted_count", 0),
            extract_meta.get("skipped_reason"),
        )

        return {
            # Backward-compatible keys (engine.py expects these)
            "injection_text":          injection_text,
            "memory_count":            extract_meta.get("memory_count", 0),
            "selected_memory_count":   len(selected),
            "memory_injected":         memory_injected,
            # Extended keys for enhanced logging
            "memory_candidates":       candidates,
            "memory_filtered_privacy": extract_meta.get("filtered_privacy", 0),
            "memory_filtered_crisis":  extract_meta.get("filtered_crisis", 0),
        }

    # ── Internal Helpers ──────────────────────────────────────────────────

    def _tag_memory(
        self,
        user_id: str,
        mem_type: str,
        content: str,
        semantic_type: str,
        sensitivity: str,
    ) -> None:
        """Updates memory_type and sensitivity fields for freshly created memory."""
        try:
            from src.services.database import SessionLocal, UserMemory
            db = SessionLocal()
            try:
                rec = db.query(UserMemory).filter(
                    UserMemory.user_id == user_id,
                    UserMemory.memory_key == mem_type,
                    UserMemory.memory_value == content,
                ).order_by(UserMemory.created_at.desc()).first()
                if rec:
                    rec.memory_type = semantic_type
                    rec.sensitivity = sensitivity
                    rec.last_reinforced_at = datetime.now(timezone.utc)
                    rec.decay_score = 1.0
                    rec.is_active = True
                    db.commit()
            finally:
                db.close()
        except Exception as tag_err:
            logger.debug("PCE | _tag_memory failed (non-critical): %s", tag_err)

    @staticmethod
    def _meta(
        memory_count: int,
        extracted_count: int,
        filtered_privacy: int,
        filtered_crisis: int,
        skipped_reason: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "memory_count":      memory_count,
            "extracted_count":   extracted_count,
            "filtered_privacy":  filtered_privacy,
            "filtered_crisis":   filtered_crisis,
            "skipped_reason":    skipped_reason,
            "memory_injected":   False,
        }

    def consolidate_memories(self, user_id: str) -> Dict[str, Any]:
        """Runs deterministic memory consolidation for a user.

        Tasks performed:
        - Outdated memory decay: Recalculates decay_score and persists to DB. Soft-deletes below MIN_CONFIDENCE_THRESHOLD (0.35).
        - Duplicate memory merge: Finds highly similar memories of the same type, reinforces the stronger one, and soft-deletes the duplicate.
        - Contradiction handling: Detects direct conflicts and penalizes confidence by 40%.

        Returns:
            Dict containing count of merged, decayed, and contradicted memories.
        """
        existing = get_active_memories_for_user(user_id)
        if not existing:
            return {"status": "success", "processed": 0, "merged": 0, "decayed": 0, "contradicted": 0}

        processed_count = len(existing)
        merged_count = 0
        decayed_count = 0
        contradicted_count = 0

        # 1. Lazy decay check and soft-delete below MIN_CONFIDENCE_THRESHOLD
        for mem in existing:
            decay = _compute_decay(mem.get("last_reinforced_at"), mem.get("created_at"))
            update_memory_decay(mem["id"], user_id, decay)

            # If confidence or decay is extremely low, soft delete
            current_conf = float(mem.get("confidence", 0.7))
            if current_conf < MIN_CONFIDENCE_THRESHOLD or decay < 0.15:
                delete_memory_for_user(mem["id"], user_id)
                decayed_count += 1

        # Reload active memories for duplicate and contradiction checks
        existing = get_active_memories_for_user(user_id)

        # 2. Duplicate merge (Jaccard similarity >= 0.75, deterministic)
        i = 0
        while i < len(existing):
            mem_a = existing[i]
            j = i + 1
            while j < len(existing):
                mem_b = existing[j]
                type_a = mem_a.get("memory_type") or mem_a.get("memory_key")
                type_b = mem_b.get("memory_type") or mem_b.get("memory_key")
                if type_a == type_b:
                    similarity = _text_similarity(mem_a.get("memory_value", ""), mem_b.get("memory_value", ""))
                    if similarity >= 0.75:
                        # Reinforce A, delete B
                        refresh_memory_reinforcement(mem_a["id"], user_id, confidence_boost=0.1)
                        delete_memory_for_user(mem_b["id"], user_id)
                        merged_count += 1
                        existing.pop(j)
                        continue
                j += 1
            i += 1

        # 3. Contradiction handling (deterministic keyword negations)
        existing = get_active_memories_for_user(user_id)
        for mem in existing:
            mtype = mem.get("memory_type") or mem.get("memory_key")
            conflict = _detect_contradiction(mem.get("memory_value", ""), mtype, existing)
            if conflict and conflict["id"] != mem["id"]:
                # Lower confidence of both conflicting memories by 40% (x0.6)
                old_conf_a = float(mem.get("confidence", 0.7))
                old_conf_b = float(conflict.get("confidence", 0.7))

                new_conf_a = max(0.1, old_conf_a * 0.6)
                new_conf_b = max(0.1, old_conf_b * 0.6)

                try:
                    from src.services.database import SessionLocal, UserMemory
                    db = SessionLocal()
                    try:
                        rec_a = db.query(UserMemory).filter(UserMemory.id == mem["id"], UserMemory.user_id == user_id).first()
                        rec_b = db.query(UserMemory).filter(UserMemory.id == conflict["id"], UserMemory.user_id == user_id).first()
                        if rec_a:
                            rec_a.confidence = new_conf_a
                        if rec_b:
                            rec_b.confidence = new_conf_b
                        db.commit()
                        contradicted_count += 1
                    finally:
                        db.close()
                except Exception as contradiction_err:
                    logger.debug("PCE | Contradiction confidence penalty failed: %s", contradiction_err)

        logger.info(
            "PCE_CONSOLIDATE | user=%s | processed=%d | merged=%d | decayed=%d | contradicted=%d",
            user_id, processed_count, merged_count, decayed_count, contradicted_count
        )

        return {
            "status": "success",
            "processed": processed_count,
            "merged": merged_count,
            "decayed": decayed_count,
            "contradicted": contradicted_count
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

personal_context_engine = PersonalContextEngine()


def process_turn(
    user_id: str,
    text: str,
    emotion: str,
    risk: str,
    privacy_mode: bool = False,
) -> Dict[str, Any]:
    """Convenience wrapper — backward-compatible with legacy call sites."""
    return personal_context_engine.process_turn(user_id, text, emotion, risk, privacy_mode)


def consolidate_memories(user_id: str) -> Dict[str, Any]:
    """Convenience wrapper — consolidated memory pipeline."""
    return personal_context_engine.consolidate_memories(user_id)

