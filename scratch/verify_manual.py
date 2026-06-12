import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment stubs
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///data/psikochat_test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["APP_ENV"] = "development"

from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
from src.response_engine.memory_profile import save_profile
from src.services.database import init_db

# Initialize database (creates tables if needed)
init_db()

# Create manual test user profile
user_id = "test_manual_user"
profile_data = {
    "recurring_topics": [],
    "recurring_emotions": [],
    "goals": ["meditasyon"],
    "stressors": ["motivasyon kaybı"],
    "coping_methods": [],
    "positive_events": [],
    "relationship_context": [],
    "work_or_school_context": [],
    "last_advice_topics": ["breathing exercise"]
}
save_profile(user_id, profile_data)

# Create a mock/real database entry for display name if needed, or get_or_create_profile will do it.
from src.services.database import get_or_create_profile
db_prof = get_or_create_profile(user_id)
# Ensure display name is set to "Deniz"
from src.services.database import update_user_profile
update_user_profile(user_id, {"display_name": "Deniz"})

test_cases = [
    {
        "text": "Merhaba",
        "emotion": "neutral",
        "desc": "Case 1: 'Merhaba' should receive a neutral greeting, no stale memory inlay."
    },
    {
        "text": "Bağlantı testi",
        "emotion": "neutral",
        "desc": "Case 2: 'Bağlantı testi' should receive a neutral/relevant response, no stale memory inlay."
    },
    {
        "text": "Bugün kendimi çok kötü hissediyorum. Hiçbir şey yapmak istemiyorum.",
        "emotion": "sadness",
        "desc": "Case 3: Emotion sadness, long message. Memory inlay allowed (should get sadness-appropriate template)."
    }
]

print("=== START MANUAL VERIFICATION ===")
for case in test_cases:
    print(f"\nDescription: {case['desc']}")
    print(f"User input: '{case['text']}' (BERT predicted emotion: {case['emotion']})")
    
    inp = EngineInput(
        user_id=user_id,
        text=case["text"],
        emotion=case["emotion"],
        risk="Normal",
        language="tr",
        preferences=UserPreferences(
            response_style="supportive",
            preferred_language="tr",
            privacy_mode=False,
            answer_length_preference="medium"
        )
    )
    
    # We enforce using local provider fallback by setting a dummy API key
    import src.core.config as config
    config.settings.OPENAI_API_KEY = "sk-dummy-test-key"
    
    res = response_engine.generate_response(inp)
    
    print(f"Response (fallback template used: {res.is_fallback}):")
    print(f"'{res.final_text}'")
    print(f"Metadata model: {res.metadata.get('final_model')}")
    print(f"Counseling category determined: {res.metadata.get('counseling_category')}")
    
    # Check if 'motivasyon kaybı' is in output
    has_stressor = "motivasyon kaybı" in res.final_text
    print(f"Stale Stressor ('motivasyon kaybı') Injected? {has_stressor}")

print("\n=== END MANUAL VERIFICATION ===")
