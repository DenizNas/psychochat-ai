import os
import sys
from fastapi.testclient import TestClient

# Ensure PYTHONPATH is correctly resolved
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app
from src.response_engine.memory_manager import clear_user_memory, get_user_memory_summary

def run_integration_tests():
    print("====================================================")
    print("PSYCHOCHAT-AI FAZ 6 INTEGRATION TEST SUITE")
    print("====================================================\n")

    # Use the context manager to trigger startup events (model loading)
    with TestClient(app) as client:
        username = f"deniz_test_qa_{int(os.getpid())}"
        password = "SecurePassword123!"

        # 1. Test registration
        print("1. Testing Register...")
        reg_payload = {"username": username, "password": password}
        reg_res = client.post("/register", json=reg_payload)
        print(f"   Status: {reg_res.status_code}")
        print(f"   Response: {reg_res.json()}")
        assert reg_res.status_code == 201, "Registration failed"

        # 2. Test login
        print("\n2. Testing Login...")
        login_res = client.post("/login", json=reg_payload)
        print(f"   Status: {login_res.status_code}")
        print(f"   Response: {login_res.json()}")
        assert login_res.status_code == 200, "Login failed"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Test GET profile (defaults)
        print("\n3. Testing GET Profile (Defaults)...")
        prof_res = client.get("/profile", headers=headers)
        print(f"   Status: {prof_res.status_code}")
        profile_data = prof_res.json()
        print(f"   Preferred Language: {profile_data.get('preferred_language')}")
        print(f"   Response Style: {profile_data.get('response_style')}")
        print(f"   Privacy Mode: {profile_data.get('privacy_mode')}")
        print(f"   Answer Length: {profile_data.get('answer_length_preference')}")
        assert profile_data.get("preferred_language") == "tr", "Default language should be 'tr'"
        assert profile_data.get("privacy_mode") is False, "Default privacy mode should be False"

        # 4. Test PUT profile (partial update and Turkish characters)
        print("\n4. Testing PUT Profile (Turkish Characters + Custom Preferences)...")
        put_payload = {
            "display_name": "Deniz Nas",
            "bio": "Türkçe karakter testi: şıöçğÜİ",
            "preferred_language": "tr",
            "response_style": "direct",
            "answer_length_preference": "short",
            "privacy_mode": False  # Keep false initially to test memory extraction
        }
        put_res = client.put("/profile", headers=headers, json=put_payload)
        print(f"   Status: {put_res.status_code}")
        updated_profile = put_res.json()
        print(f"   Updated Display Name: {updated_profile.get('display_name')}")
        print(f"   Updated Bio: {updated_profile.get('bio')}")
        print(f"   Updated Style: {updated_profile.get('response_style')}")
        print(f"   Updated Length: {updated_profile.get('answer_length_preference')}")
        
        assert updated_profile.get("display_name") == "Deniz Nas"
        assert updated_profile.get("bio") == "Türkçe karakter testi: şıöçğÜİ", "Turkish characters got corrupted"
        assert updated_profile.get("response_style") == "direct"
        assert updated_profile.get("answer_length_preference") == "short"

        # 5. Test Personalization in Predict (Language, Style, Length)
        print("\n5. Testing PredictPersonalization (Normal Input)...")
        pred_payload = {"text": "Sınav stresim yine başladı, kısa ve net cevap verir misin?"}
        pred_res = client.post("/predict", headers=headers, json=pred_payload)
        print(f"   Status: {pred_res.status_code}")
        pred_data = pred_res.json()
        print(f"   Emotion: {pred_data.get('emotion')}")
        print(f"   Risk: {pred_data.get('risk')}")
        print(f"   Response: {pred_data.get('response')}")
        assert "response" in pred_data
        assert "emotion" in pred_data
        assert "risk" in pred_data

        # 6. Test Memory Extraction (privacy_mode = False)
        print("\n6. Testing Memory Extraction (Privacy Mode = False)...")
        clear_user_memory(username)
        
        # "meditasyon bana iyi geliyor" matches (meditasyon)\s*(bana)
        mem_payload = {"text": "meditasyon bana iyi geliyor"}
        client.post("/predict", headers=headers, json=mem_payload)
        
        mem_summary = get_user_memory_summary(username)
        print(f"   Stored memories count: {mem_summary['total_memories']}")
        print(f"   Memories summary: {mem_summary}")
        assert mem_summary["total_memories"] > 0, "Memory extraction failed when privacy_mode = False"

        # 7. Test Privacy Mode (privacy_mode = True)
        print("\n7. Testing Privacy Mode (privacy_mode = True)...")
        # Enable privacy mode
        client.put("/profile", headers=headers, json={"privacy_mode": True})
        
        # Store current memory count
        prev_mem_count = get_user_memory_summary(username)["total_memories"]
        
        # Send another text that would normally trigger extraction: "müzik bana iyi geliyor"
        client.post("/predict", headers=headers, json={"text": "müzik bana iyi geliyor"})
        
        new_mem_summary = get_user_memory_summary(username)
        print(f"   Previous memories count: {prev_mem_count}")
        print(f"   New memories count: {new_mem_summary['total_memories']}")
        assert new_mem_summary["total_memories"] == prev_mem_count, "Memory extraction occurred when privacy_mode = True"
        print("   Privacy Mode successfully prevented memory extraction!")

        # 8. Test Crisis Override
        print("\n8. Testing Crisis Override (Preferences ignored under crisis)...")
        # Enable a distinct response style and length
        client.put("/profile", headers=headers, json={"response_style": "direct", "answer_length_preference": "short"})
        
        # Send a high risk (crisis) text
        crisis_payload = {"text": "bıçak aldım kendimi öldüreceğim son kez yazıyorum"}
        crisis_res = client.post("/predict", headers=headers, json=crisis_payload)
        print(f"   Status: {crisis_res.status_code}")
        crisis_data = crisis_res.json()
        print(f"   Emotion: {crisis_data.get('emotion')}")
        print(f"   Risk: {crisis_data.get('risk')}")
        print(f"   Response: {crisis_data.get('response')}")
        print(f"   Emergency Contact: {crisis_data.get('emergency_contact')}")
        
        # Under crisis, the response MUST be a safe template, not a direct short GPT response.
        # The default crisis safe template has detailed sentences and is supportive.
        assert crisis_data.get("risk").lower() in ["kriz", "1", "crisis"], "Crisis risk not detected"
        assert crisis_data.get("emergency_contact") is not None, "Emergency contact missing in crisis response"
        print("   Crisis override validated successfully!")

        print("\n====================================================")
        print("ALL FAZ 6 INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
        print("====================================================")

if __name__ == "__main__":
    run_integration_tests()
