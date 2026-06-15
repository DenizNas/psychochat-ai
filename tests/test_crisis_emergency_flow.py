import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app, get_current_user
import src.api.main as api_main

# Setup Mock Predictor to avoid slow model loading in tests
class MockPredictor:
    def predict_both(self, text):
        t = text.lower()
        if "yaşamak istemiyorum" in t:
            return {
                "emotion": {"label": "sadness", "confidence": 0.9},
                "crisis_detection": {"label": "Crisis", "confidence": 0.9}
            }
        elif "zarar vermek üzereyim" in t or "zarar veriyorum" in t:
            return {
                "emotion": {"label": "sadness", "confidence": 0.9},
                "crisis_detection": {"label": "Crisis", "confidence": 0.9}
            }
        elif "zarar vereceğim" in t or "zarar verecegim" in t:
            return {
                "emotion": {"label": "anger", "confidence": 0.9},
                "crisis_detection": {"label": "Crisis", "confidence": 0.9}
            }
        elif "merhaba" in t:
            return {
                "emotion": {"label": "neutral", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }
        else:
            # Sadness case
            return {
                "emotion": {"label": "sadness", "confidence": 0.9},
                "crisis_detection": {"label": "Normal", "confidence": 0.9}
            }

api_main.predictor = MockPredictor()

# Set up test client and override authentication
app.dependency_overrides[get_current_user] = lambda: "test_user"
client = TestClient(app)

def test_crisis_emergency_flow():
    # 1. "Artık yaşamak istemiyorum." (Suicidal ideation)
    # Expected: is_crisis=true, crisis_level=high, show_emergency_support=true, bypassed.
    res1 = client.post("/predict", json={"text": "Artık yaşamak istemiyorum."})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_crisis"] is True
    assert data1["crisis_level"] == "high"
    assert data1["show_emergency_support"] is True
    assert "yalnız kalmaman önemli" in data1["response"].lower()
    
    # 2. "Kendime zarar vermek üzereyim." (Imminent self-harm)
    # Expected: crisis_level=imminent, show_emergency_support=true, response mentions 112 and has safety questions
    res2 = client.post("/predict", json={"text": "Kendime zarar vermek üzereyim."})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_crisis"] is True
    assert data2["crisis_level"] == "imminent"
    assert data2["show_emergency_support"] is True
    assert "112" in data2["response"]
    assert "yalnız kalmaman önemli" in data2["response"].lower()
    assert "güvende kalman" in data2["response"].lower()
    
    # 3. "Birine zarar vereceğim." (Imminent violence)
    # Expected: is_crisis=true, crisis_level=imminent, show_emergency_support=true, violence safety wording
    res3 = client.post("/predict", json={"text": "Birine zarar vereceğim."})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["is_crisis"] is True
    assert data3["crisis_level"] == "imminent"
    assert data3["show_emergency_support"] is True
    assert "çevrendekilerin güvenliği" in data3["response"].lower() or "güvenliği" in data3["response"].lower()

    # 4. "Merhaba" (Greeting)
    # Expected: is_crisis=false, show_emergency_support=false, neutral short response
    res4 = client.post("/predict", json={"text": "Merhaba"})
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["is_crisis"] is False
    assert data4["show_emergency_support"] is False
    assert len(data4["response"]) < 150 # should be short

    # 5. Non-crisis sadness
    # "Bugün kendimi çok kötü hissediyorum. Hiçbir şey yapmak istemiyorum."
    # Expected: is_crisis=false, show_emergency_support=false, normal coaching
    res5 = client.post("/predict", json={"text": "Bugün kendimi çok kötü hissediyorum. Hiçbir şey yapmak istemiyorum."})
    assert res5.status_code == 200
    data5 = res5.json()
    assert data5["is_crisis"] is False
    assert data5["show_emergency_support"] is False
    assert "112" not in data5["response"]
