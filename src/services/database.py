import os
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func, case, Boolean, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from src.core.config import settings
from src.core.metrics import DATABASE_ERRORS_TOTAL

logger = logging.getLogger(__name__)

# Dynamic database URL configuration loaded centrally
DATABASE_URL = settings.DATABASE_URL

# url düzeltmesi
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# PostgreSQL ile çalışıyorsak "sqlite:///" ayarlarını yoksayacağız
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping=True eklenerek bayat (stale) bağlantılar önlenir, PostgreSQL için havuz yapılandırılır
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args=connect_args,
        pool_pre_ping=True
    )
else:
    engine = create_engine(
        DATABASE_URL, 
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Register database operational error tracker via SQLAlchemy events
@event.listens_for(engine, "handle_error")
def handle_db_error(exception_context):
    try:
        op = "statement_execute"
        if exception_context.is_disconnect:
            op = "disconnect"
        DATABASE_ERRORS_TOTAL.labels(operation=op).inc()
    except Exception:
        pass

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    role = Column(String, default="user", nullable=True)

class UserProfile(Base):
    __tablename__ = "user_profiles"
    username = Column(String, primary_key=True, index=True)
    display_name = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    profile_photo_url = Column(String, nullable=True)
    preferred_language = Column(String, default="tr")
    response_style = Column(String, default="supportive")
    theme_preference = Column(String, default="system")
    notifications_enabled = Column(Boolean, default=True)
    privacy_mode = Column(Boolean, default=False)
    answer_length_preference = Column(String, default="medium")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    user_text = Column(String)
    emotion = Column(String)
    risk = Column(String)
    language = Column(String)
    latency_ms = Column(Float)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UserMemory(Base):
    """Extended user memory table — Faz 10 Prompt 2 (Advanced Personal Context Engine).

    New columns (migration-safe, added via migrate_user_memory_schema()):
        memory_type        : 8-type semantic category (preference, coping_strategy, etc.)
        sensitivity        : 'low' | 'medium' | 'high'  — high is never injected into prompts
        last_reinforced_at : last time this memory was observed/confirmed
        decay_score        : 1.0=fresh, approaches 0.0 as time passes (lazy eval)
        is_active          : soft-delete flag; False = excluded from retrieval
    """
    __tablename__ = "user_memories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    memory_key = Column(String, index=True, nullable=False)
    memory_value = Column(String, nullable=False)
    emotion = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    source_message = Column(String, nullable=True)
    confidence = Column(Float, default=0.7)
    source = Column(String, default="auto_extraction")
    # ── Faz 10 P2 extended fields ──────────────────────────────────────────
    memory_type = Column(String, index=True, nullable=True)          # semantic category
    sensitivity = Column(String, default="low", nullable=True)       # low/medium/high
    last_reinforced_at = Column(DateTime(timezone=True), nullable=True)
    decay_score = Column(Float, default=1.0, nullable=True)          # 1.0=fresh
    is_active = Column(Boolean, default=True, nullable=True)         # soft-delete

def init_db(retries: int = 5, delay: int = 5):
    """
    Veritabanı bağlantısını ve tabloları başlatır.
    Eğer PostgreSQL kullanılıyorsa ve DB henüz hazır değilse belli sayıda tekrar dener.
    """
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database initialized and tables created successfully.")
            migrate_user_memory_schema()  # Faz 10 P2: add new columns if missing
            migrate_users_schema()  # Faz 10 P4: add role column if missing
            migrate_recommendation_schema()  # Faz 10 P7: recommendation_events table
            return
        except OperationalError as e:
            print(f"Warning: DB connection failed on attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                print("Error: Could not connect to the database after maximum retries.")
                raise e
        except Exception as e:
            print(f"Error initializing DB: {e}")
            raise e


def migrate_users_schema() -> None:
    """
    Migration-safe ALTER TABLE for users table adding 'role' column if not present.
    Ensures safe upgrades on existing SQLite and PostgreSQL production databases.
    """
    is_sqlite = DATABASE_URL.startswith("sqlite")
    try:
        with engine.connect() as conn:
            try:
                if is_sqlite:
                    # SQLite ADD COLUMN is safe via generic try/except
                    conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'user'"
                        )
                    )
                else:
                    # PostgreSQL: Check if column exists first
                    result = conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name='users' AND column_name='role'"
                        )
                    )
                    if result.fetchone() is None:
                        conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                "ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'user'"
                            )
                        )
                conn.commit()
                logger.info("MIGRATE | Added column 'role' to users table.")
            except Exception as col_err:
                conn.rollback()
                logger.debug("MIGRATE | Column 'role' likely already exists in users: %s", col_err)
    except Exception as migrate_err:
        logger.error("MIGRATE_ERROR | Failed to migrate users schema: %s", migrate_err)

def migrate_user_memory_schema() -> None:
    """
    Migration-safe ALTER TABLE for user_memories.

    Adds new Faz 10 P2 columns if they do not exist yet.
    Works for both SQLite and PostgreSQL without touching existing data.
    Safe to call multiple times (idempotent).
    """
    _NEW_COLUMNS = [
        ("memory_type",        "VARCHAR(64)",  None),
        ("sensitivity",        "VARCHAR(16)",  "'low'"),
        ("last_reinforced_at", "TIMESTAMP",    None),
        ("decay_score",        "FLOAT",        "1.0"),
        ("is_active",          "BOOLEAN",      "1"),   # 1=True for SQLite compat
    ]
    is_sqlite = DATABASE_URL.startswith("sqlite")
    try:
        with engine.connect() as conn:
            for col_name, col_type, default in _NEW_COLUMNS:
                try:
                    if is_sqlite:
                        # SQLite: ADD COLUMN is idempotent-safe via try/except
                        default_clause = f" DEFAULT {default}" if default else ""
                        conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                f"ALTER TABLE user_memories "
                                f"ADD COLUMN {col_name} {col_type}{default_clause}"
                            )
                        )
                    else:
                        # PostgreSQL: check information_schema first
                        result = conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_name='user_memories' "
                                f"AND column_name='{col_name}'"
                            )
                        )
                        if result.fetchone() is None:
                            default_clause = f" DEFAULT {default}" if default else ""
                            conn.execute(
                                __import__("sqlalchemy", fromlist=["text"]).text(
                                    f"ALTER TABLE user_memories "
                                    f"ADD COLUMN {col_name} {col_type}{default_clause}"
                                )
                            )
                    conn.commit()
                    logger.info("MIGRATE | Added column '%s' to user_memories", col_name)
                except Exception as col_err:
                    # Column already exists or non-critical error — safe to ignore
                    conn.rollback()
                    logger.debug("MIGRATE | Column '%s' likely already exists: %s", col_name, col_err)
    except Exception as migrate_err:
        logger.warning("MIGRATE | user_memories schema migration skipped: %s", migrate_err)


def migrate_recommendation_schema() -> None:
    """
    Migration-safe creation of the recommendation_events table.
    Uses Base.metadata.create_all which is idempotent (won't re-create if exists).
    Called from init_db() on every startup.
    Faz 10 Prompt 7.
    """
    try:
        # create_all is safe to call repeatedly — skips already existing tables
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(engine)
        if "recommendation_events" not in inspector.get_table_names():
            # Only create if missing
            RecommendationEvent.__table__.create(bind=engine, checkfirst=True)
            logger.info("MIGRATE | Created table 'recommendation_events'")
        else:
            logger.debug("MIGRATE | Table 'recommendation_events' already exists — skipped")
    except Exception as migrate_err:
        logger.warning("MIGRATE | recommendation_events schema migration skipped: %s", migrate_err)


def create_user(username: str, password_hash: str) -> bool:

    db = SessionLocal()
    try:
        user = User(username=username, password_hash=password_hash)
        db.add(user)
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger(__name__).error(f"Error creating user in DB: {e}")
        raise e
    finally:
        db.close()

def get_user_by_username(username: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return {"id": user.id, "username": user.username, "password_hash": user.password_hash}
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error getting user: {e}")
        raise e
    finally:
        db.close()

def save_analytics(user_id: str, user_text: str, emotion: str, risk: str, language: str, latency_ms: float):
    db = SessionLocal()
    try:
        # Enforce dynamic privacy masking based on user's active privacy profile
        privacy_mode = False
        profile = db.query(UserProfile).filter(UserProfile.username == user_id).first()
        if profile:
            privacy_mode = profile.privacy_mode

        # Enforce safety and privacy boundaries (no raw user text in log if privacy mode or crisis)
        if privacy_mode:
            user_text = "<masked_by_privacy_mode>"
        elif risk and str(risk).lower() in ["kriz", "1", "crisis"]:
            user_text = "<masked_due_to_crisis>"

        record = Analytics(
            user_id=user_id,
            user_text=user_text,
            emotion=emotion,
            risk=risk,
            language=language,
            latency_ms=latency_ms
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving analytics: {e}")
    finally:
        db.close()

def save_chat_message(user_id: str, role: str, content: str):
    db = SessionLocal()
    try:
        msg = ChatHistory(user_id=user_id, role=role, content=content)
        db.add(msg)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving chat message: {e}")
    finally:
        db.close()

def get_chat_history(user_id: str, limit: int = None) -> List[Dict]:
    db = SessionLocal()
    try:
        query = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).order_by(ChatHistory.timestamp.desc())
        if limit is not None:
            query = query.limit(limit)
        rows = query.all()
        # Sıralamayı yeniden eskiden yeniye çevirmek için reverse edilir
        rows.reverse()
        return [{"id": r.id, "role": r.role, "content": r.content, "timestamp": r.timestamp.isoformat()} for r in rows]
    except Exception as e:
        print(f"Error fetching max history: {e}")
        return []
    finally:
        db.close()

def get_analytics_summary():
    db = SessionLocal()
    try:
        total = db.query(Analytics).count()
        
        # Risk durumu (case-insensitive approach natively with SQLAlchemy)
        crisis_count = db.query(Analytics).filter(
            func.lower(Analytics.risk).in_(['kriz', '1', 'crisis'])
        ).count()
        crisis_rate = (crisis_count / total * 100) if total > 0 else 0
        
        # Emotion distribution
        emotion_rows = db.query(
            Analytics.emotion, 
            func.count(Analytics.emotion).label('count')
        ).group_by(Analytics.emotion).order_by(func.count(Analytics.emotion).desc()).all()
        
        top_emotion = emotion_rows[0].emotion if emotion_rows else "N/A"
        
        emotion_distribution = [{"emotion": r.emotion, "count": r.count} for r in emotion_rows]
        
        return {
            "total_messages": total,
            "crisis_rate": round(crisis_rate, 2),
            "top_emotion": top_emotion,
            "emotion_distribution": emotion_distribution
        }
    finally:
        db.close()

def get_analytics_timeline():
    db = SessionLocal()
    try:
        # PostgreSQL supports func.date(timestamp). SQLite supports it as well via type coercion.
        from sqlalchemy import cast, Date
        
        rows = db.query(
            cast(Analytics.timestamp, Date).label("date"),
            func.count(Analytics.id).label("count")
        ).group_by(cast(Analytics.timestamp, Date)).order_by(cast(Analytics.timestamp, Date).asc()).all()
        
        timeline = []
        for r in rows:
            # Datetime.date formatını string'e (YYYY-MM-DD) çevirerek döndürür
            timeline.append({
                "date": str(r.date),
                "count": r.count
            })
            
        return timeline
    finally:
        db.close()
def get_or_create_profile(username: str):
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.username == username).first()
        if not profile:
            # Create default profile
            profile = UserProfile(
                username=username,
                display_name=username,
                bio=""
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
        
        return {
            "username": profile.username,
            "display_name": profile.display_name,
            "bio": profile.bio,
            "profile_photo_url": profile.profile_photo_url,
            "preferred_language": profile.preferred_language,
            "response_style": profile.response_style,
            "theme_preference": profile.theme_preference,
            "notifications_enabled": profile.notifications_enabled,
            "privacy_mode": profile.privacy_mode,
            "answer_length_preference": profile.answer_length_preference,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error in get_or_create_profile: {e}")
        raise e
    finally:
        db.close()

def update_user_profile(username: str, data: dict):
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.username == username).first()
        if not profile:
            return None
        
        if "display_name" in data:
            profile.display_name = data["display_name"]
        if "bio" in data:
            profile.bio = data["bio"]
        if "profile_photo_url" in data:
            profile.profile_photo_url = data["profile_photo_url"]
        if "preferred_language" in data:
            profile.preferred_language = data["preferred_language"]
        if "response_style" in data:
            profile.response_style = data["response_style"]
        if "theme_preference" in data:
            profile.theme_preference = data["theme_preference"]
        if "notifications_enabled" in data:
            profile.notifications_enabled = data["notifications_enabled"]
        if "privacy_mode" in data:
            profile.privacy_mode = data["privacy_mode"]
        if "answer_length_preference" in data:
            profile.answer_length_preference = data["answer_length_preference"]
            
        profile.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(profile)
        
        return {
            "username": profile.username,
            "display_name": profile.displayName if hasattr(profile, "displayName") else profile.display_name,
            "bio": profile.bio,
            "profile_photo_url": profile.profile_photo_url,
            "preferred_language": profile.preferred_language,
            "response_style": profile.response_style,
            "theme_preference": profile.theme_preference,
            "notifications_enabled": profile.notifications_enabled,
            "privacy_mode": profile.privacy_mode,
            "answer_length_preference": profile.answer_length_preference,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating profile: {e}")
        raise e
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Persistent User Memory CRUD Helpers (Phase 7)
# ---------------------------------------------------------------------------

def create_memory(user_id: str, memory_key: str, memory_value: str, emotion: str = None, source_message: str = None, confidence: float = 0.7, source: str = "auto_extraction") -> bool:
    """Inserts a new memory record or updates (refreshes) if a duplicate exists."""
    db = SessionLocal()
    try:
        # Check if identical key and value exist for duplicate protection
        existing = db.query(UserMemory).filter(
            UserMemory.user_id == user_id,
            UserMemory.memory_key == memory_key,
            UserMemory.memory_value == memory_value
        ).first()
        
        if existing:
            existing.updated_at = datetime.now(timezone.utc)
            # Boost confidence on repeat observation
            existing.confidence = min(1.0, existing.confidence + 0.05)
            if emotion:
                existing.emotion = emotion
            if source_message:
                existing.source_message = source_message
        else:
            new_mem = UserMemory(
                user_id=user_id,
                memory_key=memory_key,
                memory_value=memory_value,
                emotion=emotion,
                source_message=source_message,
                confidence=confidence,
                source=source
            )
            db.add(new_mem)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_memory: {e}")
        return False
    finally:
        db.close()

def get_memories_for_user(user_id: str) -> List[Dict]:
    """Fetches all memories for a specific user from database."""
    db = SessionLocal()
    try:
        rows = db.query(UserMemory).filter(UserMemory.user_id == user_id).all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "memory_key": r.memory_key,
                "memory_value": r.memory_value,
                "emotion": r.emotion,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "source_message": r.source_message,
                "confidence": r.confidence,
                "source": r.source
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error in get_memories_for_user: {e}")
        return []
    finally:
        db.close()

def delete_memory(memory_id: int) -> bool:
    """Deletes a specific memory entry by unique identifier."""
    db = SessionLocal()
    try:
        mem = db.query(UserMemory).filter(UserMemory.id == memory_id).first()
        if mem:
            db.delete(mem)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error in delete_memory: {e}")
        return False
    finally:
        db.close()

def cleanup_old_memories(user_id: str, max_limit: int = 50) -> bool:
    """Trims oldest / lowest confidence memories once user hits max limit."""
    db = SessionLocal()
    try:
        # Fetch all user memories sorted by confidence desc, updated_at desc
        rows = db.query(UserMemory).filter(UserMemory.user_id == user_id).order_by(
            UserMemory.confidence.desc(),
            UserMemory.updated_at.desc()
        ).all()
        
        if len(rows) > max_limit:
            to_delete = rows[max_limit:]
            for mem in to_delete:
                db.delete(mem)
            db.commit()
            logger.info(f"MEMORY_CLEANUP | UserID: {user_id} | Trimmed {len(to_delete)} memories")
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error in cleanup_old_memories: {e}")
        return False
    finally:
        db.close()

def clear_user_memories_db(user_id: str) -> int:
    """Deletes all memory records for a specific user. Returns count of deleted entries."""
    db = SessionLocal()
    try:
        deleted_count = db.query(UserMemory).filter(UserMemory.user_id == user_id).delete()
        db.commit()
        return deleted_count
    except Exception as e:
        db.rollback()
        logger.error(f"Error in clear_user_memories_db: {e}")
        return 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Faz 10 P2: Advanced Memory CRUD Helpers
# ---------------------------------------------------------------------------

def get_memory_by_id_for_user(memory_id: int, user_id: str) -> Dict:
    """Fetches a single memory record with ownership validation.

    Returns the record dict if found AND belongs to user_id, else None.
    Prevents IDOR attacks — never access by ID alone.
    """
    db = SessionLocal()
    try:
        rec = db.query(UserMemory).filter(
            UserMemory.id == memory_id,
            UserMemory.user_id == user_id,
        ).first()
        if not rec:
            return None
        return _user_memory_to_dict(rec)
    except Exception as e:
        logger.error("Error in get_memory_by_id_for_user: %s", e)
        return None
    finally:
        db.close()


def delete_memory_for_user(memory_id: int, user_id: str) -> bool:
    """Soft-deletes a memory (sets is_active=False) after ownership validation.

    Returns True on success, False if record not found or doesn't belong to user.
    Uses soft delete to preserve audit trail; hard delete not performed.
    """
    db = SessionLocal()
    try:
        rec = db.query(UserMemory).filter(
            UserMemory.id == memory_id,
            UserMemory.user_id == user_id,
        ).first()
        if not rec:
            return False
        rec.is_active = False
        rec.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("MEMORY_DELETE | user=%s | id=%d | soft-deleted", user_id, memory_id)
        return True
    except Exception as e:
        db.rollback()
        logger.error("Error in delete_memory_for_user: %s", e)
        return False
    finally:
        db.close()


def get_active_memories_for_user(user_id: str) -> List[Dict]:
    """Fetches only active (not soft-deleted) memories for a user, ordered by relevance.

    Falls back to old behaviour (is_active IS NULL treated as active) so existing rows
    without the column set still appear.
    """
    db = SessionLocal()
    try:
        rows = db.query(UserMemory).filter(
            UserMemory.user_id == user_id,
            (UserMemory.is_active == True) | (UserMemory.is_active == None),  # noqa: E711
        ).order_by(
            UserMemory.confidence.desc(),
            UserMemory.updated_at.desc(),
        ).all()
        return [_user_memory_to_dict(r) for r in rows]
    except Exception as e:
        logger.error("Error in get_active_memories_for_user: %s", e)
        return []
    finally:
        db.close()


def refresh_memory_reinforcement(memory_id: int, user_id: str, confidence_boost: float = 0.05) -> bool:
    """Updates last_reinforced_at and boosts confidence for a memory.

    Called when an existing memory is confirmed by a new user message.
    Returns True on success.
    """
    db = SessionLocal()
    try:
        rec = db.query(UserMemory).filter(
            UserMemory.id == memory_id,
            UserMemory.user_id == user_id,
        ).first()
        if not rec:
            return False
        rec.last_reinforced_at = datetime.now(timezone.utc)
        rec.decay_score = min(1.0, (rec.decay_score or 1.0) * 1.1)  # reinforce lifts decay
        rec.confidence = min(1.0, rec.confidence + confidence_boost)
        rec.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error("Error in refresh_memory_reinforcement: %s", e)
        return False
    finally:
        db.close()


def update_memory_decay(memory_id: int, user_id: str, new_decay: float) -> bool:
    """Persists a new decay_score computed by the PersonalContextEngine."""
    db = SessionLocal()
    try:
        rec = db.query(UserMemory).filter(
            UserMemory.id == memory_id,
            UserMemory.user_id == user_id,
        ).first()
        if not rec:
            return False
        rec.decay_score = max(0.0, min(1.0, new_decay))
        rec.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error("Error in update_memory_decay: %s", e)
        return False
    finally:
        db.close()


def _user_memory_to_dict(r: UserMemory) -> Dict:
    """Converts a UserMemory ORM row to a serialisable dict (privacy-safe — no source_message)."""
    return {
        "id": r.id,
        "user_id": r.user_id,
        "memory_key": r.memory_key,
        "memory_value": r.memory_value,
        "emotion": r.emotion,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "confidence": r.confidence,
        "source": r.source,
        # Faz 10 P2 fields
        "memory_type": r.memory_type,
        "sensitivity": r.sensitivity or "low",
        "last_reinforced_at": r.last_reinforced_at.isoformat() if r.last_reinforced_at else None,
        "decay_score": r.decay_score if r.decay_score is not None else 1.0,
        "is_active": r.is_active if r.is_active is not None else True,
    }


# ---------------------------------------------------------------------------
# Emotion Timeline Analytics (Phase 7 - Prompt 2)
# ---------------------------------------------------------------------------

class EmotionEvent(Base):
    """
    Table definition for Emotion Events timeline tracking.
    This schema stores absolutely NO user chat text or messages,
    making it completely privacy-safe and crisis-safe by design.
    """
    __tablename__ = "emotion_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    message_id = Column(String, index=True, nullable=False)
    emotion = Column(String, nullable=False)
    risk = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source = Column(String, default="predict", nullable=False)


# ---------------------------------------------------------------------------
# Advanced Intervention Scheduler (Phase 8 - Prompt 1)
# ---------------------------------------------------------------------------

class ScheduledIntervention(Base):
    """
    Table definition for Advanced Intervention Scheduler.
    This schema stores scheduled wellness interventions for the user.
    """
    __tablename__ = "scheduled_interventions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    intervention_type = Column(String, nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False)  # Stored in UTC
    status = Column(String, default="pending", nullable=False)  # pending, delivered, skipped, cancelled
    priority = Column(String, default="medium", nullable=False)  # low, medium, high
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source_insight = Column(String, nullable=True)
    delivery_channel = Column(String, default="in_app", nullable=False)


class MoodJournal(Base):
    """
    Table definition for Mood Journal entries.
    Allows manual mood logging with optional note, intensity, and source tracking.
    """
    __tablename__ = "mood_journals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    mood = Column(String, nullable=False)  # happy, calm, anxious, sad, angry, tired, neutral
    intensity = Column(Integer, nullable=False)  # 1 to 5
    note = Column(String, nullable=True)  # Optional, max 500 chars
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    source = Column(String, default="journal", nullable=False)


class NotificationEvent(Base):
    """
    Table definition for Push Notification Intelligence events.
    Tracks all scheduled and delivered notifications for every user.
    """
    __tablename__ = "notification_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    notification_type = Column(String, nullable=False)  # scheduled_intervention, daily_report, weekly_report, mood_journal_reminder
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False)  # Stored in UTC
    status = Column(String, default="pending", nullable=False)  # pending, delivered, skipped, cancelled
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String, default="scheduler", nullable=False)


class SecurityAuditLog(Base):
    """
    Table definition for Salts-Encrypted Security Audit Logs.
    Complies fully with Kvkk/GDPR requirements by preserving no raw PII.
    """
    __tablename__ = "security_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)
    event_type = Column(String, index=True, nullable=False)
    ip_address_hash = Column(String, nullable=False)
    user_agent_hash = Column(String, nullable=False)
    request_id = Column(String, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    metadata_json = Column(String, nullable=True)
    severity = Column(String, default="INFO", nullable=False)


class UserConsent(Base):
    """
    Table definition for explicit User Consent Tracking.
    Default permissions are set to False (explicit opt-in mandate).
    """
    __tablename__ = "user_consents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False, unique=True)
    privacy_policy_version = Column(String, default="v1.0", nullable=False)
    terms_version = Column(String, default="v1.0", nullable=False)
    analytics_consent = Column(Boolean, default=False, nullable=False)
    wellness_insights_consent = Column(Boolean, default=False, nullable=False)
    notifications_consent = Column(Boolean, default=False, nullable=False)
    ai_processing_consent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RecommendationEvent(Base):
    """
    Table definition for Wellness Recommendation Events.
    Faz 10 Prompt 7 — Advanced Analytics & Recommendation Engine.

    Privacy design:
        - No raw chat text stored
        - No raw journal notes stored
        - reason field uses wellness-safe language only
        - metadata_json stores action configs (no PII)
    """
    __tablename__ = "recommendation_events"
    id = Column(String, primary_key=True, index=True)           # rec_<user>_<type>_<ts>
    user_id = Column(String, index=True, nullable=False)
    recommendation_type = Column(String, nullable=False)         # e.g. breathing_break
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    priority = Column(String, default="medium", nullable=False)  # low | medium | high
    priority_order = Column(Integer, default=1, nullable=False)  # 0=high,1=medium,2=low
    confidence = Column(Float, default=0.5, nullable=False)
    reason = Column(String, nullable=True)                       # wellness-safe explanation
    status = Column(String, default="active", nullable=False)    # active|dismissed|completed|expired
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String, default="recommendation_engine_v1", nullable=False)
    metadata_json = Column(String, nullable=True)                # actions list as JSON


def save_emotion_event(user_id: str, message_id: str, emotion: str, risk: str, source: str = "predict") -> bool:
    """Saves a new emotion timeline event to SQLite database securely."""
    db = SessionLocal()
    try:
        event = EmotionEvent(
            user_id=user_id,
            message_id=message_id,
            emotion=emotion,
            risk=risk,
            source=source
        )
        db.add(event)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error in save_emotion_event: {e}")
        return False
    finally:
        db.close()


def get_user_emotion_timeline(user_id: str, days: int = 7) -> List[Dict]:
    """Fetches user emotion timeline events sorted chronologically (ascending)."""
    db = SessionLocal()
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        events = db.query(EmotionEvent).filter(
            EmotionEvent.user_id == user_id,
            EmotionEvent.created_at >= cutoff
        ).order_by(EmotionEvent.created_at.asc()).all()

        return [
            {
                "id": e.id,
                "message_id": e.message_id,
                "emotion": e.emotion,
                "risk": e.risk,
                "created_at": e.created_at.isoformat(),
                "source": e.source
            }
            for e in events
        ]
    except Exception as e:
        logger.error(f"Error in get_user_emotion_timeline: {e}")
        return []
    finally:
        db.close()


def get_user_emotion_summary(user_id: str, days: int = 7) -> Dict:
    """
    Computes summary data of emotional events for a specific user.
    Uses in-memory date calculations to remain 100% database-agnostic.
    """
    db = SessionLocal()
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        events = db.query(EmotionEvent).filter(
            EmotionEvent.user_id == user_id,
            EmotionEvent.created_at >= cutoff
        ).order_by(EmotionEvent.created_at.asc()).all()

        total_messages = len(events)
        emotion_dist = {}
        crisis_count = 0
        daily_map = {}

        for e in events:
            em = e.emotion or "neutral"
            emotion_dist[em] = emotion_dist.get(em, 0) + 1

            if e.risk and str(e.risk).lower() in ["kriz", "1", "crisis"]:
                crisis_count += 1

            # Daily grouping using local-date format
            date_str = e.created_at.strftime("%Y-%m-%d")
            if date_str not in daily_map:
                daily_map[date_str] = {"emotions": {}, "total_count": 0}

            daily_map[date_str]["total_count"] += 1
            daily_map[date_str]["emotions"][em] = daily_map[date_str]["emotions"].get(em, 0) + 1

        dominant_emotion = None
        if emotion_dist:
            dominant_emotion = max(emotion_dist, key=emotion_dist.get)
        else:
            dominant_emotion = "Nötr"

        # Transform to sorted date array
        daily_trend = []
        for date_str in sorted(daily_map.keys()):
            daily_trend.append({
                "date": date_str,
                "emotions": daily_map[date_str]["emotions"],
                "total_count": daily_map[date_str]["total_count"]
            })

        return {
            "total_messages": total_messages,
            "emotion_distribution": emotion_dist,
            "dominant_emotion": dominant_emotion,
            "crisis_count": crisis_count,
            "daily_trend": daily_trend
        }
    except Exception as e:
        logger.error(f"Error in get_user_emotion_summary: {e}")
        return {
            "total_messages": 0,
            "emotion_distribution": {},
            "dominant_emotion": "Nötr",
            "crisis_count": 0,
            "daily_trend": []
        }
    finally:
        db.close()


def save_scheduled_intervention(user_id: str, intervention_type: str, scheduled_for: datetime, status: str = "pending", priority: str = "medium", source_insight: str = None, delivery_channel: str = "in_app") -> bool:
    """Saves a new scheduled intervention to the database."""
    db = SessionLocal()
    try:
        record = ScheduledIntervention(
            user_id=user_id,
            intervention_type=intervention_type,
            scheduled_for=scheduled_for,
            status=status,
            priority=priority,
            source_insight=source_insight,
            delivery_channel=delivery_channel
        )
        db.add(record)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving scheduled intervention: {e}")
        return False
    finally:
        db.close()


def get_scheduled_interventions_for_user(user_id: str) -> List[Dict]:
    """Fetches all scheduled interventions for a specific user, sorted chronologically."""
    db = SessionLocal()
    try:
        rows = db.query(ScheduledIntervention).filter(
            ScheduledIntervention.user_id == user_id
        ).order_by(ScheduledIntervention.scheduled_for.asc()).all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "type": r.intervention_type,
                "scheduled_for": r.scheduled_for.isoformat(),
                "status": r.status,
                "priority": r.priority,
                "created_at": r.created_at.isoformat(),
                "source_insight": r.source_insight,
                "delivery_channel": r.delivery_channel
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching scheduled interventions: {e}")
        return []
    finally:
        db.close()


def cancel_pending_interventions(user_id: str) -> bool:
    """Cancels (or marks as cancelled) all pending scheduled interventions for a user."""
    db = SessionLocal()
    try:
        pending = db.query(ScheduledIntervention).filter(
            ScheduledIntervention.user_id == user_id,
            ScheduledIntervention.status == "pending"
        ).all()
        for record in pending:
            record.status = "cancelled"
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling pending interventions: {e}")
        return False
    finally:
        db.close()


def save_mood_journal(user_id: str, mood: str, intensity: int, note: str = None, source: str = "journal") -> MoodJournal:
    """Saves a manual user mood journal entry securely to the database."""
    db = SessionLocal()
    try:
        entry = MoodJournal(
            user_id=user_id,
            mood=mood,
            intensity=intensity,
            note=note,
            source=source
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving mood journal: {e}")
        raise e
    finally:
        db.close()


def get_mood_journals_for_user(user_id: str, days: int = 7) -> list:
    """Retrieves all mood journal entries in the requested timeframe (in days) sorted chronologically descending."""
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = db.query(MoodJournal).filter(
            MoodJournal.user_id == user_id,
            MoodJournal.created_at >= cutoff
        ).order_by(MoodJournal.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "mood": r.mood,
                "intensity": r.intensity,
                "note": r.note,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "source": r.source
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching mood journals: {e}")
        return []
    finally:
        db.close()


def delete_mood_journal(user_id: str, journal_id: int) -> bool:
    """Deletes a mood journal entry securely ensuring ownership validation."""
    db = SessionLocal()
    try:
        entry = db.query(MoodJournal).filter(
            MoodJournal.user_id == user_id,
            MoodJournal.id == journal_id
        ).first()
        if not entry:
            return False
        db.delete(entry)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting mood journal: {e}")
        return False
    finally:
        db.close()


def save_notification_event(
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    scheduled_for: datetime,
    status: str = "pending",
    source: str = "scheduler"
) -> NotificationEvent:
    """Saves a notification event entry to the database."""
    db = SessionLocal()
    try:
        event = NotificationEvent(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            scheduled_for=scheduled_for,
            status=status,
            source=source
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving notification event: {e}")
        raise e
    finally:
        db.close()


def get_notification_events_for_user(user_id: str) -> list:
    """Retrieves all notification events for a specific user ordered by scheduled_for descending."""
    db = SessionLocal()
    try:
        rows = db.query(NotificationEvent).filter(
            NotificationEvent.user_id == user_id
        ).order_by(NotificationEvent.scheduled_for.desc()).all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "notification_type": r.notification_type,
                "title": r.title,
                "body": r.body,
                "scheduled_for": r.scheduled_for.isoformat(),
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
                "source": r.source
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching notification events: {e}")
        return []
    finally:
        db.close()


def mark_notification_as_delivered(user_id: str, notification_id: int) -> bool:
    """Marks a pending notification event as delivered securely confirming ownership."""
    db = SessionLocal()
    try:
        event = db.query(NotificationEvent).filter(
            NotificationEvent.user_id == user_id,
            NotificationEvent.id == notification_id
        ).first()
        if not event:
            return False
        event.status = "delivered"
        event.delivered_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error marking notification delivered: {e}")
        return False
    finally:
        db.close()


def cancel_pending_notifications_for_type(user_id: str, notification_type: str) -> bool:
    """Cancels (marks as cancelled) all pending notification events for a user and type."""
    db = SessionLocal()
    try:
        pending = db.query(NotificationEvent).filter(
            NotificationEvent.user_id == user_id,
            NotificationEvent.notification_type == notification_type,
            NotificationEvent.status == "pending"
        ).all()
        for record in pending:
            record.status = "cancelled"
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling pending notifications: {e}")
        return False
    finally:
        db.close()


def get_all_usernames() -> List[str]:
    """Retrieves all registered user usernames securely."""
    db = SessionLocal()
    try:
        users = db.query(User.username).all()
        return [u.username for u in users]
    except Exception as e:
        logger.error(f"DATABASE_HELPER | Failed to fetch all usernames: {e}")
        return []
    finally:
        db.close()


def cleanup_old_emotion_events(days: int = 30) -> int:
    """Purges emotion timeline events older than specified days to keep the DB optimized."""
    db = SessionLocal()
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = db.query(EmotionEvent).filter(EmotionEvent.created_at < cutoff).delete()
        db.commit()
        return deleted
    except Exception as e:
        db.rollback()
        logger.error(f"DATABASE_HELPER | Failed to clean up old emotion events: {e}")
        return 0
    finally:
        db.close()



