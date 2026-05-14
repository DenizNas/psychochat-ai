import requests
import json

base_url = "http://localhost:8001"

# 1. Register
print("Registering...")
res = requests.post(f"{base_url}/register", json={"username": "testuser_engine", "password": "testpass_engine"})
print(res.status_code, res.text)

# 2. Login
print("Logging in...")
res = requests.post(f"{base_url}/login", json={"username": "testuser_engine", "password": "testpass_engine"})
print(res.status_code, res.text)

if res.status_code == 200:
    token = res.json()["access_token"]
    
    # 3. Predict
    print("Testing Predict...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    data = {
        "text": "Kendimi çok yalnız hissediyorum."
    }
    
    res_predict = requests.post(f"{base_url}/predict", headers=headers, json=data)
    print(res_predict.status_code)
    try:
        parsed = res_predict.json()
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except:
        print(res_predict.text)
else:
    print("Login failed, cannot test predict.")
