import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app, get_current_user
import src.api.main as api_main
from src.response_engine.strategy_engine import detect_conversation_strategy
from src.response_engine.counseling_examples import detect_emotion_subtype, categorize_input
from src.services.database import init_db, SessionLocal, EmotionEvent, save_emotion_event, get_user_emotion_timeline

# Setup Mock Predictor to return expected raw emotions
class MockPredictor:
    def predict_both(self, text):
        t = text.lower()
        if "mutsuz" in t:
            return {
                "emotion": {"label": "sadness", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }
        elif "sınav" in t or "sinav" in t:
            return {
                "emotion": {"label": "anxiety", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }
        elif "başarısız" in t or "basarisiz" in t:
            return {
                "emotion": {"label": "fear", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }
        elif "ne yapacağımı" in t or "ne yapacagimi" in t:
            return {
                "emotion": {"label": "neutral", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }
        elif "yalnız" in t or "yalniz" in t:
            return {
                "emotion": {"label": "sadness", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }
        else:
            return {
                "emotion": {"label": "neutral", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }

api_main.predictor = MockPredictor()

# Override authentication for testing API endpoints
client = TestClient(app)


def test_detect_strategy_logic():
    """Verify that keyword/rule based strategy detection maps queries to correct strategies."""
    # Sadness -> validation
    strategy = detect_conversation_strategy("Bugün kendimi çok mutsuz hissediyorum.", "sadness", "disappointment")
    assert strategy == "validation"

    # Uncertainty -> action_planning
    strategy = detect_conversation_strategy("Ne yapacağımı bilmiyorum.", "uncertainty", "decision_uncertainty")
    assert strategy == "action_planning"

    # failure_fear -> reflection
    strategy = detect_conversation_strategy("Başarısız olmaktan korkuyorum.", "fear", "failure_fear")
    assert strategy == "reflection"

    # exam_anxiety -> psychoeducation
    strategy = detect_conversation_strategy("Yarınki sınav için çok kaygılanıyorum.", "anxiety", "exam_anxiety")
    assert strategy == "psychoeducation"

    # loneliness -> validation
    strategy = detect_conversation_strategy("Kendimi çok yalnız hissediyorum.", "loneliness", None)
    assert strategy == "validation"

    # neutral -> exploration
    strategy = detect_conversation_strategy("Merhaba.", "neutral", None)
    assert strategy == "exploration"


def test_api_predict_returns_strategy():
    """Verify /predict returns the correct strategy."""
    app.dependency_overrides[get_current_user] = lambda: "test_user_strategy"
    
    # Clean up any leftover database records to avoid spam protection triggers
    init_db()
    db = SessionLocal()
    try:
        from src.services.database import ChatHistory, EmotionEvent
        db.query(ChatHistory).filter(ChatHistory.user_id == "test_user_strategy").delete()
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_strategy").delete()
        db.commit()
    finally:
        db.close()

    try:
        # Test mutsuz -> validation
        res = client.post("/predict", json={"text": "Bugün kendimi çok mutsuz hissediyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "sadness"
        assert data["strategy"] == "validation"

        # Test bilmiyorum -> action_planning
        res = client.post("/predict", json={"text": "Ne yapacağımı bilmiyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "uncertainty"
        assert data["strategy"] == "action_planning"

        # Test başarısız -> reflection
        res = client.post("/predict", json={"text": "Başarısız olmaktan korkuyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "fear"
        assert data["strategy"] == "reflection"

        # Test sınav -> psychoeducation
        res = client.post("/predict", json={"text": "Yarınki sınav için çok kaygılanıyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "anxiety"
        assert data["strategy"] == "psychoeducation"

        # Test yalnız -> validation
        res = client.post("/predict", json={"text": "Kendimi çok yalnız hissediyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "loneliness"
        assert data["strategy"] == "validation"
    finally:
        app.dependency_overrides.clear()


def test_database_persistence_of_strategies():
    """Verify save_emotion_event and get_user_emotion_timeline handle strategy correctly."""
    init_db()
    db = SessionLocal()
    try:
        # Clear existing events
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_strategy").delete()
        db.commit()

        # Save event with strategy
        saved = save_emotion_event(
            user_id="test_user_strategy",
            message_id="msg-abc123",
            emotion="anxiety",
            risk="low",
            source="predict",
            subtype="exam_anxiety",
            strategy="psychoeducation"
        )
        assert saved is True

        # Retrieve timeline and check strategy
        timeline = get_user_emotion_timeline(user_id="test_user_strategy", days=1)
        assert len(timeline) == 1
        assert timeline[0]["message_id"] == "msg-abc123"
        assert timeline[0]["emotion"] == "anxiety"
        assert timeline[0]["subtype"] == "exam_anxiety"
        assert timeline[0]["strategy"] == "psychoeducation"

    finally:
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_strategy").delete()
        db.commit()
        db.close()
