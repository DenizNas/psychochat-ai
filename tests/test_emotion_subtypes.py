import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app, get_current_user
import src.api.main as api_main
from src.response_engine.counseling_examples import detect_emotion_subtype, categorize_input
from src.services.database import init_db, SessionLocal, EmotionEvent, save_emotion_event, get_user_emotion_timeline

# Setup Mock Predictor to avoid slow model loading in tests and return expected raw emotion groups
class MockPredictor:
    def predict_both(self, text):
        t = text.lower()
        if "keyif alamıyorum" in t or "keyif alamiyorum" in t:
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
        elif "ne yapacağımı" in t or "ne yapacagimi" in t or "yönünü kaybettim" in t or "yonunu kaybettim" in t:
            # uncertainty
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


def test_detect_emotion_subtype_rules():
    """Verify that keyword/rule based subtype detection maps queries to correct subtypes."""
    # Sadness -> anhedonia
    category_sad = categorize_input("Hiçbir şeyden keyif alamıyorum.", "sadness")
    subtype_sad = detect_emotion_subtype("Hiçbir şeyden keyif alamıyorum.", category_sad)
    assert category_sad == "sadness"
    assert subtype_sad == "anhedonia"

    # Anxiety -> exam_anxiety
    category_anx = categorize_input("Yarınki sınav için çok kaygılanıyorum.", "anxiety")
    subtype_anx = detect_emotion_subtype("Yarınki sınav için çok kaygılanıyorum.", category_anx)
    assert category_anx == "anxiety"
    assert subtype_anx == "exam_anxiety"

    # Fear -> failure_fear
    category_fear = categorize_input("Başarısız olmaktan korkuyorum.", "fear")
    subtype_fear = detect_emotion_subtype("Başarısız olmaktan korkuyorum.", category_fear)
    assert category_fear == "fear"
    assert subtype_fear == "failure_fear"

    # Uncertainty -> decision_uncertainty
    category_unc1 = categorize_input("Ne yapacağımı bilmiyorum.", "neutral")
    subtype_unc1 = detect_emotion_subtype("Ne yapacağımı bilmiyorum.", category_unc1)
    assert category_unc1 == "uncertainty"
    assert subtype_unc1 == "decision_uncertainty"

    # Uncertainty -> life_direction_uncertainty
    category_unc2 = categorize_input("Hayatımın yönünü kaybettim.", "neutral")
    subtype_unc2 = detect_emotion_subtype("Hayatımın yönünü kaybettim.", category_unc2)
    assert category_unc2 == "uncertainty"
    assert subtype_unc2 == "life_direction_uncertainty"


def test_loneliness_not_sadness_subtype():
    """Verify loneliness is classified as a primary category, not a sadness subtype."""
    category = categorize_input("Kendimi çok yalnız hissediyorum.", "sadness")
    subtype = detect_emotion_subtype("Kendimi çok yalnız hissediyorum.", category)
    # Loneliness is a primary category, so the mapped category is loneliness.
    # Therefore, detect_emotion_subtype with category="loneliness" should return None
    # since loneliness has no subtypes.
    assert category == "loneliness"
    assert subtype is None


def test_api_predict_returns_subtype():
    """Verify /predict returns the mapped emotion and its subtype."""
    app.dependency_overrides[get_current_user] = lambda: "test_user_subtype"
    
    # Clean up database records to avoid spam protection triggers
    init_db()
    db = SessionLocal()
    try:
        from src.services.database import ChatHistory, EmotionEvent
        db.query(ChatHistory).filter(ChatHistory.user_id == "test_user_subtype").delete()
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_subtype").delete()
        db.commit()
    finally:
        db.close()

    try:
        # Test anhedonia subtype
        res = client.post("/predict", json={"text": "Hiçbir şeyden keyif alamıyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "sadness"
        assert data["subtype"] == "anhedonia"

        # Test exam_anxiety subtype
        res = client.post("/predict", json={"text": "Yarınki sınav için çok kaygılanıyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "anxiety"
        assert data["subtype"] == "exam_anxiety"

        # Test failure_fear subtype
        res = client.post("/predict", json={"text": "Başarısız olmaktan korkuyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "fear"
        assert data["subtype"] == "failure_fear"

        # Test decision_uncertainty subtype
        res = client.post("/predict", json={"text": "Ne yapacağımı bilmiyorum."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "uncertainty"
        assert data["subtype"] == "decision_uncertainty"

        # Test life_direction_uncertainty subtype
        res = client.post("/predict", json={"text": "Hayatımın yönünü kaybettim."})
        assert res.status_code == 200
        data = res.json()
        assert data["emotion"] == "uncertainty"
        assert data["subtype"] == "life_direction_uncertainty"
    finally:
        app.dependency_overrides.clear()


def test_database_persistence_of_subtypes():
    """Verify save_emotion_event and get_user_emotion_timeline handle subtype correctly."""
    init_db()
    db = SessionLocal()
    try:
        # Clear existing events for "test_user_subtype"
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_subtype").delete()
        db.commit()

        # Save an event with a subtype
        saved = save_emotion_event(
            user_id="test_user_subtype",
            message_id="msg-123456",
            emotion="sadness",
            risk="low",
            source="predict",
            subtype="anhedonia"
        )
        assert saved is True

        # Retrieve the timeline and check subtype
        timeline = get_user_emotion_timeline(user_id="test_user_subtype", days=1)
        assert len(timeline) == 1
        assert timeline[0]["message_id"] == "msg-123456"
        assert timeline[0]["emotion"] == "sadness"
        assert timeline[0]["subtype"] == "anhedonia"

    finally:
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_subtype").delete()
        db.commit()
        db.close()
