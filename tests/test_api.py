import sys
import os
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.main import app

client = TestClient(app)

def test_api():
    print("Testing Normal Emotion Scenario...")
    res1 = client.post("/predict", json={"text": "Bugün hava çok güzel, kendimi harika hissediyorum!"})
    print("Status:", res1.status_code)
    print("Response:", res1.json())
    
    print("\nTesting Sadness/Anxiety Scenario...")
    res2 = client.post("/predict", json={"text": "Sonuçlar açıklanmıyor çok kaygılıyım."})
    print("Status:", res2.status_code)
    print("Response:", res2.json())
    
    print("\nTesting Crisis Scenario...")
    res3 = client.post("/predict", json={"text": "Artık dayanamıyorum, her şey çok anlamsız, yapamıyorum."})
    print("Status:", res3.status_code)
    print("Response:", res3.json())

if __name__ == "__main__":
    test_api()
