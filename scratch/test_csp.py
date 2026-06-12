import sys
import os
from fastapi.testclient import TestClient

# Make sure src path is imported correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app

client = TestClient(app)

def test_csp_headers():
    print("Running CSP verification tests...")
    
    # 1. Verify health endpoint is accessible and has strict CSP
    print("Testing /health...")
    health_res = client.get("/health")
    print(f"/health Status: {health_res.status_code}")
    assert health_res.status_code == 200, "Health check failed!"
    health_csp = health_res.headers.get("Content-Security-Policy")
    print(f"/health CSP: {health_csp}")
    assert health_csp == "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';", "Strict CSP expected on /health"
    
    # 2. Verify openapi.json works and has strict CSP (or default)
    print("Testing /openapi.json...")
    openapi_res = client.get("/openapi.json")
    print(f"/openapi.json Status: {openapi_res.status_code}")
    assert openapi_res.status_code == 200, "OpenAPI schema failed!"
    openapi_csp = openapi_res.headers.get("Content-Security-Policy")
    print(f"/openapi.json CSP: {openapi_csp}")
    assert openapi_csp == "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';", "Strict CSP expected on /openapi.json"
    
    # 3. Verify docs URL is accessible and has relaxed CSP
    print("Testing /docs...")
    docs_res = client.get("/docs")
    print(f"/docs Status: {docs_res.status_code}")
    assert docs_res.status_code == 200, "Docs page failed to load!"
    docs_csp = docs_res.headers.get("Content-Security-Policy")
    print(f"/docs CSP: {docs_csp}")
    expected_relaxed_csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com;"
    )
    assert docs_csp == expected_relaxed_csp, f"Expected relaxed CSP, got: {docs_csp}"
    
    # 4. Verify redoc URL is accessible and has relaxed CSP
    print("Testing /redoc...")
    redoc_res = client.get("/redoc")
    print(f"/redoc Status: {redoc_res.status_code}")
    assert redoc_res.status_code == 200, "ReDoc page failed to load!"
    redoc_csp = redoc_res.headers.get("Content-Security-Policy")
    print(f"/redoc CSP: {redoc_csp}")
    assert redoc_csp == expected_relaxed_csp, f"Expected relaxed CSP, got: {redoc_csp}"
    
    # 5. Verify root URL is accessible and has strict CSP
    print("Testing /...")
    root_res = client.get("/")
    print(f"/ Status: {root_res.status_code}")
    assert root_res.status_code == 200
    root_csp = root_res.headers.get("Content-Security-Policy")
    print(f"/ CSP: {root_csp}")
    assert root_csp == "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';", "Strict CSP expected on root /"

    print("\nALL CSP VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_csp_headers()
