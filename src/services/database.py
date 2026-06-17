import os
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func, case, Boolean, event, ForeignKey, Numeric
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
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
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
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

class PsychologistProfile(Base):
    __tablename__ = "psychologist_profiles"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    title = Column(String, nullable=False)
    specialty = Column(String, nullable=False)
    bio = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PsychologistAvailability(Base):
    __tablename__ = "psychologist_availability"
    id = Column(Integer, primary_key=True, index=True)
    psychologist_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False) # 0-6 (0=Monday, 6=Sunday)
    start_time = Column(String, nullable=False) # "HH:MM"
    end_time = Column(String, nullable=False) # "HH:MM"
    slot_duration_minutes = Column(Integer, default=60, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    blocked_dates = Column(String, nullable=True) # comma-separated list of YYYY-MM-DD
    custom_exceptions = Column(String, nullable=True) # custom JSON format configuration
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    psychologist = relationship("User", foreign_keys=[psychologist_id])


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    psychologist_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    appointment_date = Column(String, nullable=False)
    appointment_time = Column(String, nullable=False)
    status = Column(String, default="scheduled", nullable=False)
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

class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    email = Column(String, index=True, nullable=False)
    verification_code = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    failed_attempts = Column(Integer, default=0, nullable=False)

def init_db(retries: int = 5, delay: int = 5):
    """
    Veritabanı bağlantısını ve tabloları başlatır.
    Eğer PostgreSQL kullanılıyorsa ve DB henüz hazır değilse belli sayıda tekrar dener.
    """
    logger.info(f"DATABASE | Initializing database connection. Active URL: {DATABASE_URL}")
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database initialized and tables created successfully.")
            migrate_user_memory_schema()  # Faz 10 P2: add new columns if missing
            migrate_users_schema()  # Faz 10 P4: add role column if missing
            migrate_users_schema_phase2a() # Phase 2A: add email and full_name columns if missing
            migrate_recommendation_schema()  # Faz 10 P7: recommendation_events table
            migrate_password_reset_codes_schema()  # Phase 11.0A: password_reset_codes table
            migrate_emotion_events_schema()  # Sprint 2: add subtype column if missing
            migrate_emotion_events_schema_sprint3()  # Sprint 3: add strategy column if missing
            migrate_emotion_events_schema_sprint4()  # Sprint 4: add variation column if missing
            seed_plans()  # Seed default plans
            seed_admin()  # Seed default admin user
            seed_test_user()  # Seed default test user denizdennasnas@gmail.com
            seed_psychologists()  # Seed default psychologists and clean up test/orphaned profiles
            logger.info(f"DATABASE | Database initialized successfully. Active URL: {DATABASE_URL}")
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

def migrate_users_schema_phase2a() -> None:
    """
    Migration-safe ALTER TABLE for users table adding 'email' and 'full_name' columns if not present.
    """
    is_sqlite = DATABASE_URL.startswith("sqlite")
    try:
        with engine.connect() as conn:
            # 1. Add email column
            try:
                if is_sqlite:
                    conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "ALTER TABLE users ADD COLUMN email VARCHAR(255)"
                        )
                    )
                else:
                    result = conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name='users' AND column_name='email'"
                        )
                    )
                    if result.fetchone() is None:
                        conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                "ALTER TABLE users ADD COLUMN email VARCHAR(255)"
                            )
                        )
            except Exception as e:
                pass

            # 2. Add full_name column
            try:
                if is_sqlite:
                    conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "ALTER TABLE users ADD COLUMN full_name VARCHAR(255)"
                        )
                    )
                else:
                    result = conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name='users' AND column_name='full_name'"
                        )
                    )
                    if result.fetchone() is None:
                        conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                "ALTER TABLE users ADD COLUMN full_name VARCHAR(255)"
                            )
                        )
            except Exception as e:
                pass
            conn.commit()
            logger.info("MIGRATE | Phase 2A database user schema completed.")
    except Exception as migrate_err:
        logger.error("MIGRATE_ERROR | Failed to migrate users schema for phase 2a: %s", migrate_err)

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


def migrate_password_reset_codes_schema() -> None:
    """
    Migration-safe table creation for password_reset_codes.
    """
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(engine)
        if "password_reset_codes" not in inspector.get_table_names():
            PasswordResetCode.__table__.create(bind=engine, checkfirst=True)
            logger.info("MIGRATE | Created table 'password_reset_codes'")
        else:
            logger.debug("MIGRATE | Table 'password_reset_codes' already exists — skipped")
    except Exception as migrate_err:
        logger.warning("MIGRATE | password_reset_codes schema migration failed: %s", migrate_err)


def migrate_emotion_events_schema() -> None:
    """
    Migration-safe ALTER TABLE for emotion_events table adding 'subtype' column if not present.
    """
    is_sqlite = DATABASE_URL.startswith("sqlite")
    try:
        with engine.connect() as conn:
            try:
                if is_sqlite:
                    # SQLite ADD COLUMN is safe via generic try/except
                    conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "ALTER TABLE emotion_events ADD COLUMN subtype VARCHAR(64) DEFAULT NULL"
                        )
                    )
                else:
                    # PostgreSQL: Check if column exists first
                    result = conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name='emotion_events' AND column_name='subtype'"
                        )
                    )
                    if result.fetchone() is None:
                        conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                "ALTER TABLE emotion_events ADD COLUMN subtype VARCHAR(64) DEFAULT NULL"
                            )
                        )
                conn.commit()
                logger.info("MIGRATE | Added column 'subtype' to emotion_events table.")
            except Exception as col_err:
                conn.rollback()
                logger.debug("MIGRATE | Column 'subtype' likely already exists in emotion_events: %s", col_err)
    except Exception as migrate_err:
        logger.error("MIGRATE_ERROR | Failed to migrate emotion_events schema: %s", migrate_err)


def migrate_emotion_events_schema_sprint3() -> None:
    """
    Migration-safe ALTER TABLE for emotion_events table adding 'strategy' column if not present.
    """
    is_sqlite = DATABASE_URL.startswith("sqlite")
    try:
        with engine.connect() as conn:
            try:
                if is_sqlite:
                    # SQLite ADD COLUMN is safe via generic try/except
                    conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "ALTER TABLE emotion_events ADD COLUMN strategy VARCHAR(64) DEFAULT NULL"
                        )
                    )
                else:
                    # PostgreSQL: Check if column exists first
                    result = conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name='emotion_events' AND column_name='strategy'"
                        )
                    )
                    if result.fetchone() is None:
                        conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                "ALTER TABLE emotion_events ADD COLUMN strategy VARCHAR(64) DEFAULT NULL"
                            )
                        )
                conn.commit()
                logger.info("MIGRATE | Added column 'strategy' to emotion_events table.")
            except Exception as col_err:
                conn.rollback()
                logger.debug("MIGRATE | Column 'strategy' likely already exists in emotion_events: %s", col_err)
    except Exception as migrate_err:
        logger.error("MIGRATE_ERROR | Failed to migrate emotion_events schema for strategy: %s", migrate_err)


def migrate_emotion_events_schema_sprint4() -> None:
    """
    Migration-safe ALTER TABLE for emotion_events table adding 'variation' column if not present.
    """
    is_sqlite = DATABASE_URL.startswith("sqlite")
    try:
        with engine.connect() as conn:
            try:
                if is_sqlite:
                    # SQLite ADD COLUMN is safe via generic try/except
                    conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "ALTER TABLE emotion_events ADD COLUMN variation VARCHAR(64) DEFAULT NULL"
                        )
                    )
                else:
                    # PostgreSQL: Check if column exists first
                    result = conn.execute(
                        __import__("sqlalchemy", fromlist=["text"]).text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name='emotion_events' AND column_name='variation'"
                        )
                    )
                    if result.fetchone() is None:
                        conn.execute(
                            __import__("sqlalchemy", fromlist=["text"]).text(
                                "ALTER TABLE emotion_events ADD COLUMN variation VARCHAR(64) DEFAULT NULL"
                            )
                        )
                conn.commit()
                logger.info("MIGRATE | Added column 'variation' to emotion_events table.")
            except Exception as col_err:
                conn.rollback()
                logger.debug("MIGRATE | Column 'variation' likely already exists in emotion_events: %s", col_err)
    except Exception as migrate_err:
        logger.error("MIGRATE_ERROR | Failed to migrate emotion_events schema for variation: %s", migrate_err)


def create_user(username: str, password_hash: str, email: Optional[str] = None, full_name: Optional[str] = None, role: str = "user") -> bool:

    db = SessionLocal()
    try:
        user = User(username=username, password_hash=password_hash, email=email, full_name=full_name, role=role)
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
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "password_hash": user.password_hash,
                "role": user.role
            }
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error getting user: {e}")
        raise e
    finally:
        db.close()

def get_user_by_email(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "password_hash": user.password_hash,
                "role": user.role
            }
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error getting user by email: {e}")
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
        
        user = db.query(User).filter(User.username == username).first()
        psychologist_profile = None
        if user and user.role == "psychologist":
            psychologist_profile = db.query(PsychologistProfile).filter(PsychologistProfile.user_id == user.id).first()

        return {
            "username": profile.username,
            "display_name": profile.display_name,
            "bio": psychologist_profile.bio if psychologist_profile else profile.bio,
            "profile_photo_url": profile.profile_photo_url,
            "preferred_language": profile.preferred_language,
            "response_style": profile.response_style,
            "theme_preference": profile.theme_preference,
            "notifications_enabled": profile.notifications_enabled,
            "privacy_mode": profile.privacy_mode,
            "answer_length_preference": profile.answer_length_preference,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
            "id": user.id if user else None,
            "email": user.email if user else None,
            "full_name": user.full_name if user else None,
            "role": user.role if user else "user",
            "title": psychologist_profile.title if psychologist_profile else None,
            "specialty": psychologist_profile.specialty if psychologist_profile else None,
            "status": psychologist_profile.status if psychologist_profile else None,
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
    subtype = Column(String, nullable=True)
    strategy = Column(String, nullable=True)
    variation = Column(String, nullable=True)


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


def save_emotion_event(user_id: str, message_id: str, emotion: str, risk: str, source: str = "predict", subtype: Optional[str] = None, strategy: Optional[str] = None, variation: Optional[str] = None) -> bool:
    """Saves a new emotion timeline event to SQLite database securely."""
    db = SessionLocal()
    try:
        event = EmotionEvent(
            user_id=user_id,
            message_id=message_id,
            emotion=emotion,
            risk=risk,
            source=source,
            subtype=subtype,
            strategy=strategy,
            variation=variation
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
                "source": e.source,
                "subtype": e.subtype,
                "strategy": e.strategy,
                "variation": e.variation
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


# ── Subscription and Payment System Enums & Models ─────────────────────────

import enum
from sqlalchemy import Enum as SQLEnum

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    CANCELED = "canceled"
    EXPIRED = "expired"
    PAYMENT_FAILED = "payment_failed"
    PENDING = "pending"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELED = "canceled"

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(32), unique=True, index=True, nullable=False)
    price_lira = Column(Numeric(10, 2), nullable=False)
    billing_interval = Column(String(16), default="monthly", nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.username"), index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.INACTIVE, nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    provider_subscription_id = Column(String(255), unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    plan = relationship("SubscriptionPlan")

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.username"), index=True, nullable=False)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id"), nullable=True)
    provider_transaction_id = Column(String(255), unique=True, index=True, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="TRY", nullable=False)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = Column(String(64), nullable=True)
    idempotency_key = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    subscription = relationship("UserSubscription")

def seed_plans():
    """Seeds default subscription plans if they do not exist."""
    db = SessionLocal()
    try:
        # Check if plans are already seeded
        if db.query(SubscriptionPlan).count() == 0:
            plans = [
                SubscriptionPlan(
                    name="free",
                    price_lira=0.00,
                    billing_interval="monthly",
                    description="Sınırlı günlük yapay zeka sohbeti, temel duygu durum analizi.",
                    is_active=True
                ),
                SubscriptionPlan(
                    name="premium",
                    price_lira=settings.PRICE_PREMIUM_TRY,
                    billing_interval="monthly",
                    description="Sınırsız yapay zeka sohbeti, haftalık wellness raporları, öncelikli uzman randevuları.",
                    is_active=True
                ),
                SubscriptionPlan(
                    name="professional_support",
                    price_lira=settings.PRICE_PROFESSIONAL_TRY,
                    billing_interval="monthly",
                    description="Tüm premium özellikleri, ayda 2 görüntülü uzman seansı, 7/24 öncelikli destek.",
                    is_active=True
                )
            ]
            db.add_all(plans)
            db.commit()
            logger.info("SEED | Seeded default subscription plans.")
    except Exception as e:
        db.rollback()
        logger.error(f"SEED | Error seeding plans: {e}")
    finally:
        db.close()

def create_psychologist(username: str, password_hash: str, email: str, full_name: str, title: str, specialty: str, bio: str) -> bool:
    db = SessionLocal()
    try:
        user = User(username=username, password_hash=password_hash, email=email, full_name=full_name, role="psychologist")
        db.add(user)
        db.flush()
        
        profile = PsychologistProfile(user_id=user.id, title=title, specialty=specialty, bio=bio, status="pending")
        db.add(profile)
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating psychologist in DB: {e}")
        raise e
    finally:
        db.close()

def get_approved_psychologists():
    db = SessionLocal()
    try:
        results = db.query(User, PsychologistProfile).join(
            PsychologistProfile, User.id == PsychologistProfile.user_id
        ).filter(PsychologistProfile.status == "approved").all()
        
        output = []
        for user, profile in results:
            output.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "title": profile.title,
                "specialty": profile.specialty,
                "bio": profile.bio,
                "status": profile.status
            })
        return output
    except Exception as e:
        logger.error(f"Error getting approved psychologists: {e}")
        return []
    finally:
        db.close()

def approve_psychologist(username: str) -> bool:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False
        profile = db.query(PsychologistProfile).filter(PsychologistProfile.user_id == user.id).first()
        if not profile:
            return False
        profile.status = "approved"
        profile.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving psychologist: {e}")
        return False
    finally:
        db.close()

def create_appointment(username: str, psychologist_username: str, date_str: str, time_str: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")
        
        psy = db.query(User).filter(User.username == psychologist_username).first()
        if not psy:
            raise ValueError("Psikolog bulunamadı.")
        
        if psy.role != "psychologist":
            raise ValueError("Seçilen kullanıcı psikolog rolüne sahip değil.")
        
        profile = db.query(PsychologistProfile).filter(PsychologistProfile.user_id == psy.id).first()
        if not profile or profile.status != "approved":
            raise ValueError("Psikolog henüz onaylanmamış.")
        
        # 1. Past date/time check (Istanbul/Turkey timezone safe)
        from src.services.intervention_scheduler import ISTANBUL_TZ
        now_local = datetime.now(ISTANBUL_TZ)
        current_date_str = now_local.strftime("%Y-%m-%d")
        if date_str < current_date_str:
            raise ValueError("Geçmiş bir tarihe randevu alınamaz.")
        if date_str == current_date_str:
            current_time_str = now_local.strftime("%H:%M")
            if time_str <= current_time_str:
                raise ValueError("Geçmiş bir saate randevu alınamaz.")
                
        # 2. Weekday matching
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Geçersiz tarih formatı. YYYY-MM-DD olmalıdır.")
        day_of_week = dt.weekday() # 0-6 (0=Monday, 6=Sunday)
        
        # 3. Retrieve active availabilities for the psychologist on this day
        availabilities = db.query(PsychologistAvailability).filter(
            PsychologistAvailability.psychologist_id == psy.id,
            PsychologistAvailability.day_of_week == day_of_week,
            PsychologistAvailability.is_active == True
        ).all()
        
        matched = False
        for av in availabilities:
            def parse_t(t):
                h, m = map(int, t.split(":"))
                return h * 60 + m
            s_min = parse_t(av.start_time)
            e_min = parse_t(av.end_time)
            req_min = parse_t(time_str)
            
            # Generate valid slot start times
            slots = []
            current = s_min
            while current + av.slot_duration_minutes <= e_min:
                slots.append(current)
                current += av.slot_duration_minutes
                
            if req_min in slots:
                matched = True
                break
                
        if not matched:
            raise ValueError("Seçilen saat uzman psikoloğun müsaitlik saatleri dışındadır.")
            
        # 4. Check if slot is already booked (Scheduled status)
        existing_booking = db.query(Appointment).filter(
            Appointment.psychologist_id == psy.id,
            Appointment.appointment_date == date_str,
            Appointment.appointment_time == time_str,
            Appointment.status == "scheduled"
        ).first()
        if existing_booking:
            raise ValueError("Bu saat dilimi zaten dolu.")
        
        appt = Appointment(
            user_id=user.id,
            psychologist_id=psy.id,
            appointment_date=date_str,
            appointment_time=time_str,
            status="scheduled"
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)
        return {
            "id": appt.id,
            "user_id": appt.user_id,
            "psychologist_id": appt.psychologist_id,
            "appointment_date": appt.appointment_date,
            "appointment_time": appt.appointment_time,
            "status": appt.status,
            "created_at": appt.created_at.isoformat() if appt.created_at else None,
            "psychologist_name": psy.full_name or psy.username,
            "psychologist_specialty": profile.specialty
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def get_appointments_for_user(username: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return []
        
        if user.role == "psychologist":
            # Psychologist sees appointments assigned to them
            results = db.query(Appointment, User).join(
                User, User.id == Appointment.user_id
            ).filter(
                Appointment.psychologist_id == user.id
            ).all()
            
            output = []
            for appt, patient in results:
                output.append({
                    "id": appt.id,
                    "user_id": appt.user_id,
                    "psychologist_id": appt.psychologist_id,
                    "appointment_date": appt.appointment_date,
                    "appointment_time": appt.appointment_time,
                    "status": appt.status,
                    "created_at": appt.created_at.isoformat() if appt.created_at else None,
                    "patient_name": patient.full_name or patient.username,
                    "patient_username": patient.username,
                    "patient_email": patient.email
                })
            return output
        else:
            # User sees their own booked appointments
            results = db.query(Appointment, User, PsychologistProfile).join(
                User, User.id == Appointment.psychologist_id
            ).join(
                PsychologistProfile, PsychologistProfile.user_id == User.id
            ).filter(
                Appointment.user_id == user.id
            ).all()
            
            output = []
            for appt, psy, profile in results:
                output.append({
                    "id": appt.id,
                    "user_id": appt.user_id,
                    "psychologist_id": appt.psychologist_id,
                    "appointment_date": appt.appointment_date,
                    "appointment_time": appt.appointment_time,
                    "status": appt.status,
                    "created_at": appt.created_at.isoformat() if appt.created_at else None,
                    "psychologist_name": psy.full_name or psy.username,
                    "psychologist_specialty": profile.specialty
                })
            return output
    except Exception as e:
        logger.error(f"Error getting appointments: {e}")
        return []
    finally:
        db.close()

def cancel_appointment_in_db(username: str, appointment_id: int) -> bool:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False
        
        appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appt:
            return False
        
        if user.role == "psychologist":
            if appt.psychologist_id != user.id:
                return False
        else:
            if appt.user_id != user.id:
                return False
        
        appt.status = "cancelled"
        appt.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling appointment: {e}")
        return False
    finally:
        db.close()


def seed_admin():
    """Seeds default admin user or updates existing if wrong."""
    from src.services.auth import get_password_hash, verify_password
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        hashed_pw = get_password_hash("psiko_secret123")
        if not admin_user:
            user = User(
                username="admin",
                password_hash=hashed_pw,
                email="admin",
                full_name="Admin",
                role="admin"
            )
            db.add(user)
            db.commit()
            logger.info("SEED | Seeded default admin user.")
        else:
            updated = False
            if admin_user.email != "admin":
                admin_user.email = "admin"
                updated = True
            if admin_user.role != "admin":
                admin_user.role = "admin"
                updated = True
            if admin_user.full_name != "Admin":
                admin_user.full_name = "Admin"
                updated = True
            if not verify_password("psiko_secret123", admin_user.password_hash):
                admin_user.password_hash = hashed_pw
                updated = True
            if updated:
                db.commit()
                logger.info("SEED | Updated existing admin user to match defaults.")
    except Exception as e:
        db.rollback()
        logger.error(f"SEED | Error seeding/updating admin user: {e}")
    finally:
        db.close()

def seed_test_user():
    """Seeds a default test user or updates existing user to match defaults."""
    from src.services.auth import get_password_hash, verify_password
    db = SessionLocal()
    try:
        test_user = db.query(User).filter(User.email == "denizdennasnas@gmail.com").first()
        hashed_pw = get_password_hash("password123")
        if not test_user:
            user = User(
                username="deniz",
                password_hash=hashed_pw,
                email="denizdennasnas@gmail.com",
                full_name="Deniz Nas",
                role="user"
            )
            db.add(user)
            db.commit()
            logger.info("SEED | Seeded default test user denizdennasnas@gmail.com.")
        else:
            updated = False
            if test_user.username != "deniz":
                test_user.username = "deniz"
                updated = True
            if test_user.full_name != "Deniz Nas":
                test_user.full_name = "Deniz Nas"
                updated = True
            if test_user.role != "user":
                test_user.role = "user"
                updated = True
            if not verify_password("password123", test_user.password_hash):
                test_user.password_hash = hashed_pw
                updated = True
            if updated:
                db.commit()
                logger.info("SEED | Updated existing test user denizdennasnas@gmail.com to match defaults.")
    except Exception as e:
        db.rollback()
        logger.error(f"SEED | Error seeding test user: {e}")
    finally:
        db.close()


def seed_psychologists():
    """Seeds default approved psychologists and cleans up orphaned or stale mock profiles."""
    from src.services.auth import get_password_hash, verify_password
    db = SessionLocal()
    try:
        default_psychologists = [
            {
                "username": "antepogullari",
                "email": "antepogullari@gmail.com",
                "full_name": "Betül Akarçay",
                "title": "Doçent Psikolog",
                "specialty": "Bilişsel Terapi",
                "bio": "Merhaba, ben Doçent Psikolog Betül Akarçay. Bilişsel davranışçı terapi alanında uzmanım.",
                "status": "approved"
            },
            {
                "username": "ahmet_yilmaz",
                "email": "ahmet_yilmaz@example.com",
                "full_name": "Ahmet Yılmaz",
                "title": "Uzm. Psk.",
                "specialty": "Kaygı",
                "bio": "Merhaba, ben Uzman Psikolog Ahmet Yılmaz. Kaygı bozuklukları ve panik atak üzerinde çalışıyorum.",
                "status": "approved"
            }
        ]
        
        for psy_data in default_psychologists:
            user = db.query(User).filter(User.username == psy_data["username"]).first()
            hashed_pw = get_password_hash("password123")
            if not user:
                user = User(
                    username=psy_data["username"],
                    password_hash=hashed_pw,
                    email=psy_data["email"],
                    full_name=psy_data["full_name"],
                    role="psychologist"
                )
                db.add(user)
                db.flush()
            else:
                user.role = "psychologist"
                user.full_name = psy_data["full_name"]
                user.email = psy_data["email"]
                if not verify_password("password123", user.password_hash):
                    user.password_hash = hashed_pw
            
            profile = db.query(PsychologistProfile).filter(PsychologistProfile.user_id == user.id).first()
            if not profile:
                profile = PsychologistProfile(
                    user_id=user.id,
                    title=psy_data["title"],
                    specialty=psy_data["specialty"],
                    bio=psy_data["bio"],
                    status=psy_data["status"]
                )
                db.add(profile)
            else:
                profile.title = psy_data["title"]
                profile.specialty = psy_data["specialty"]
                profile.bio = psy_data["bio"]
                profile.status = psy_data["status"]
        
        # Clean up any psychologist profiles that don't belong to a psychologist user or are generated mock testusers
        all_profiles = db.query(PsychologistProfile).all()
        for p in all_profiles:
            u = db.query(User).filter(User.id == p.user_id).first()
            if not u or u.role != "psychologist" or "testuser_" in u.username.lower() or "patient_" in u.username.lower():
                db.delete(p)
                
        db.commit()
        logger.info("SEED | Seeded default psychologists and cleaned up orphaned/test profiles.")
    except Exception as e:
        db.rollback()
        logger.error(f"SEED | Error seeding psychologists: {e}")
    finally:
        db.close()


def get_pending_psychologists():
    db = SessionLocal()
    try:
        results = db.query(User, PsychologistProfile).join(
            PsychologistProfile, User.id == PsychologistProfile.user_id
        ).filter(PsychologistProfile.status == "pending").all()
        
        output = []
        for user, profile in results:
            output.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "title": profile.title,
                "specialty": profile.specialty,
                "bio": profile.bio,
                "status": profile.status,
                "created_at": profile.created_at.isoformat() if profile.created_at else None
            })
        return output
    except Exception as e:
        logger.error(f"Error getting pending psychologists: {e}")
        return []
    finally:
        db.close()


def get_all_psychologists():
    db = SessionLocal()
    try:
        results = db.query(User, PsychologistProfile).join(
            PsychologistProfile, User.id == PsychologistProfile.user_id
        ).all()
        
        output = []
        for user, profile in results:
            output.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "title": profile.title,
                "specialty": profile.specialty,
                "bio": profile.bio,
                "status": profile.status,
                "created_at": profile.created_at.isoformat() if profile.created_at else None
            })
        return output
    except Exception as e:
        logger.error(f"Error getting all psychologists: {e}")
        return []
    finally:
        db.close()


def reject_psychologist(username: str) -> bool:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False
        profile = db.query(PsychologistProfile).filter(PsychologistProfile.user_id == user.id).first()
        if not profile:
            return False
        profile.status = "rejected"
        profile.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting psychologist: {e}")
        return False
    finally:
        db.close()


def check_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    def parse_t(t):
        h, m = map(int, t.split(":"))
        return h * 60 + m
    s1, e1 = parse_t(start1), parse_t(end1)
    s2, e2 = parse_t(start2), parse_t(end2)
    return max(s1, s2) < min(e1, e2)


def has_overlapping_availability(db, psychologist_id: int, day_of_week: int, start_time: str, end_time: str, exclude_id: int = None) -> bool:
    query = db.query(PsychologistAvailability).filter(
        PsychologistAvailability.psychologist_id == psychologist_id,
        PsychologistAvailability.day_of_week == day_of_week,
        PsychologistAvailability.is_active == True
    )
    if exclude_id is not None:
        query = query.filter(PsychologistAvailability.id != exclude_id)
    
    existing = query.all()
    for av in existing:
        if check_overlap(start_time, end_time, av.start_time, av.end_time):
            return True
    return False


def get_psychologist_availabilities_db(psychologist_id: int):
    db = SessionLocal()
    try:
        rows = db.query(PsychologistAvailability).filter(
            PsychologistAvailability.psychologist_id == psychologist_id
        ).all()
        return [
            {
                "id": r.id,
                "psychologist_id": r.psychologist_id,
                "day_of_week": r.day_of_week,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "slot_duration_minutes": r.slot_duration_minutes,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None
            }
            for r in rows
        ]
    finally:
        db.close()


def create_psychologist_availability_db(psychologist_id: int, day_of_week: int, start_time: str, end_time: str, slot_duration_minutes: int):
    if day_of_week < 0 or day_of_week > 6:
        raise ValueError("Gün seçimi 0 ile 6 arasında olmalıdır.")
    
    if slot_duration_minutes not in [30, 45, 60, 90]:
        raise ValueError("Geçersiz seans süresi. Sadece 30, 45, 60 veya 90 dakika seçebilirsiniz.")
    
    try:
        def parse_t(t):
            h, m = map(int, t.split(":"))
            if h < 0 or h > 23 or m < 0 or m > 59:
                raise ValueError()
            return h * 60 + m
        s_min = parse_t(start_time)
        e_min = parse_t(end_time)
    except Exception:
        raise ValueError("Saat formatı geçerli HH:MM formatında olmalıdır.")
        
    if s_min >= e_min:
        raise ValueError("Başlangıç saati bitiş saatinden önce olmalıdır.")
        
    db = SessionLocal()
    try:
        if has_overlapping_availability(db, psychologist_id, day_of_week, start_time, end_time):
            raise ValueError("Bu zaman aralığı mevcut bir müsaitlik kaydınızla çakışıyor.")
            
        new_av = PsychologistAvailability(
            psychologist_id=psychologist_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            slot_duration_minutes=slot_duration_minutes,
            is_active=True
        )
        db.add(new_av)
        db.commit()
        db.refresh(new_av)
        return {
            "id": new_av.id,
            "psychologist_id": new_av.psychologist_id,
            "day_of_week": new_av.day_of_week,
            "start_time": new_av.start_time,
            "end_time": new_av.end_time,
            "slot_duration_minutes": new_av.slot_duration_minutes,
            "is_active": new_av.is_active,
            "created_at": new_av.created_at.isoformat() if new_av.created_at else None,
            "updated_at": new_av.updated_at.isoformat() if new_av.updated_at else None
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def update_psychologist_availability_db(psychologist_id: int, availability_id: int, day_of_week: Optional[int] = None, start_time: Optional[str] = None, end_time: Optional[str] = None, slot_duration_minutes: Optional[int] = None, is_active: Optional[bool] = None):
    db = SessionLocal()
    try:
        av = db.query(PsychologistAvailability).filter(
            PsychologistAvailability.id == availability_id
        ).first()
        if not av:
            raise ValueError("Müsaitlik kaydı bulunamadı.")
            
        if av.psychologist_id != psychologist_id:
            raise ValueError("Bu müsaitlik kaydını düzenleme yetkiniz yok.")
            
        new_day = day_of_week if day_of_week is not None else av.day_of_week
        new_start = start_time if start_time is not None else av.start_time
        new_end = end_time if end_time is not None else av.end_time
        new_duration = slot_duration_minutes if slot_duration_minutes is not None else av.slot_duration_minutes
        new_active = is_active if is_active is not None else av.is_active
        
        if new_day < 0 or new_day > 6:
            raise ValueError("Gün seçimi 0 ile 6 arasında olmalıdır.")
            
        if new_duration not in [30, 45, 60, 90]:
            raise ValueError("Geçersiz seans süresi. Sadece 30, 45, 60 veya 90 dakika seçebilirsiniz.")
            
        try:
            def parse_t(t):
                h, m = map(int, t.split(":"))
                if h < 0 or h > 23 or m < 0 or m > 59:
                    raise ValueError()
                return h * 60 + m
            s_min = parse_t(new_start)
            e_min = parse_t(new_end)
        except Exception:
            raise ValueError("Saat formatı geçerli HH:MM formatında olmalıdır.")
            
        if s_min >= e_min:
            raise ValueError("Başlangıç saati bitiş saatinden önce olmalıdır.")
            
        if new_active:
            if has_overlapping_availability(db, psychologist_id, new_day, new_start, new_end, exclude_id=availability_id):
                raise ValueError("Bu zaman aralığı mevcut bir müsaitlik kaydınızla çakışıyor.")
                
        av.day_of_week = new_day
        av.start_time = new_start
        av.end_time = new_end
        av.slot_duration_minutes = new_duration
        av.is_active = new_active
        av.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(av)
        return {
            "id": av.id,
            "psychologist_id": av.psychologist_id,
            "day_of_week": av.day_of_week,
            "start_time": av.start_time,
            "end_time": av.end_time,
            "slot_duration_minutes": av.slot_duration_minutes,
            "is_active": av.is_active,
            "created_at": av.created_at.isoformat() if av.created_at else None,
            "updated_at": av.updated_at.isoformat() if av.updated_at else None
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def delete_psychologist_availability_db(psychologist_id: int, availability_id: int) -> bool:
    db = SessionLocal()
    try:
        av = db.query(PsychologistAvailability).filter(
            PsychologistAvailability.id == availability_id
        ).first()
        if not av:
            return False
            
        if av.psychologist_id != psychologist_id:
            raise ValueError("Bu müsaitlik kaydını silme yetkiniz yok.")
            
        db.delete(av)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()






