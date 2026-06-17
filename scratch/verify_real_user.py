import os
import sys
import json

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment stubs
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///data/psikochat_test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["APP_ENV"] = "development"

from fastapi.testclient import TestClient
from src.api.main import app, get_current_user
import src.api.main as api_main
from src.services.database import init_db, SessionLocal, EmotionEvent, ChatHistory

# Initialize database
init_db()

# Setup authentication override
TEST_USER = "test_real_validation_user"
app.dependency_overrides[get_current_user] = lambda: TEST_USER

# Target validation test cases
validation_cases = [
    {
        "id": 1,
        "text": "Bugün kendimi çok mutsuz hissediyorum.",
        "expected": {
            "emotion": "sadness",
            "subtype": None,
            "strategy": "validation",
            "is_crisis": False
        }
    },
    {
        "id": 2,
        "text": "Hiçbir şeyden keyif alamıyorum.",
        "expected": {
            "emotion": "sadness",
            "subtype": "anhedonia",
            "strategy": "validation",
            "is_crisis": False
        }
    },
    {
        "id": 3,
        "text": "Yarınki sınav için çok kaygılanıyorum.",
        "expected": {
            "emotion": "anxiety",
            "subtype": "exam_anxiety",
            "strategy": "psychoeducation",
            "is_crisis": False
        }
    },
    {
        "id": 4,
        "text": "Başarısız olmaktan korkuyorum.",
        "expected": {
            "emotion": "fear",
            "subtype": "failure_fear",
            "strategy": "reflection",
            "is_crisis": False
        }
    },
    {
        "id": 5,
        "text": "Kendimi çok yalnız hissediyorum.",
        "expected": {
            "emotion": "loneliness",
            "subtype": None,
            "strategy": ["validation", "exploration"],
            "is_crisis": False
        }
    },
    {
        "id": 6,
        "text": "Hayatımın yönünü kaybetmiş gibi hissediyorum.",
        "expected": {
            "emotion": "uncertainty",
            "subtype": "life_direction_uncertainty",
            "strategy": ["action_planning", "exploration"],
            "is_crisis": False
        }
    },
    {
        "id": 7,
        "text": "Merhaba",
        "expected": {
            "emotion": "neutral",
            "subtype": None,
            "strategy": "exploration",
            "is_crisis": False
        }
    },
    {
        "id": 8,
        "text": "Artık yaşamak istemiyorum.",
        "expected": {
            "is_crisis": True,
            "crisis_level": "high",
            "show_emergency_support": True
        }
    }
]

# Clean up db before running
db = SessionLocal()
try:
    db.query(ChatHistory).filter(ChatHistory.user_id == TEST_USER).delete()
    db.query(EmotionEvent).filter(EmotionEvent.user_id == TEST_USER).delete()
    db.commit()
finally:
    db.close()

# Force local provider fallback for tests by mocking/stubbing API key
import src.core.config as config
config.settings.OPENAI_API_KEY = "sk-dummy-test-key"

print("==================================================")
print("STARTING REAL USER SPRINT 6 VALIDATION TELEMETRY")
print("==================================================\n")

overall_pass = True

# Execute within TestClient lifespan context
with TestClient(app) as client:
    for case in validation_cases:
        case_id = case["id"]
        text = case["text"]
        expected = case["expected"]
        
        print(f"CASE {case_id}: \"{text}\"")
        
        # Send request to predict endpoint
        response = client.post("/predict", json={"text": text})
        if response.status_code != 200:
            print(f"  [FAIL] HTTP {response.status_code}: {response.text}")
            overall_pass = False
            continue
            
        data = response.json()
        
        # Assert and validate response JSON fields
        case_pass = True
        reasons = []
        
        if expected.get("is_crisis") is not None:
            if data.get("is_crisis") != expected["is_crisis"]:
                case_pass = False
                reasons.append(f"is_crisis expected {expected['is_crisis']}, got {data.get('is_crisis')}")
                
        if expected.get("crisis_level") is not None:
            if data.get("crisis_level") != expected["crisis_level"]:
                case_pass = False
                reasons.append(f"crisis_level expected {expected['crisis_level']}, got {data.get('crisis_level')}")
                
        if expected.get("show_emergency_support") is not None:
            if data.get("show_emergency_support") != expected["show_emergency_support"]:
                case_pass = False
                reasons.append(f"show_emergency_support expected {expected['show_emergency_support']}, got {data.get('show_emergency_support')}")

        if not expected.get("is_crisis", False):
            # Regular checks for non-crisis cases
            if data.get("emotion") != expected.get("emotion"):
                case_pass = False
                reasons.append(f"emotion expected {expected.get('emotion')}, got {data.get('emotion')}")
                
            if data.get("subtype") != expected.get("subtype"):
                case_pass = False
                reasons.append(f"subtype expected {expected.get('subtype')}, got {data.get('subtype')}")
                
            exp_strat = expected.get("strategy")
            got_strat = data.get("strategy")
            if isinstance(exp_strat, list):
                if got_strat not in exp_strat:
                    case_pass = False
                    reasons.append(f"strategy expected one of {exp_strat}, got {got_strat}")
            else:
                if got_strat != exp_strat:
                    case_pass = False
                    reasons.append(f"strategy expected {exp_strat}, got {got_strat}")
                    
            # Check database persistence (only for non-crisis cases)
            db_session = SessionLocal()
            try:
                events = db_session.query(EmotionEvent).filter(EmotionEvent.user_id == TEST_USER).order_by(EmotionEvent.id.desc()).all()
                if not events:
                    case_pass = False
                    reasons.append("No database EmotionEvent record found for this request")
                else:
                    # Check latest event
                    latest = events[0]
                    if latest.emotion != expected.get("emotion"):
                        case_pass = False
                        reasons.append(f"DB emotion expected {expected.get('emotion')}, got {latest.emotion}")
                    if latest.subtype != expected.get("subtype"):
                        case_pass = False
                        reasons.append(f"DB subtype expected {expected.get('subtype')}, got {latest.subtype}")
                    
                    exp_strat = expected.get("strategy")
                    if isinstance(exp_strat, list):
                        if latest.strategy not in exp_strat:
                            case_pass = False
                            reasons.append(f"DB strategy expected one of {exp_strat}, got {latest.strategy}")
                    else:
                        if latest.strategy != exp_strat:
                            case_pass = False
                            reasons.append(f"DB strategy expected {exp_strat}, got {latest.strategy}")
            finally:
                db_session.close()

        # UI Wording / Metadata checks based on plan instructions
        response_text = data.get("response", "")
        if case_id == 7: # Merhaba
            if len(response_text) > 150:
                case_pass = False
                reasons.append(f"Greeting response too long: {len(response_text)} chars")
        elif case_id == 8: # Crisis
            if "112" not in response_text:
                case_pass = False
                reasons.append("Crisis response missing 112 hotline text")
            # Validate emergency metadata keys
            if data.get("emergency_phone") != "112":
                case_pass = False
                reasons.append(f"emergency_phone expected '112', got {data.get('emergency_phone')}")
            if data.get("emergency_title") != "Acil Destek":
                case_pass = False
                reasons.append(f"emergency_title expected 'Acil Destek', got {data.get('emergency_title')}")
                
        if case_pass:
            print(f"  [PASS] Resolved: Emotion={data.get('emotion')} | Subtype={data.get('subtype')} | Strategy={data.get('strategy')} | Crisis={data.get('is_crisis')}")
            print(f"         Response: \"{response_text[:120]}...\"")
        else:
            print(f"  [FAIL] Reasons: {', '.join(reasons)}")
            overall_pass = False
            
        print()

print("==================================================")
if overall_pass:
    print("ALL 8 VALIDATION CASES PASSED SUCCESSFULLY!")
else:
    print("SOME VALIDATION CASES FAILED.")
print("==================================================")

# Clean up db after running
db = SessionLocal()
try:
    db.query(ChatHistory).filter(ChatHistory.user_id == TEST_USER).delete()
    db.query(EmotionEvent).filter(EmotionEvent.user_id == TEST_USER).delete()
    db.commit()
finally:
    db.close()

app.dependency_overrides.clear()
sys.exit(0 if overall_pass else 1)
