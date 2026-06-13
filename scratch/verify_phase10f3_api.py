import requests
import json
import uuid

def verify():
    url_base = "http://localhost:8000"
    
    unique_id = str(uuid.uuid4())[:8]
    
    # 1. Register a normal user
    payload_user = {
        "username": f"user_{unique_id}",
        "password": "password123",
        "email": f"user_{unique_id}@example.com",
        "full_name": "Test User Regular"
    }
    print("Testing user registration...")
    res = requests.post(f"{url_base}/register", json=payload_user)
    print("Status:", res.status_code, "Response:", res.json())
    assert res.status_code == 201
    
    # 2. Register psychologist with missing fields (should fail)
    payload_psy_fail = {
        "username": f"psy_fail_{unique_id}",
        "password": "password123",
        "email": f"psy_fail_{unique_id}@example.com",
        "full_name": "Failed Psychologist",
        "role": "psychologist"
    }
    print("\nTesting psychologist registration with missing fields...")
    res = requests.post(f"{url_base}/register", json=payload_psy_fail)
    print("Status:", res.status_code, "Response:", res.text)
    assert res.status_code == 400
    
    # 3. Register psychologist with correct fields
    payload_psy_ok = {
        "username": f"psy_ok_{unique_id}",
        "password": "password123",
        "email": f"psy_ok_{unique_id}@example.com",
        "full_name": "Success Psychologist",
        "role": "psychologist",
        "title": "Dr. Psk.",
        "specialty": "Kaygı Bozuklukları",
        "bio": "Merhaba, ben uzman klinik psikoloğum ve bu biyografi en az 20 karakterdir."
    }
    print("\nTesting psychologist registration with correct fields...")
    res = requests.post(f"{url_base}/register", json=payload_psy_ok)
    print("Status:", res.status_code, "Response:", res.json())
    assert res.status_code == 201

    # 4. Login with existing test user deniznas@example.com
    print("\nTesting login for deniznas@example.com...")
    login_payload = {
        "email": "deniznas@example.com",
        "password": "password123"
    }
    res = requests.post(f"{url_base}/login", json=login_payload)
    print("Status:", res.status_code)
    assert res.status_code == 200
    data = res.json()
    print("User role in response:", data.get("role"))
    assert data.get("role") == "user"
    
    print("\nALL VERIFICATIONS PASSED!")

if __name__ == "__main__":
    verify()
