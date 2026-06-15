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
from src.services.database import init_db, update_user_profile, get_or_create_profile

# Initialize database
init_db()

# Create manual test user profile
user_id = "test_manual_user_40d"
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

db_prof = get_or_create_profile(user_id)
update_user_profile(user_id, {"display_name": "Deniz"})

test_cases = [
    {
        "text": "Merhaba",
        "emotion": "neutral",
        "desc": "Case 1: 'Merhaba' greeting connection check."
    },
    {
        "text": "Bağlantı testi",
        "emotion": "neutral",
        "desc": "Case 2: 'Bağlantı testi' system check."
    },
    {
        "text": "Bugün kendimi çok kötü hissediyorum. Hiçbir şey yapmak istemiyorum.",
        "emotion": "sadness",
        "desc": "Case 3: Sadness / withdrawal cycle response check."
    },
    {
        "text": "Çok kaygılıyım, kalbim hızlı atıyor.",
        "emotion": "anxiety",
        "desc": "Case 4: Anxiety / body alarm response check."
    },
    {
        "text": "Kendimi çok suçlu hissediyorum, hata yaptım.",
        "emotion": "neutral",  # Will categorize by keyword
        "desc": "Case 5: Guilt / shame response check."
    },
    {
        "text": "Hayatımda ne yapacağımı bilmiyorum, kararsızlık beni tüketiyor.",
        "emotion": "neutral",  # Will categorize by keyword
        "desc": "Case 6: Uncertainty / ambiguity check."
    },
    {
        "text": "Hiçbir şey yapmak içimden gelmiyor, çok isteksizim.",
        "emotion": "neutral",  # Will categorize by keyword
        "desc": "Case 7: Motivation loss / activation loop check."
    },
    {
        "text": "Kendimi çok yalnız hissediyorum, kimse beni aramıyor.",
        "emotion": "neutral",  # Will categorize by keyword
        "desc": "Case 8: Loneliness check."
    }
]

print("=== START MANUAL QUALITY VERIFICATION (LOCAL FALLBACK MODE) ===")
for i, case in enumerate(test_cases, 1):
    print(f"\n[{i}/8] {case['desc']}")
    print(f"User Input: '{case['text']}'")
    
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
    
    # Force fallback provider by setting a dummy API key
    import src.core.config as config
    config.settings.OPENAI_API_KEY = "sk-dummy-test-key"
    
    res = response_engine.generate_response(inp)
    
    print(f"Fallback Used? {res.is_fallback}")
    print(f"Determined Category: {res.metadata.get('counseling_category')}")
    print(f"Response:\n  \"{res.final_text}\"\n")
    print("-" * 60)

print("\n=== END MANUAL QUALITY VERIFICATION ===")
