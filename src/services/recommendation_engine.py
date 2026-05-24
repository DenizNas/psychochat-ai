"""
recommendation_engine.py — Faz 10 Prompt 7
============================================
Privacy-safe, diagnosis-free, deterministic Rule-Based Recommendation Engine v1.

Design Principles:
    - ZERO raw chat text usage — metadata-driven only
    - ZERO raw journal note usage — only mood/intensity metadata
    - ZERO medical diagnosis language — wellness-safe framing only
    - Crisis-safe prioritization — professional_support surfaces first on high crisis count
    - Explainable — every recommendation has a human-readable reason
    - Idempotent refresh — no spam-duplicates within expiry window

Recommendation Sources (all metadata-only):
    1. Emotion event summary (7d, 30d comparison)
    2. Daily mood trend metadata
    3. Mood journal intensity/mood aggregates
    4. Wellness dashboard overview
    5. Scheduled intervention history
    6. Behavioral insights (from behavioral_insights.py)

Output format (per recommendation):
    {
        "id": "rec_<user>_<type>_<datestamp>",
        "recommendation_type": str,
        "title": str,
        "description": str,
        "priority": "low" | "medium" | "high",
        "confidence": float (0.0–1.0),
        "reason": str,    # wellness-safe, no raw text
        "actions": list[dict],
        "created_at": ISO-8601 str,
        "expires_at": ISO-8601 str,
        "source": "recommendation_engine_v1"
    }
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from src.services.database import (
    SessionLocal,
    get_user_emotion_summary,
    get_mood_journals_for_user,
    get_scheduled_interventions_for_user,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

REC_EXPIRY_HOURS: int = 48  # Default recommendation TTL

# Wellness-safe action types (matched in Android RecommendationScreen)
_ACTION_BREATHING  = "open_breathing_timer"
_ACTION_JOURNAL    = "open_journal"
_ACTION_WALK       = "open_walk_tracker"
_ACTION_HYDRATION  = "set_hydration_reminder"
_ACTION_SLEEP      = "open_sleep_routine"
_ACTION_SOCIAL     = "open_social_tips"
_ACTION_REFLECT    = "open_positive_reflection"
_ACTION_SUPPORT    = "show_professional_support_info"
_ACTION_SCREEN     = "show_screen_time_tips"
_ACTION_FOCUS      = "start_focus_timer"
_ACTION_CHECKIN    = "open_mood_checkin"
_ACTION_GROUNDING  = "open_grounding_exercise"

# ── ORM Model (imported lazily to avoid circular imports) ────────────────────

def _get_rec_event_model():
    """Lazy import of RecommendationEvent to avoid circular DB import."""
    from src.services.database import RecommendationEvent
    return RecommendationEvent


# ── Public API ────────────────────────────────────────────────────────────────

def generate_recommendations(
    user_id: str,
    privacy_mode: bool = False,
    wellness_insights_consent: bool = True,
) -> List[Dict[str, Any]]:
    """
    Core entry-point: generates personalised wellness recommendations.

    Args:
        user_id:                  Authenticated user identifier.
        privacy_mode:             If True, generation is minimised (consent gate).
        wellness_insights_consent: If False, recommendations are blocked per consent.

    Returns:
        List of recommendation dicts (already persisted to DB as active).
    """
    start = time.time()

    # ── Consent / Privacy Gate ────────────────────────────────────────────────
    if not wellness_insights_consent:
        logger.info(
            "RECOMMENDATION_ENGINE | skipped_privacy | user=%s | reason=consent_off",
            user_id,
        )
        return []

    if privacy_mode:
        logger.info(
            "RECOMMENDATION_ENGINE | skipped_privacy | user=%s | reason=privacy_mode",
            user_id,
        )
        return []

    # ── Load metadata signals ─────────────────────────────────────────────────
    signals = _collect_signals(user_id)

    # ── Run scoring rules ─────────────────────────────────────────────────────
    candidates = _run_rules(user_id, signals)

    # ── Crisis-safe prioritization ────────────────────────────────────────────
    candidates = _apply_crisis_prioritization(candidates, signals)

    # ── Novelty / diversity filter ────────────────────────────────────────────
    candidates = _apply_diversity(candidates)

    # ── Duplicate / expiry guard ──────────────────────────────────────────────
    candidates = _filter_existing(user_id, candidates)

    # ── Persist active recommendations ────────────────────────────────────────
    persisted = _persist_recommendations(user_id, candidates)

    elapsed_ms = (time.time() - start) * 1000
    logger.info(
        "RECOMMENDATION_ENGINE | generated | user=%s | count=%d | crisis_count=%d"
        " | latency_ms=%.1f",
        user_id,
        len(persisted),
        signals.get("crisis_count_7d", 0),
        elapsed_ms,
    )
    return persisted


def get_active_recommendations(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves currently active (non-expired) recommendations for a user."""
    RecEvent = _get_rec_event_model()
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = (
            db.query(RecEvent)
            .filter(
                RecEvent.user_id == user_id,
                RecEvent.status == "active",
                RecEvent.expires_at > now,
            )
            .order_by(
                RecEvent.priority_order.asc(),
                RecEvent.created_at.desc(),
            )
            .limit(12)
            .all()
        )
        return [_rec_to_dict(r) for r in rows]
    except Exception as e:
        logger.error("RECOMMENDATION_ENGINE | get_active error | user=%s | %s", user_id, e)
        return []
    finally:
        db.close()


def record_feedback(
    user_id: str,
    rec_id: str,
    feedback: str,  # "helpful" | "not_helpful" | "dismissed"
) -> bool:
    """Records user feedback on a recommendation and updates its status."""
    RecEvent = _get_rec_event_model()
    db = SessionLocal()
    try:
        rec = (
            db.query(RecEvent)
            .filter(RecEvent.id == rec_id, RecEvent.user_id == user_id)
            .first()
        )
        if not rec:
            return False

        if feedback == "dismissed":
            rec.status = "dismissed"
        elif feedback in ("helpful", "not_helpful"):
            rec.status = "completed"

        # Store feedback value in metadata_json for future scoring improvement
        meta = json.loads(rec.metadata_json or "{}")
        meta["feedback"] = feedback
        meta["feedback_at"] = datetime.now(timezone.utc).isoformat()
        rec.metadata_json = json.dumps(meta, ensure_ascii=False)

        db.commit()
        logger.info(
            "RECOMMENDATION_ENGINE | feedback | user=%s | rec_id=%s | feedback=%s",
            user_id, rec_id, feedback,
        )
        return True
    except Exception as e:
        db.rollback()
        logger.error(
            "RECOMMENDATION_ENGINE | feedback_error | user=%s | %s", user_id, e
        )
        return False
    finally:
        db.close()


def expire_old_recommendations(user_id: Optional[str] = None) -> int:
    """
    Marks expired recommendations as 'expired'.
    Called by Celery periodic task or on-demand.
    Returns count of expired records.
    """
    RecEvent = _get_rec_event_model()
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        q = db.query(RecEvent).filter(
            RecEvent.status == "active",
            RecEvent.expires_at <= now,
        )
        if user_id:
            q = q.filter(RecEvent.user_id == user_id)
        recs = q.all()
        for r in recs:
            r.status = "expired"
        db.commit()
        return len(recs)
    except Exception as e:
        db.rollback()
        logger.error("RECOMMENDATION_ENGINE | expire_error | %s", e)
        return 0
    finally:
        db.close()


def anonymize_recommendations(user_id: str) -> int:
    """Deletes all recommendation_events for a user (GDPR / delete flow)."""
    RecEvent = _get_rec_event_model()
    db = SessionLocal()
    try:
        deleted = (
            db.query(RecEvent)
            .filter(RecEvent.user_id == user_id)
            .delete()
        )
        db.commit()
        logger.info(
            "RECOMMENDATION_ENGINE | anonymized | user=%s | deleted=%d",
            user_id, deleted,
        )
        return deleted
    except Exception as e:
        db.rollback()
        logger.error("RECOMMENDATION_ENGINE | anonymize_error | user=%s | %s", user_id, e)
        return 0
    finally:
        db.close()


# ── Signal Collection ─────────────────────────────────────────────────────────

def _collect_signals(user_id: str) -> Dict[str, Any]:
    """
    Pulls all metadata signals (NO raw text) needed for rule evaluation.

    Returns a flat signal dict with keys:
        crisis_count_7d, crisis_count_30d,
        dominant_emotion_7d, dominant_emotion_30d,
        anxiety_rate_7d, sadness_rate_7d, joy_rate_7d,
        total_messages_7d, total_messages_30d,
        mood_avg_intensity_7d, mood_entry_count_7d,
        mood_avg_intensity_30d, mood_entry_count_30d,
        pending_interventions_count,
        stress_trend_increasing,  (bool)
        anomaly_intensity_spike,  (bool)
        anomaly_journal_drop,     (bool)
    """
    sig: Dict[str, Any] = {}

    # 1. Emotion summary — 7d
    summary_7d = get_user_emotion_summary(user_id=user_id, days=7)
    sig["total_messages_7d"]    = summary_7d.get("total_messages", 0)
    sig["crisis_count_7d"]      = summary_7d.get("crisis_count", 0)
    sig["dominant_emotion_7d"]  = (summary_7d.get("dominant_emotion") or "neutral").lower()
    dist_7d                     = summary_7d.get("emotion_distribution", {})

    total_7d = sig["total_messages_7d"] or 1  # guard against zero-division
    sig["anxiety_rate_7d"] = _emotion_rate(dist_7d, [
        "anxiety", "kaygı", "stres", "stress"
    ], total_7d)
    sig["sadness_rate_7d"] = _emotion_rate(dist_7d, [
        "sadness", "üzüntü", "sad", "durgun"
    ], total_7d)
    sig["joy_rate_7d"] = _emotion_rate(dist_7d, [
        "joy", "happiness", "mutlu", "neşe", "mutluluk"
    ], total_7d)
    sig["anger_rate_7d"] = _emotion_rate(dist_7d, [
        "anger", "öfke", "angry", "kızgın"
    ], total_7d)

    # 2. Emotion summary — 30d (for anomaly comparison)
    summary_30d = get_user_emotion_summary(user_id=user_id, days=30)
    sig["total_messages_30d"]   = summary_30d.get("total_messages", 0)
    sig["crisis_count_30d"]     = summary_30d.get("crisis_count", 0)
    sig["dominant_emotion_30d"] = (summary_30d.get("dominant_emotion") or "neutral").lower()
    dist_30d                    = summary_30d.get("emotion_distribution", {})
    total_30d                   = sig["total_messages_30d"] or 1
    sig["anxiety_rate_30d"]     = _emotion_rate(dist_30d, [
        "anxiety", "kaygı", "stres", "stress"
    ], total_30d)

    # 3. Mood journal metadata — 7d and 30d
    journals_7d = get_mood_journals_for_user(user_id=user_id, days=7)
    journals_30d = get_mood_journals_for_user(user_id=user_id, days=30)
    sig["mood_entry_count_7d"]    = len(journals_7d)
    sig["mood_entry_count_30d"]   = len(journals_30d)
    sig["mood_avg_intensity_7d"]  = (
        sum(j.get("intensity", 3) for j in journals_7d) / len(journals_7d)
        if journals_7d else 3.0
    )
    sig["mood_avg_intensity_30d"] = (
        sum(j.get("intensity", 3) for j in journals_30d) / len(journals_30d)
        if journals_30d else 3.0
    )
    sig["mood_types_7d"] = Counter(
        j.get("mood", "neutral") for j in journals_7d
    )

    # 4. Intervention history
    interventions = get_scheduled_interventions_for_user(user_id=user_id)
    sig["pending_interventions_count"] = sum(
        1 for i in interventions if i.get("status") == "pending"
    )

    # 5. Derived: stress_trend_increasing (7d vs 30d anxiety rate delta)
    delta_anxiety = sig["anxiety_rate_7d"] - sig["anxiety_rate_30d"]
    sig["stress_trend_increasing"] = delta_anxiety >= 0.15

    # 6. Anomaly: intensity spike (7d intensity > 30d intensity by >= 0.8)
    intensity_delta = sig["mood_avg_intensity_7d"] - sig["mood_avg_intensity_30d"]
    sig["anomaly_intensity_spike"] = intensity_delta >= 0.8

    # 7. Anomaly: journal drop (30d count >4 but 7d count <=1)
    sig["anomaly_journal_drop"] = (
        sig["mood_entry_count_30d"] >= 4 and sig["mood_entry_count_7d"] <= 1
    )

    return sig


# ── Rule Engine ───────────────────────────────────────────────────────────────

def _run_rules(user_id: str, sig: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based recommendation generation.
    Rules are evaluated in priority order. Each rule emits at most one recommendation.
    Returns list of candidate recommendation dicts (not yet persisted).
    """
    now = datetime.now(timezone.utc)
    candidates: List[Dict[str, Any]] = []

    # ── RULE 1: Crisis safety — professional support ──────────────────────────
    if sig["crisis_count_7d"] >= 2:
        confidence = min(1.0, 0.80 + sig["crisis_count_7d"] * 0.04)
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="professional_support",
            title="Profesyonel destek faydalı olabilir",
            description=(
                "Son günlerde zorlayıcı duygu durumlarının öne çıktığı gözlemlendi. "
                "Bir psikoloji uzmanıyla konuşmak destekleyici olabilir."
            ),
            priority="high",
            confidence=round(confidence, 2),
            reason=(
                "Son 7 günde yüksek yoğunluklu duygu örüntüleri birden fazla kez öne çıktı."
            ),
            actions=[{
                "label": "Destek kaynaklarını gör",
                "action_type": _ACTION_SUPPORT,
            }],
            now=now,
        ))
        logger.info(
            "RECOMMENDATION_ENGINE | crisis_priority | user=%s | crisis_count=%d",
            user_id, sig["crisis_count_7d"],
        )

    # ── RULE 2: High anxiety rate — breathing break ───────────────────────────
    if sig["anxiety_rate_7d"] >= 0.35 and sig["total_messages_7d"] >= 4:
        confidence = min(1.0, 0.55 + sig["anxiety_rate_7d"] * 0.45)
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="breathing_break",
            title="Kısa bir nefes molası iyi gelebilir",
            description=(
                "Son günlerde kaygı temalı örüntüler biraz öne çıkmış görünüyor. "
                "Bir dakikalık nefes molası destekleyici olabilir."
            ),
            priority="medium" if sig["anxiety_rate_7d"] < 0.60 else "high",
            confidence=round(confidence, 2),
            reason=(
                "Son 7 günde kaygı yoğunluğu ve stres işaretleri sıkça tekrarlandı."
            ),
            actions=[{
                "label": "1 dakikalık nefes egzersizi",
                "action_type": _ACTION_BREATHING,
            }],
            now=now,
        ))

    # ── RULE 3: High sadness rate — journaling prompt ─────────────────────────
    if sig["sadness_rate_7d"] >= 0.30 and sig["total_messages_7d"] >= 4:
        confidence = min(1.0, 0.50 + sig["sadness_rate_7d"] * 0.50)
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="journaling_prompt",
            title="Hislerini yazmak hafifletici olabilir",
            description=(
                "Duygularını kâğıda dökmek zaman zaman içi rahatlatır. "
                "Bugün birkaç satır yazmayı denemek isteyebilirsin."
            ),
            priority="medium",
            confidence=round(confidence, 2),
            reason="Son 7 günde durgun ve hüzünlü duygu örüntüleri öne çıktı.",
            actions=[{
                "label": "Günlük yaz",
                "action_type": _ACTION_JOURNAL,
            }],
            now=now,
        ))

    # ── RULE 4: Stress trend increasing — grounding exercise ─────────────────
    if sig["stress_trend_increasing"] and sig["total_messages_7d"] >= 3:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="grounding_exercise",
            title="Topraklanma egzersizi deneye bilirsin",
            description=(
                "Son günlerde genel duygu yoğunluğunda artış gözlemlendi. "
                "5-4-3-2-1 topraklanma tekniği zihni sakinleştirmeye yardımcı olabilir."
            ),
            priority="medium",
            confidence=0.72,
            reason="Son 7 günde duygu yoğunluğu önceki döneme kıyasla artış gösterdi.",
            actions=[{
                "label": "Topraklanma egzersizini başlat",
                "action_type": _ACTION_GROUNDING,
            }],
            now=now,
        ))

    # ── RULE 5: Anomaly — intensity spike ────────────────────────────────────
    if sig["anomaly_intensity_spike"] and sig["mood_entry_count_7d"] >= 2:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="mood_checkin",
            title="Nasıl hissediyorsun?",
            description=(
                "Son günlerde duygu yoğunluğunda artış gözlemlendi. "
                "Ruh halini kısa bir notla kaydetmek faydalı olabilir."
            ),
            priority="medium",
            confidence=0.68,
            reason=(
                "Son 7 gün ruh hali yoğunluğu önceki 30 güne göre belirgin biçimde arttı."
            ),
            actions=[{
                "label": "Ruh hali notunu gir",
                "action_type": _ACTION_CHECKIN,
            }],
            now=now,
        ))

    # ── RULE 6: High anger rate — short walk ─────────────────────────────────
    if sig["anger_rate_7d"] >= 0.25 and sig["total_messages_7d"] >= 4:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="short_walk",
            title="Kısa bir yürüyüş enerjini dengeleyebilir",
            description=(
                "Gerginlik ve öfke duygularının öne çıktığı günlerde kısa bir yürüyüş "
                "zihni rahatlatmaya yardımcı olabilir."
            ),
            priority="medium",
            confidence=0.65,
            reason="Son 7 günde gerginlik ve yoğun duygu örüntüleri öne çıktı.",
            actions=[{
                "label": "Yürüyüşe çık",
                "action_type": _ACTION_WALK,
            }],
            now=now,
        ))

    # ── RULE 7: High intensity mood journals — hydration reminder ─────────────
    if sig["mood_avg_intensity_7d"] >= 3.8 and sig["mood_entry_count_7d"] >= 2:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="hydration_reminder",
            title="Su içmeyi unutma",
            description=(
                "Yoğun duygu deneyimleri enerjiyi tüketir. "
                "Bol su içmek zihinsel netliği destekler."
            ),
            priority="low",
            confidence=0.58,
            reason="Son günlerde yüksek yoğunluklu ruh hali girişleri öne çıktı.",
            actions=[{
                "label": "Su hatırlatıcısı kur",
                "action_type": _ACTION_HYDRATION,
            }],
            now=now,
        ))

    # ── RULE 8: Journal drop anomaly — mood check-in ──────────────────────────
    if sig["anomaly_journal_drop"]:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="mood_checkin",
            title="Ruh halin nasıl?",
            description=(
                "Son günlerde günlük takibinde bir azalma gözlemlendi. "
                "Kısa bir ruh hali kaydı içini dökmene yardımcı olabilir."
            ),
            priority="low",
            confidence=0.60,
            reason="Son 7 günde günlük giriş sıklığında düşüş gözlemlendi.",
            actions=[{
                "label": "Ruh halini kaydet",
                "action_type": _ACTION_CHECKIN,
            }],
            now=now,
        ))

    # ── RULE 9: Low joy rate — positive reflection ────────────────────────────
    if sig["joy_rate_7d"] <= 0.10 and sig["total_messages_7d"] >= 4:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="positive_reflection",
            title="Olumlu bir an bul",
            description=(
                "Bugün seni mutlu eden küçük bir şeyi hatırlamak zihni dinginleştirebilir."
            ),
            priority="low",
            confidence=0.55,
            reason="Son 7 günde olumlu duygu örüntüleri oldukça sınırlı kaldı.",
            actions=[{
                "label": "Olumlu yansıma egzersizi",
                "action_type": _ACTION_REFLECT,
            }],
            now=now,
        ))

    # ── RULE 10: Pending interventions > 2 — focus break ─────────────────────
    if sig["pending_interventions_count"] >= 2:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="focus_break",
            title="Kısa bir ara ver",
            description=(
                "Yoğun planlı aktiviteler varken kendine küçük molalar vermek "
                "sürdürülebilirlik açısından faydalıdır."
            ),
            priority="low",
            confidence=0.52,
            reason="Birden fazla planlanmış aktivite bulunuyor.",
            actions=[{
                "label": "Odak molası başlat",
                "action_type": _ACTION_FOCUS,
            }],
            now=now,
        ))

    # ── RULE 11: Sleep routine (low entry + high intensity evening pattern) ───
    if (
        sig["mood_avg_intensity_7d"] >= 3.5
        and sig["total_messages_7d"] >= 3
        and sig["joy_rate_7d"] < 0.20
    ):
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="sleep_routine",
            title="Uyku düzenine dikkat etmek iyi gelebilir",
            description=(
                "Yoğun duygusal günler uyku kalitesini etkileyebilir. "
                "Düzenli bir uyku rutini genel iyi hissi destekler."
            ),
            priority="low",
            confidence=0.58,
            reason="Son günlerde yüksek yoğunluklu duygu örüntüleri gözlemlendi.",
            actions=[{
                "label": "Uyku rutini önerilerini gör",
                "action_type": _ACTION_SLEEP,
            }],
            now=now,
        ))

    # ── RULE 12: Social connection (prolonged sadness + low joy) ─────────────
    if sig["sadness_rate_7d"] >= 0.25 and sig["joy_rate_7d"] <= 0.15:
        candidates.append(_make_rec(
            user_id=user_id,
            rec_type="social_connection",
            title="Biriyle bağlantı kurmak iyi gelebilir",
            description=(
                "Güvendiğin biriyle kısa bir sohbet bazen büyük fark yaratır."
            ),
            priority="low",
            confidence=0.60,
            reason="Son 7 günde düşük duygu durumu ve sınırlı neşe örüntüleri öne çıktı.",
            actions=[{
                "label": "Sosyal bağlantı ipuçları",
                "action_type": _ACTION_SOCIAL,
            }],
            now=now,
        ))

    return candidates


# ── Crisis-Safe Prioritization ────────────────────────────────────────────────

def _apply_crisis_prioritization(
    candidates: List[Dict], sig: Dict
) -> List[Dict]:
    """
    When crisis_count_7d >= 2:
      - professional_support is sorted to top with priority=high
      - other medium/low recs are demoted one priority step
    This ensures crisis safety without exposing crisis content.
    """
    if sig["crisis_count_7d"] < 2:
        return candidates

    result = []
    for c in candidates:
        if c["recommendation_type"] == "professional_support":
            c["priority"] = "high"
            c["_priority_order"] = 0
        else:
            # Demote all others when crisis is active
            if c["priority"] == "high":
                c["priority"] = "medium"
            elif c["priority"] == "medium":
                c["priority"] = "low"
            c["_priority_order"] = 2
        result.append(c)

    result.sort(key=lambda x: x.get("_priority_order", 1))
    return result


# ── Diversity Filter ──────────────────────────────────────────────────────────

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

def _apply_diversity(candidates: List[Dict]) -> List[Dict]:
    """
    Removes duplicate recommendation types (keep highest confidence per type).
    Sorts by priority → confidence desc.
    Caps at 5 recommendations per refresh cycle.
    """
    seen_types: set = set()
    unique: List[Dict] = []
    # Sort by priority first, then confidence desc
    sorted_cands = sorted(
        candidates,
        key=lambda c: (_PRIORITY_ORDER.get(c["priority"], 2), -c["confidence"]),
    )
    for c in sorted_cands:
        if c["recommendation_type"] not in seen_types:
            seen_types.add(c["recommendation_type"])
            unique.append(c)
        if len(unique) >= 5:
            break
    return unique


# ── Duplicate Guard ───────────────────────────────────────────────────────────

def _filter_existing(user_id: str, candidates: List[Dict]) -> List[Dict]:
    """
    Filters out recommendation types that already have an active (non-expired)
    record in the DB for this user. Prevents spam-duplicates within expiry window.
    """
    RecEvent = _get_rec_event_model()
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        existing = (
            db.query(RecEvent.recommendation_type)
            .filter(
                RecEvent.user_id == user_id,
                RecEvent.status == "active",
                RecEvent.expires_at > now,
            )
            .all()
        )
        existing_types = {r.recommendation_type for r in existing}
        return [c for c in candidates if c["recommendation_type"] not in existing_types]
    except Exception as e:
        logger.error(
            "RECOMMENDATION_ENGINE | filter_existing_error | user=%s | %s", user_id, e
        )
        return candidates
    finally:
        db.close()


# ── Persistence ───────────────────────────────────────────────────────────────

def _persist_recommendations(
    user_id: str, candidates: List[Dict]
) -> List[Dict[str, Any]]:
    """Saves all candidate recommendations to recommendation_events table."""
    if not candidates:
        return []

    RecEvent = _get_rec_event_model()
    db = SessionLocal()
    try:
        persisted = []
        for c in candidates:
            priority_order = _PRIORITY_ORDER.get(c.get("priority", "low"), 2)
            rec = RecEvent(
                id=c["id"],
                user_id=user_id,
                recommendation_type=c["recommendation_type"],
                title=c["title"],
                description=c["description"],
                priority=c["priority"],
                priority_order=priority_order,
                confidence=c["confidence"],
                reason=c["reason"],
                status="active",
                created_at=datetime.fromisoformat(c["created_at"]),
                expires_at=datetime.fromisoformat(c["expires_at"]),
                source="recommendation_engine_v1",
                metadata_json=json.dumps({
                    "actions": c.get("actions", []),
                }, ensure_ascii=False),
            )
            db.add(rec)
            persisted.append(c)
        db.commit()
        return persisted
    except Exception as e:
        db.rollback()
        logger.error(
            "RECOMMENDATION_ENGINE | persist_error | user=%s | %s", user_id, e
        )
        return []
    finally:
        db.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_rec(
    user_id: str,
    rec_type: str,
    title: str,
    description: str,
    priority: str,
    confidence: float,
    reason: str,
    actions: List[Dict],
    now: datetime,
) -> Dict[str, Any]:
    """Constructs a recommendation candidate dict."""
    date_str = now.strftime("%Y%m%d%H%M")
    safe_uid = user_id.replace(" ", "_")[:20]
    rec_id = f"rec_{safe_uid}_{rec_type}_{date_str}"
    expires = now + timedelta(hours=REC_EXPIRY_HOURS)
    return {
        "id": rec_id,
        "recommendation_type": rec_type,
        "title": title,
        "description": description,
        "priority": priority,
        "confidence": confidence,
        "reason": reason,
        "actions": actions,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "source": "recommendation_engine_v1",
    }


def _emotion_rate(dist: Dict[str, int], emotion_keys: List[str], total: int) -> float:
    """Computes summed rate for a group of emotion labels."""
    count = sum(dist.get(k, 0) for k in emotion_keys)
    return count / total


def _rec_to_dict(rec) -> Dict[str, Any]:
    """Converts a RecommendationEvent ORM row to a safe API response dict."""
    meta = {}
    try:
        meta = json.loads(rec.metadata_json or "{}")
    except Exception:
        pass
    return {
        "id": rec.id,
        "recommendation_type": rec.recommendation_type,
        "title": rec.title,
        "description": rec.description,
        "priority": rec.priority,
        "confidence": rec.confidence,
        "reason": rec.reason,
        "actions": meta.get("actions", []),
        "status": rec.status,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
        "source": rec.source,
    }
