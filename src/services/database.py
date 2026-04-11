import os
import time
import logging
from datetime import datetime
from typing import List, Dict
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func, case
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

# Varsayılan olarak SQLite kullanmaya devam eder, ancak ortam değişkeninden çekiyorsa PostgreSQL kullanır
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/psikochat.db")

# url düzeltmesi
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# PostgreSQL ile çalışıyorsak "sqlite:///" ayarlarını yoksayacağız
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping=True eklenerek bayat (stale) bağlantılar önlenir
engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    user_text = Column(String)
    emotion = Column(String)
    risk = Column(String)
    language = Column(String)
    latency_ms = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db(retries: int = 5, delay: int = 5):
    """
    Veritabanı bağlantısını ve tabloları başlatır.
    Eğer PostgreSQL kullanılıyorsa ve DB henüz hazır değilse belli sayıda tekrar dener.
    """
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database initialized and tables created successfully.")
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
        return [{"role": r.role, "content": r.content} for r in rows]
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
