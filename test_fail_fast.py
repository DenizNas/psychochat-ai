import os
import sys
import subprocess

emotion_dir = "models/emotion_model"
missing_dir = "models/emotion_model_missing"

# 1. Temporarily rename to simulate missing model
if os.path.exists(emotion_dir):
    os.rename(emotion_dir, missing_dir)
    print(f"Renamed {emotion_dir} to {missing_dir}")

try:
    # 2. Try to run main.py (Should fail with sys.exit(1))
    print("Testing fail-fast startup...")
    # Run simply as a module to trigger load_models logic, but since load_models is triggered via uvicorn on startup,
    # let's write a small script that just calls load_models()
    
    test_script = """
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath('.')))
from src.api.main import load_models
load_models()
    """
    with open("tmp_fail_test.py", "w") as f:
        f.write(test_script)
        
    result = subprocess.run([sys.executable, "tmp_fail_test.py"], capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
    print(f"RETURN CODE: {result.returncode}")
    
    if result.returncode == 1:
        print("SUCCESS: App correctly failed with exit code 1.")
    else:
        print(f"FAIL: Expected exit code 1, got {result.returncode}")

finally:
    # 3. Restore
    if os.path.exists(missing_dir):
        os.rename(missing_dir, emotion_dir)
        print("Restored original directory.")
    if os.path.exists("tmp_fail_test.py"):
        os.remove("tmp_fail_test.py")
