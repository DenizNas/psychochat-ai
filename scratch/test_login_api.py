import requests
import json

def test_login():
    url = "http://localhost:8000/login"
    payload = {
        "email": "deniznas@example.com",
        "password": "password123"
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    print("Sending POST request to:", url)
    print("Payload:", json.dumps(payload, indent=2))
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)
        if response.status_code == 200:
            print("Login test PASSED!")
        else:
            print("Login test FAILED!")
    except Exception as e:
        print("Error connecting to server:", e)

if __name__ == "__main__":
    test_login()
