import os
import sys

# 1. Set environment variables to simulate staging/production
os.environ["APP_ENV"] = "production"

from src.core.config import Settings

print("Directly testing Settings validation with low-entropy key in production mode...")

try:
    # Instantiate Settings directly with a low-entropy key
    Settings(
        APP_ENV="production",
        DEBUG=False,
        SECRET_KEY="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        DATABASE_URL="sqlite:///data/psikochat.db",
        CORS_ORIGINS=[]
    )
    print("FAIL: Settings loaded successfully with weak key! This should have failed.")
    sys.exit(1)
except Exception as e:
    print("\nSUCCESS: Validation correctly threw an error:")
    print(f"Error details:\n{e}")
    print("======================================================")
