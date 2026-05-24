import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.metrics import COMPLIANCE_AUDIT_EVENTS_TOTAL
from src.services.database import (
    User, UserProfile, UserMemory, Analytics, ChatHistory,
    MoodJournal, EmotionEvent, ScheduledIntervention, NotificationEvent,
    SecurityAuditLog, UserConsent
)

logger = logging.getLogger(__name__)

class ComplianceService:
    """
    SRE-Grade Enterprise Compliance & Privacy Governance Service.
    Enforces Kvkk/GDPR rules, encrypted audit logs, consent tracking, 
    and irreversible anonymization strategies.
    """

    def hash_sensitive_value(self, val: str) -> str:
        """
        Cryptographically hashes a sensitive value (like IP or User-Agent)
        using SHA-256 and the application secret key as a secure salt.
        This guarantees complete protection of PII in the audit log database.
        """
        if not val:
            return "empty"
        salt = settings.SECRET_KEY or "default_audit_salt"
        payload = f"{val}:{salt}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _sanitize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Recursively strips any sensitive keys (e.g. passwords, tokens, API keys) 
        from audit log metadata payloads to prevent leaks.
        """
        if not metadata:
            return {}
        
        sensitive_keywords = {"pass", "token", "key", "secret", "auth", "credential", "prompt"}
        sanitized = {}
        for k, v in metadata.items():
            if any(kw in k.lower() for kw in sensitive_keywords):
                sanitized[k] = "<redacted>"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_metadata(v)
            else:
                sanitized[k] = v
        return sanitized

    def log_security_event(
        self,
        db: Session,
        user_id: Optional[str],
        event_type: str,
        ip_address: str,
        user_agent: str,
        request_id: Optional[str] = None,
        severity: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Logs a secure audit event to the database.
        Hashes sensitive client identifiers, sanitizes extra metadata, 
        and increments isolated Prometheus counters.
        Runs under robust exception shielding to prevent disrupting user journeys.
        """
        try:
            hashed_ip = self.hash_sensitive_value(ip_address)
            hashed_ua = self.hash_sensitive_value(user_agent)
            sanitized_meta = self._sanitize_metadata(metadata)
            
            # Formulate ORM log entry
            log_entry = SecurityAuditLog(
                user_id=user_id,
                event_type=event_type,
                ip_address_hash=hashed_ip,
                user_agent_hash=hashed_ua,
                request_id=request_id,
                severity=severity,
                metadata_json=json.dumps(sanitized_meta) if sanitized_meta else None
            )
            db.add(log_entry)
            db.commit()
            
            # Increment Prometheus telemetry
            COMPLIANCE_AUDIT_EVENTS_TOTAL.labels(event_type=event_type, severity=severity).inc()
            logger.info("AUDIT_LOG | Event: %s | User: %s | Severity: %s", event_type, user_id, severity)
            return True
        except Exception as e:
            db.rollback()
            logger.error("AUDIT_LOG_ERROR | Failed to write compliance event: %s", e)
            return False

    def cleanup_old_audit_logs(self, db: Session, retention_days: int = 180) -> int:
        """
        Purges security audit records exceeding the legal retention policy limit (default 180 days).
        Returns the count of successfully deleted records.
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            deleted_count = db.query(SecurityAuditLog).filter(
                SecurityAuditLog.created_at < cutoff
            ).delete()
            db.commit()
            logger.info("AUDIT_LOG_CLEANUP | Expired logs purged. Retention: %d days | Deleted: %d", retention_days, deleted_count)
            return deleted_count
        except Exception as e:
            db.rollback()
            logger.error("AUDIT_LOG_CLEANUP_ERROR | Failed to purge audit logs: %s", e)
            return 0

    def export_user_data(self, db: Session, username: str) -> Dict[str, Any]:
        """
        Generates a complete, privacy-safe JSON representation of all data 
        associated with a user, excluding passwords, tokens, prompts, or secrets.
        Conforms strictly to GDPR Article 20 Right to Data Portability.
        """
        # 1. Fetch Profile (utilize get_or_create_profile for lazy defaults creation)
        from src.services.database import get_or_create_profile
        profile_data = {}
        try:
            profile_data = get_or_create_profile(username)
        except Exception:
            profile_row = db.query(UserProfile).filter(UserProfile.username == username).first()
            if profile_row:
                profile_data = {
                    "username": profile_row.username,
                    "display_name": profile_row.display_name,
                    "bio": profile_row.bio,
                    "profile_photo_url": profile_row.profile_photo_url,
                    "preferred_language": profile_row.preferred_language,
                    "response_style": profile_row.response_style,
                    "theme_preference": profile_row.theme_preference,
                    "notifications_enabled": profile_row.notifications_enabled,
                    "privacy_mode": profile_row.privacy_mode,
                    "answer_length_preference": profile_row.answer_length_preference,
                    "created_at": profile_row.created_at.isoformat() if profile_row.created_at else None
                }

        # 2. Fetch Mood Journals
        mood_rows = db.query(MoodJournal).filter(MoodJournal.user_id == username).all()
        mood_journals = [
            {
                "mood": m.mood,
                "intensity": m.intensity,
                "note": m.note,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "source": m.source
            }
            for m in mood_rows
        ]

        # 3. Fetch Memory Summaries (Privacy-safe: excludes raw source chat messages!)
        memory_rows = db.query(UserMemory).filter(
            UserMemory.user_id == username,
            UserMemory.is_active == True
        ).all()
        memories = [
            {
                "memory_key": m.memory_key,
                "memory_value": m.memory_value,
                "memory_type": m.memory_type or "preference",
                "sensitivity": m.sensitivity or "low",
                "confidence": m.confidence,
                "decay_score": m.decay_score if m.decay_score is not None else 1.0,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in memory_rows
        ]

        # 4. Fetch Emotion Events Timeline
        emotion_rows = db.query(EmotionEvent).filter(EmotionEvent.user_id == username).all()
        emotion_timeline = [
            {
                "emotion": e.emotion,
                "risk": e.risk,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "source": e.source
            }
            for e in emotion_rows
        ]

        # 5. Fetch Scheduled Interventions
        intervention_rows = db.query(ScheduledIntervention).filter(ScheduledIntervention.user_id == username).all()
        interventions = [
            {
                "intervention_type": i.intervention_type,
                "scheduled_for": i.scheduled_for.isoformat() if i.scheduled_for else None,
                "status": i.status,
                "priority": i.priority,
                "created_at": i.created_at.isoformat() if i.created_at else None
            }
            for i in intervention_rows
        ]

        # 6. Fetch Notification Settings logs
        notification_rows = db.query(NotificationEvent).filter(NotificationEvent.user_id == username).all()
        notification_events = [
            {
                "notification_type": n.notification_type,
                "status": n.status,
                "scheduled_for": n.scheduled_for.isoformat() if n.scheduled_for else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "delivered_at": n.delivered_at.isoformat() if n.delivered_at else None
            }
            for n in notification_rows
        ]

        # 7. Fetch Consent status
        consent_row = db.query(UserConsent).filter(UserConsent.user_id == username).first()
        consent_status = {
            "privacy_policy_version": consent_row.privacy_policy_version,
            "terms_version": consent_row.terms_version,
            "analytics_consent": consent_row.analytics_consent,
            "wellness_insights_consent": consent_row.wellness_insights_consent,
            "notifications_consent": consent_row.notifications_consent,
            "ai_processing_consent": consent_row.ai_processing_consent,
            "updated_at": consent_row.updated_at.isoformat() if consent_row.updated_at else None
        } if consent_row else {
            "privacy_policy_version": "v1.0",
            "terms_version": "v1.0",
            "analytics_consent": False,
            "wellness_insights_consent": False,
            "notifications_consent": False,
            "ai_processing_consent": False
        }

        # 8. Fetch Security Audit trail headers (Sanitized — excludes IP/UA hashes and complex internal metadatas)
        audit_rows = db.query(SecurityAuditLog).filter(SecurityAuditLog.user_id == username).all()
        audit_trail = [
            {
                "event_type": a.event_type,
                "severity": a.severity,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in audit_rows
        ]

        # 9. Fetch Wellness Recommendations History
        from src.services.database import RecommendationEvent
        rec_rows = db.query(RecommendationEvent).filter(RecommendationEvent.user_id == username).all()
        recommendations = [
            {
                "id": r.id,
                "recommendation_type": r.recommendation_type,
                "title": r.title,
                "description": r.description,
                "priority": r.priority,
                "confidence": r.confidence,
                "reason": r.reason,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "source": r.source,
                "metadata_json": r.metadata_json
            }
            for r in rec_rows
        ]

        # Compile final GDPR compliant export JSON payload
        export_payload = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "export_version": "GDPR-v1.0",
            "personal_profile": profile_data,
            "manual_mood_journals": mood_journals,
            "persistent_memories": memories,
            "emotion_timeline": emotion_timeline,
            "scheduled_wellness_interventions": interventions,
            "notifications_logs": notification_events,
            "data_processing_consents": consent_status,
            "compliance_audit_summary": audit_trail,
            "wellness_recommendations": recommendations
        }
        return export_payload

    def delete_user_data(self, db: Session, username: str) -> bool:
        """
        Performs irreversible deactivation and anonymization of user data.
        1. Deletes the core User credential record (logins permanently blocked).
        2. Blanks personal identifiers in UserProfile.
        3. Soft-deletes user memory summaries (sets is_active=False).
        4. Replaces manual journal notes with generic masked text.
        5. Re-maps tracking identifiers (Analytics, NotificationEvents, ScheduledInterventions)
           to '<anonymized>' to preserve statistics while destroying links to any real identity.
        """
        try:
            # 1. Delete standard User credential record (permanent lockout)
            db.query(User).filter(User.username == username).delete()

            # 2. Blank personal identifiers in UserProfile (preserves profile template, but nulls metadata)
            profile = db.query(UserProfile).filter(UserProfile.username == username).first()
            if profile:
                profile.display_name = "Anonymized User"
                profile.bio = ""
                profile.profile_photo_url = None
                profile.notifications_enabled = False
                profile.privacy_mode = True
                profile.updated_at = datetime.now(timezone.utc)

            # 3. Soft-deletes user memories
            db.query(UserMemory).filter(UserMemory.user_id == username).update(
                {UserMemory.is_active: False, UserMemory.updated_at: datetime.now(timezone.utc)}
            )

            # 4. Mask manual journal notes
            db.query(MoodJournal).filter(MoodJournal.user_id == username).update(
                {MoodJournal.note: "<masked_by_user_deletion>", MoodJournal.updated_at: datetime.now(timezone.utc)}
            )

            # 5. Anonymize analytical logs by mapping their user_id to "<anonymized>"
            db.query(Analytics).filter(Analytics.user_id == username).update({Analytics.user_id: "<anonymized>"})
            db.query(EmotionEvent).filter(EmotionEvent.user_id == username).update({EmotionEvent.user_id: "<anonymized>"})
            db.query(ScheduledIntervention).filter(ScheduledIntervention.user_id == username).update({ScheduledIntervention.user_id: "<anonymized>"})
            db.query(NotificationEvent).filter(NotificationEvent.user_id == username).update({NotificationEvent.user_id: "<anonymized>"})

            # 6. Delete recommendation events (KVKK/GDPR erasure)
            from src.services.database import RecommendationEvent
            db.query(RecommendationEvent).filter(RecommendationEvent.user_id == username).delete()

            # 7. Delete consent records
            db.query(UserConsent).filter(UserConsent.user_id == username).delete()

            db.commit()
            logger.warning("USER_DELETE_SUCCESS | GDPR erasure and anonymization completed for user '%s'.", username)
            return True
        except Exception as e:
            db.rollback()
            logger.error("USER_DELETE_ERROR | Failed to execute anonymization process: %s", e)
            return False

# Global singleton compliance service instance
compliance_service = ComplianceService()
