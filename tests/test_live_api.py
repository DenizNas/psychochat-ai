import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8001"

def test_live_notifications():
    print("--- 1. REGISTER TEST USER ---")
    reg_payload = {
        "username": "live_user_test",
        "password": "strongpassword123"
    }
    r = requests.post(f"{BASE_URL}/register", json=reg_payload)
    print("Register Status:", r.status_code)
    # If already registered, register might return 400, which is fine
    
    print("\n--- 2. LOGIN TO OBTAIN JWT TOKEN ---")
    login_payload = {
        "username": "live_user_test",
        "password": "strongpassword123"
    }
    r = requests.post(f"{BASE_URL}/login", json=login_payload)
    print("Login Status:", r.status_code)
    if r.status_code != 200:
        print("Login failed, aborting")
        sys.exit(1)
        
    token = r.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    print("\n--- 3. REFRESH NOTIFICATION TIMELINE ---")
    r = requests.post(f"{BASE_URL}/notifications/refresh", headers=headers)
    print("Refresh Status:", r.status_code)
    print("Refresh Response Payload:")
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    
    print("\n--- 4. GET PLANNED NOTIFICATIONS ---")
    r = requests.get(f"{BASE_URL}/notifications", headers=headers)
    print("Get Status:", r.status_code)
    events = r.json()
    print(f"Total planned notification events: {len(events)}")
    
    if len(events) > 0:
        notif_id = events[0]["id"]
        print(f"\n--- 5. MARK NOTIFICATION {notif_id} DELIVERED ---")
        r = requests.post(f"{BASE_URL}/notifications/{notif_id}/mark-delivered", headers=headers)
        print("Mark Delivered Status:", r.status_code)
        print("Response:", r.json())
        
        # Get notifications again to verify delivered status
        r = requests.get(f"{BASE_URL}/notifications", headers=headers)
        events_after = r.json()
        print("Updated status for first item:", events_after[0]["status"])
        print("Delivered at timestamp:", events_after[0]["delivered_at"])

if __name__ == "__main__":
    test_live_notifications()
