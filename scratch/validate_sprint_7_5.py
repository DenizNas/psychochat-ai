import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_engine.engine import ResponseEngine
from src.response_engine.models import EngineInput
from src.services.database import init_db, SessionLocal, ChatHistory, save_chat_message

def validate():
    print("Initializing DB...")
    init_db()
    db = SessionLocal()
    user_id = "manual_validation_user"
    try:
        db.query(ChatHistory).filter(ChatHistory.user_id == user_id).delete()
        db.commit()
    finally:
        db.close()

    engine = ResponseEngine()

    conversation = [
        ("Bugün çok mutsuzum.", "sadness"),
        ("Hiçbir şeyden keyif alamıyorum.", "sadness"),
        ("Kimseyle konuşmak istemiyorum.", "sadness")
    ]

    print("\nRunning multi-turn manual validation conversation...")
    for text, emotion in conversation:
        print(f"\nUser: {text}")
        engine_input = EngineInput(
            text=text,
            emotion=emotion,
            risk="Normal",
            user_id=user_id,
            language="tr"
        )
        output = engine.generate_response(engine_input)
        print(f"Assistant: {output.final_text}")
        print(f"Detected Pattern: {output.metadata.get('conversation_pattern')}")

if __name__ == "__main__":
    validate()
