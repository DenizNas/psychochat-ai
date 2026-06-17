import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.database import init_db, SessionLocal, ChatHistory, get_chat_history, save_chat_message

init_db()
user_id = "test_user_ts_diagnostic"
db = SessionLocal()
try:
    db.query(ChatHistory).filter(ChatHistory.user_id == user_id).delete()
    db.commit()
finally:
    db.close()

save_chat_message(user_id, "user", "Hello timestamp test")
history = get_chat_history(user_id)
if history:
    print("Timestamp string from get_chat_history:", history[0]["timestamp"])
    
    # Query database record directly
    db = SessionLocal()
    try:
        rec = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).first()
        print("SQLAlchemy datetime type:", type(rec.timestamp))
        print("SQLAlchemy datetime val:", rec.timestamp)
        print("SQLAlchemy tzinfo:", rec.timestamp.tzinfo)
    finally:
        db.close()
