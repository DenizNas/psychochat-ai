import urllib.request
import json
import time

url = "http://localhost:8000/auth/password-reset/request"
data = {"email": "denizdennasnas@gmail.com"}
req = urllib.request.Request(
    url, 
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

def run_request(i):
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            duration = time.time() - start
            print(f"Request {i} - Status Code: {response.getcode()} - Duration: {duration:.2f}s")
            print("Response Body:", response.read().decode("utf-8"))
    except Exception as e:
        duration = time.time() - start
        print(f"Request {i} - Error after {duration:.2f}s: {e}")
        if hasattr(e, 'read'):
            print("Error Body:", e.read().decode("utf-8"))

print("Running first request...")
run_request(1)

# Wait cooldown
print("Sleeping 1 second...")
time.sleep(1)

print("Running second request...")
run_request(2)
