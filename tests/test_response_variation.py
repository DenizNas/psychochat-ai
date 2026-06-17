import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app, get_current_user
import src.api.main as api_main
from src.response_engine.variation_engine import select_linguistic_variants, VARIANTS
from src.services.database import init_db, SessionLocal, EmotionEvent, save_emotion_event, get_user_emotion_timeline

# Setup Mock Predictor to avoid loading raw models in tests
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
        else:
            return {
                "emotion": {"label": "neutral", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }

api_main.predictor = MockPredictor()

# Override authentication for testing API endpoints
app.dependency_overrides[get_current_user] = lambda: "test_user_var"
client = TestClient(app)


def test_variation_engine_logic():
    """Verify that selection and anti-repetition rules work correctly in the variation engine."""
    # Test 1: Empty history returns the default first option
    var_id, directive = select_linguistic_variants(
        recent_responses=[],
        emotion="sadness",
        strategy="validation"
    )
    assert var_id == "val_1"
    assert "yükü taşırken" in directive.lower()

    # Test 2: If first option is in history, anti-repetition filters it out
    # val_1 keywords: "yükü taş", "yorulduğunu", "görebiliyorum"
    var_id_filtered, directive_filtered = select_linguistic_variants(
        recent_responses=["Bu yükü taşırken ne kadar yorulduğunu görebiliyorum. Paylaşman çok değerli."],
        emotion="sadness",
        strategy="validation"
    )
    assert var_id_filtered != "val_1"

    # Test 3: If all options are filtered, falls back safely to first option
    var_id_fallback, _ = select_linguistic_variants(
        recent_responses=[
            "Bu yükü taşırken ne kadar yorulduğunu görebiliyorum.",
            "Bunun seni ne kadar yorduğunu hissedebiliyorum.",
            "Bu duygularla tek başına baş etmeye çalışmak kolay görünmüyor.",
            "Yaşadığın şeyin ağırlığını en derinden duyabiliyorum."
        ],
        emotion="sadness",
        strategy="validation"
    )
    assert var_id_fallback == "val_1"


def test_api_predict_returns_variation():
    """Verify that the /predict endpoint returns the chosen variation key in metadata."""
    res = client.post("/predict", json={"text": "Bugün kendimi çok mutsuz hissediyorum."})
    assert res.status_code == 200
    data = res.json()
    assert data["emotion"] == "sadness"
    assert "variation" in data
    assert data["variation"] is not None


def test_database_persistence_of_variation():
    """Verify that save_emotion_event and get_user_emotion_timeline handle variation correctly."""
    init_db()
    db = SessionLocal()
    try:
        # Clear existing events
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_var_db").delete()
        db.commit()

        # Save event with variation
        saved = save_emotion_event(
            user_id="test_user_var_db",
            message_id="msg-var123",
            emotion="sadness",
            risk="low",
            source="predict",
            subtype="anhedonia",
            strategy="validation",
            variation="val_2"
        )
        assert saved is True

        # Retrieve timeline and check variation column
        timeline = get_user_emotion_timeline(user_id="test_user_var_db", days=1)
        assert len(timeline) == 1
        assert timeline[0]["message_id"] == "msg-var123"
        assert timeline[0]["emotion"] == "sadness"
        assert timeline[0]["variation"] == "val_2"

    finally:
        db.query(EmotionEvent).filter(EmotionEvent.user_id == "test_user_var_db").delete()
        db.commit()
        db.close()
