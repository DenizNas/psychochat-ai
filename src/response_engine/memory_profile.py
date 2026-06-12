import os
import json
import logging
from typing import Dict, Any, List
from src.ai.preprocessing import turkish_lower

logger = logging.getLogger(__name__)

# Enforce secure directory pathing
DATA_DIR = os.path.abspath("data/memory_profiles")
os.makedirs(DATA_DIR, exist_ok=True)

def get_profile_path(user_id: str) -> str:
    """Sanitizes user_id and guards against path traversal."""
    if ".." in user_id or "/" in user_id or "\\" in user_id:
        raise ValueError("Path traversal violation detected!")
        
    safe_user_id = "".join([c for c in user_id if c.isalnum() or c in ("-", "_")])
    if not safe_user_id:
        safe_user_id = "default_user"
    
    path = os.path.abspath(os.path.join(DATA_DIR, f"{safe_user_id}.json"))
    
    # Path traversal protection
    if not path.startswith(DATA_DIR):
        raise ValueError("Path traversal violation detected!")
    
    return path

def load_profile(user_id: str) -> Dict[str, Any]:
    """Loads a user's memory profile safely, returning a default empty structure if missing."""
    try:
        path = get_profile_path(user_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"PCE_PROFILE | Error loading profile for user {user_id}: {e}")
        
    return {
        "recurring_topics": [],
        "recurring_emotions": [],
        "goals": [],
        "stressors": [],
        "coping_methods": [],
        "positive_events": [],
        "relationship_context": [],
        "work_or_school_context": [],
        "last_advice_topics": []
    }

def save_profile(user_id: str, profile: Dict[str, Any]) -> None:
    """Saves the user profile structure to disk."""
    try:
        path = get_profile_path(user_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"PCE_PROFILE | Error saving profile for user {user_id}: {e}")

def add_to_profile(user_id: str, key: str, value: str) -> None:
    """Adds a unique entry to the profile list, capping size to avoid bloat."""
    profile = load_profile(user_id)
    if key not in profile:
        profile[key] = []
    
    val_clean = value.strip()
    if not val_clean:
        return
        
    val_lower = turkish_lower(val_clean)
    
    # Deduplication and incremental merge check
    exists = False
    for item in profile[key]:
        if val_lower in turkish_lower(item) or turkish_lower(item) in val_lower:
            exists = True
            break
            
    if not exists:
        profile[key].append(val_clean)
        # Cap size at 6 to keep context window footprint low
        if len(profile[key]) > 6:
            profile[key].pop(0)
        save_profile(user_id, profile)

def build_summary_for_prompt(user_id: str) -> str:
    """
    Compiles a highly factual, statement-based user summary.
    Enforces a strict cap of 10 lines maximum (including header).
    """
    profile = load_profile(user_id)
    lines = []
    
    # stressors
    if profile.get("stressors"):
        unique_stressors = list(dict.fromkeys(profile["stressors"]))[:2]
        for stressor in unique_stressors:
            lines.append(f"- Son zamanlarda {stressor} nedeniyle stres/kaygı yaşıyor olabilir.")
            
    # goals
    if profile.get("goals"):
        unique_goals = list(dict.fromkeys(profile["goals"]))[:2]
        for goal in unique_goals:
            goal_tr = {
                "anxiety reduction": "kaygıyı azaltma",
                "sleep improvement": "uyku düzenini iyileştirme",
                "mood awareness": "duygusal farkındalık geliştirme",
                "confidence building": "özgüven inşa etme",
                "social connection": "sosyal bağları güçlendirme",
                "stress management": "stres yönetimi"
            }.get(turkish_lower(goal), goal)
            lines.append(f"- Kendisi {goal_tr} konusunda odaklanmaya/gelişmeye çalışıyor.")
            
    # coping methods
    if profile.get("coping_methods"):
        unique_coping = list(dict.fromkeys(profile["coping_methods"]))[:2]
        for method in unique_coping:
            lines.append(f"- Kendisine iyi gelen/yardımcı olan baş etme yöntemi: {method}.")
            
    # relationships
    if profile.get("relationship_context"):
        unique_relations = list(dict.fromkeys(profile["relationship_context"]))[:1]
        for relation in unique_relations:
            lines.append(f"- Hayatındaki yakın ilişki durumu: {relation}.")
            
    # academic/work context
    if profile.get("work_or_school_context"):
        unique_contexts = list(dict.fromkeys(profile["work_or_school_context"]))[:1]
        for ctx in unique_contexts:
            lines.append(f"- Hayatındaki okul/iş/kariyer bağlamı: {ctx}.")

    # Strict capping (max 8 lines of body + 1 header = 9 lines total)
    lines = lines[:8]
    if not lines:
        return ""
        
    summary_header = "Kullanıcı Profil Özeti:"
    return summary_header + "\n" + "\n".join(lines)

def detect_and_add_advice_topics(user_id: str, assistant_response: str) -> None:
    """Scans the generated assistant response for suggested advice areas to track them."""
    profile = load_profile(user_id)
    if "last_advice_topics" not in profile:
        profile["last_advice_topics"] = []
        
    response_lower = turkish_lower(assistant_response)
    added_topics = []
    
    if any(k in response_lower for k in ["nefes egzersizi", "derin nefes", "nefes al", "nefes alıp ver", "nefesinizi"]):
        added_topics.append("breathing exercise")
        
    if any(k in response_lower for k in ["günlük tut", "yazmayı dene", "hislerini yaz", "günlüğe yaz", "günlük yaz"]):
        added_topics.append("journaling")
        
    if any(k in response_lower for k in ["uyku düzeni", "uyku saati", "uyku rutini", "ılık duş", "uyku öncesi"]):
        added_topics.append("sleep routine")
        
    if any(k in response_lower for k in ["sosyal bağ", "arkadaşlarınla", "yakınlarınla", "paylaşmak", "sosyalleş", "birine anlat"]):
        added_topics.append("social connection")

    if any(k in response_lower for k in ["yürüyüş", "yürümek", "yürüyüşe çık"]):
        added_topics.append("walking")
        
    for topic in added_topics:
        if topic not in profile["last_advice_topics"]:
            profile["last_advice_topics"].append(topic)
            
    # Cap size to last 4 suggested advice topics
    if len(profile["last_advice_topics"]) > 4:
        profile["last_advice_topics"] = profile["last_advice_topics"][-4:]
        
    save_profile(user_id, profile)

def get_advice_prevention_instructions(user_id: str) -> str:
    """Returns prompt instructions preventing repetition based on last recommended advice."""
    profile = load_profile(user_id)
    advice_list = profile.get("last_advice_topics", [])
    if not advice_list:
        return ""
        
    _ADVICE_MAP = {
        "breathing exercise": "nefes egzersizi",
        "journaling": "günlük tutma",
        "sleep routine": "uyku rutini",
        "social connection": "sosyal bağlantı kurma",
        "walking": "yürüyüş"
    }
    formatted_advice = ", ".join(_ADVICE_MAP.get(t, t) for t in advice_list)
    return (
        f"Son Önerilen Tavsiyeler: {formatted_advice}\n"
        "Tavsiye Tekrarını Önleme Kuralı: Yakın zamanda yukarıdaki tavsiyeler verilmişse, "
        "aynı önerileri şablon gibi tekrarlamaktan kaçın. Bunun yerine:\n"
        "- Geçen sefer nefes egzersizi gibi daha bedensel bir yöntemden gitmiştik; istersen bu kez başka bir şeye bakalım.\n"
        "- Bunu daha önce denediysen, aynı öneriyi tekrar etmek yerine alternatif bul.\n"
        "- Geçmişte neyin işe yaradığını sor."
    )
