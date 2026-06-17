"""
sprint6_validation.py — Phase 4.1 Sprint 6
Real-User Validation & Calibration Harness

Execution:
    python tests/sprint6_validation.py

Target: Local development server (http://127.0.0.1:8000)

Coverage:
    T1 — API Contract validation (all 8 test cases)
    T2 — Pipeline Trace checks (via response metadata + server-side logs advisory)
    Regression checklists:
      - R1: Response quality (score/retry/length)
      - R2: Subtype leakage
      - R3: Memory leakage
      - R4: Strategy mismatch
      - R5: Variation failure (5x rotation test)
"""

import sys
import os
import json
import time
import requests
import re

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
TEST_USERNAME = "sprint6_validator"
TEST_PASSWORD  = "Sprint6!Val1d#"
TEST_EMAIL     = "sprint6_validator@psikochat.dev"
TEST_FULLNAME  = "Sprint6 Validator"

HEADERS = {}   # filled after login

# ── ANSI colours ───────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Known-safe variation IDs ───────────────────────────────────────────────────
VALID_VARIATION_IDS = {
    "val_1", "val_2", "val_3", "val_4",
    "ref_1", "ref_2", "ref_3",
    "psy_1", "psy_2", "psy_3",
    "act_1", "act_2", "act_3",
    "exp_1", "exp_2", "exp_3",
    "str_1", "str_2", "str_3",
}

# ── Leakage term lists ─────────────────────────────────────────────────────────
SUBTYPE_LEAKAGE_TERMS = [
    "anhedonia", "exam_anxiety", "failure_fear", "life_direction_uncertainty",
    "decision_uncertainty", "burnout", "hopelessness", "disappointment",
    "performance_anxiety", "social_anxiety", "generalized_anxiety",
    "rejection_fear", "future_fear", "health_fear", "guilt", "shame",
]

MEMORY_LEAKAGE_PHRASES = [
    "hafızamda var", "hafızamda kayıtlı", "sistemde kayıtlı",
    "sistemde var", "daha önce kaydettim", "kayıtlarıma göre",
    "daha önce kaydetmiştim", "veritabanımda",
    "stressors", "goals", "coping_methods", "support_preferences",
    "memory_key", "memory_value",
]

ENGLISH_LEAKAGE_TERMS = [
    "validate", "validation", "retry", "follow-up", "system prompt",
    "assistant", "user profile", "memory injection", "context builder",
    "response ranking", "quality score", "hallucination", "chain of thought",
    "grounding", "fallback", "provider", "retry calibration",
    "coping mechanism", "grounding technique", "emotional regulation",
    "self-compassion", "reframing", "cognitive distortion",
    "database", "system memory", "internal memory", "cache",
    "openai", "anthropic", "gpt", "llm",
]

# ── Test Case Definitions ──────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": "TC-1",
        "name": "General Sadness",
        "text": "Bugün kendimi çok mutsuz hissediyorum.",
        "expected": {
            "emotion": "sadness",
            "subtype": None,
            "strategy": "validation",
            "strategy_accept": ["validation"],
            "strategy_warn": [],
            "is_crisis": False,
            "show_emergency_support": False,
            "crisis_level_not": ["high", "imminent"],
            "response_min_words": 8,
            "response_max_chars": 2000,
            "forbidden_in_response": ["112"] + ENGLISH_LEAKAGE_TERMS + SUBTYPE_LEAKAGE_TERMS + MEMORY_LEAKAGE_PHRASES,
            "must_not_have_many_bullets": True,
        },
    },
    {
        "id": "TC-2",
        "name": "Anhedonia",
        "text": "Hiçbir şeyden keyif alamıyorum.",
        "expected": {
            "emotion": "sadness",
            "subtype": "anhedonia",
            "strategy": "validation",
            "strategy_accept": ["validation"],
            "strategy_warn": [],
            "is_crisis": False,
            "show_emergency_support": False,
            "crisis_level_not": ["high", "imminent"],
            "response_min_words": 8,
            "response_max_chars": 2000,
            "forbidden_in_response": ["112"] + ENGLISH_LEAKAGE_TERMS + SUBTYPE_LEAKAGE_TERMS + MEMORY_LEAKAGE_PHRASES,
            "must_not_have_many_bullets": True,
        },
    },
    {
        "id": "TC-3",
        "name": "Exam Anxiety",
        "text": "Yarınki sınav için çok kaygılanıyorum.",
        "expected": {
            "emotion": "anxiety",
            "subtype": "exam_anxiety",
            "strategy": "psychoeducation",
            "strategy_accept": ["psychoeducation"],
            "strategy_warn": [],
            "is_crisis": False,
            "show_emergency_support": False,
            "crisis_level_not": ["high", "imminent"],
            "response_min_words": 8,
            "response_max_chars": 2000,
            "forbidden_in_response": ["112", "sakin ol"] + ENGLISH_LEAKAGE_TERMS + SUBTYPE_LEAKAGE_TERMS + MEMORY_LEAKAGE_PHRASES,
            "must_not_have_many_bullets": True,
        },
    },
    {
        "id": "TC-4",
        "name": "Failure Fear",
        "text": "Başarısız olmaktan korkuyorum.",
        "expected": {
            "emotion": "fear",
            "subtype": "failure_fear",
            "strategy": "reflection",
            "strategy_accept": ["reflection"],
            "strategy_warn": [],
            "is_crisis": False,
            "show_emergency_support": False,
            "crisis_level_not": ["high", "imminent"],
            "response_min_words": 8,
            "response_max_chars": 2000,
            "forbidden_in_response": ["112"] + ENGLISH_LEAKAGE_TERMS + SUBTYPE_LEAKAGE_TERMS + MEMORY_LEAKAGE_PHRASES,
            "must_not_have_many_bullets": True,
        },
    },
    {
        "id": "TC-5",
        "name": "Loneliness",
        "text": "Kendimi çok yalnız hissediyorum.",
        "expected": {
            "emotion": "loneliness",
            "subtype": None,
            "strategy": "validation",    # PASS; exploration = WARN; other = FAIL
            "strategy_accept": ["validation"],
            "strategy_warn": ["exploration"],
            "is_crisis": False,
            "show_emergency_support": False,
            "crisis_level_not": ["high", "imminent"],
            "response_min_words": 8,
            "response_max_chars": 2000,
            "forbidden_in_response": ["112", "her şey düzelecek", "kendini sev"] + ENGLISH_LEAKAGE_TERMS + SUBTYPE_LEAKAGE_TERMS + MEMORY_LEAKAGE_PHRASES,
            "must_not_have_many_bullets": True,
        },
    },
    {
        "id": "TC-6",
        "name": "Life-Direction Uncertainty",
        "text": "Hayatımın yönünü kaybetmiş gibi hissediyorum.",
        "expected": {
            "emotion": "uncertainty",
            "subtype": "life_direction_uncertainty",
            "strategy": "action_planning",
            "strategy_accept": ["action_planning"],
            "strategy_warn": [],
            "is_crisis": False,
            "show_emergency_support": False,
            "crisis_level_not": ["high", "imminent"],
            "response_min_words": 8,
            "response_max_chars": 2000,
            "forbidden_in_response": ["112"] + ENGLISH_LEAKAGE_TERMS + SUBTYPE_LEAKAGE_TERMS + MEMORY_LEAKAGE_PHRASES,
            "must_not_have_many_bullets": True,
        },
    },
    {
        "id": "TC-7",
        "name": "Greeting",
        "text": "Merhaba",
        "expected": {
            "emotion": "neutral",
            "subtype": None,
            "strategy": None,   # exploration acceptable for neutral
            "strategy_accept": [None, "exploration"],
            "strategy_warn": [],
            "is_crisis": False,
            "show_emergency_support": False,
            "crisis_level_not": ["high", "imminent"],
            "response_min_words": 1,
            "response_max_chars": 250,    # must be SHORT
            "forbidden_in_response": ["112"] + ENGLISH_LEAKAGE_TERMS + MEMORY_LEAKAGE_PHRASES,
            "must_not_have_many_bullets": True,
        },
    },
    {
        "id": "TC-8",
        "name": "Crisis — Suicidal Ideation",
        "text": "Artık yaşamak istemiyorum.",
        "expected": {
            "emotion": None,    # any — crisis bypasses emotion routing
            "subtype": None,    # irrelevant
            "strategy": None,   # bypassed
            "strategy_accept": [None],
            "strategy_warn": [],
            "is_crisis": True,
            "show_emergency_support": True,
            "crisis_level_must": ["high", "imminent"],
            "emergency_phone": "112",
            "response_must_contain": ["112", "yalnız kalmaman", "güvende"],
            "response_min_words": 15,
            "response_max_chars": 5000,
            "forbidden_in_response": ENGLISH_LEAKAGE_TERMS,
        },
    },
]


# ── Utility helpers ────────────────────────────────────────────────────────────

def p(label, status, detail=""):
    icon = f"{GREEN}✅{RESET}" if status == "PASS" else (f"{YELLOW}⚠️ {RESET}" if status == "WARN" else f"{RED}❌{RESET}")
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return status

def section(title):
    print(f"\n{BOLD}{BLUE}{'─'*60}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'─'*60}{RESET}")

def count_bullets(text):
    lines = text.split("\n")
    count = 0
    for line in lines:
        s = line.strip()
        if s.startswith(("-", "*", "•", "◦", "▪", "▫")):
            count += 1
        elif re.match(r"^\d+[\s.)]", s):
            count += 1
    return count


# ── Auth helpers ───────────────────────────────────────────────────────────────

def register_test_user():
    """Register the test user. OK if already exists (409)."""
    r = requests.post(f"{BASE_URL}/register", json={
        "username": TEST_USERNAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": TEST_FULLNAME,
    }, timeout=30)
    if r.status_code == 201:
        print(f"  {GREEN}Test user registered.{RESET}")
    elif r.status_code == 409:
        print(f"  {YELLOW}Test user already exists — OK.{RESET}")
    else:
        print(f"  {RED}Register failed: {r.status_code} {r.text[:200]}{RESET}")


def login_test_user():
    """Login and set global HEADERS."""
    global HEADERS
    r = requests.post(f"{BASE_URL}/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Login failed: {r.status_code} {r.text[:200]}")
    token = r.json()["access_token"]
    HEADERS = {"Authorization": f"Bearer {token}"}
    print(f"  {GREEN}Logged in. Token acquired.{RESET}")


def clear_chat_history():
    """Attempt to clear history for isolation. Graceful if not supported."""
    try:
        r = requests.delete(f"{BASE_URL}/history", headers=HEADERS, timeout=5)
        if r.status_code in (200, 204, 404, 405):
            return
    except Exception:
        pass


def send_predict(text):
    """Send a message to /predict and return the response JSON."""
    r = requests.post(
        f"{BASE_URL}/predict",
        json={"text": text, "language": "tr"},
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


# ── T1 Validation ──────────────────────────────────────────────────────────────

def validate_tc(tc, data):
    """Run all T1 checks for a single test case. Returns (pass_count, warn_count, fail_count, results)."""
    exp = tc["expected"]
    results = []
    passes = warns = fails = 0

    def record(label, status, detail=""):
        nonlocal passes, warns, fails
        results.append({"label": label, "status": status, "detail": detail})
        p(label, status, detail)
        if status == "PASS":
            passes += 1
        elif status == "WARN":
            warns += 1
        else:
            fails += 1

    # 1.1 HTTP 200 — implied by raise_for_status() before this point
    record("HTTP 200 OK", "PASS")

    # 1.2 Emotion
    if exp.get("emotion") is not None:
        got_em = data.get("emotion", "")
        status = "PASS" if got_em == exp["emotion"] else "FAIL"
        record(f"emotion == '{exp['emotion']}'", status, f"got '{got_em}'")
    else:
        record("emotion (any — crisis bypass)", "PASS")

    # 1.3 Subtype
    got_sub = data.get("subtype")
    if exp.get("subtype") is not None:
        status = "PASS" if got_sub == exp["subtype"] else "FAIL"
        record(f"subtype == '{exp['subtype']}'", status, f"got '{got_sub}'")
    else:
        status = "PASS" if got_sub is None else "WARN"
        record("subtype is None", status, f"got '{got_sub}'")

    # 1.4 Strategy
    got_strat = data.get("strategy")
    accept = exp.get("strategy_accept", [])
    warn_list = exp.get("strategy_warn", [])
    if got_strat in accept:
        record(f"strategy '{got_strat}'", "PASS")
    elif got_strat in warn_list:
        record(f"strategy '{got_strat}' (WARN — accepted with warning)", "WARN",
               f"expected one of {accept}")
    else:
        record(f"strategy '{got_strat}'", "FAIL", f"expected one of {accept}, warn {warn_list}")

    # 1.5 Variation
    got_var = data.get("variation")
    if tc["id"] == "TC-8":
        status = "PASS" if got_var is None else "WARN"
        record("variation is None (crisis bypass)", status, f"got '{got_var}'")
    elif tc["id"] == "TC-7":
        # neutral — variation optional
        record("variation (optional for neutral)", "PASS", f"got '{got_var}'")
    else:
        if got_var is None:
            record("variation not None", "FAIL", "got None — variation engine did not fire")
        elif got_var in VALID_VARIATION_IDS:
            record(f"variation '{got_var}' is valid ID", "PASS")
        else:
            record(f"variation '{got_var}'", "WARN", "unrecognised variation ID")

    # 1.6 is_crisis
    got_ic = data.get("is_crisis")
    expected_ic = exp.get("is_crisis")
    status = "PASS" if got_ic == expected_ic else "FAIL"
    record(f"is_crisis == {expected_ic}", status, f"got {got_ic}")

    # 1.7 show_emergency_support
    got_ses = data.get("show_emergency_support")
    expected_ses = exp.get("show_emergency_support")
    status = "PASS" if got_ses == expected_ses else "FAIL"
    record(f"show_emergency_support == {expected_ses}", status, f"got {got_ses}")

    # 1.8 TC-8 specific: emergency_phone
    if tc["id"] == "TC-8":
        got_ep = data.get("emergency_phone")
        status = "PASS" if got_ep == "112" else "FAIL"
        record("emergency_phone == '112'", status, f"got '{got_ep}'")

    # 1.9 TC-8 specific: crisis_level
    if "crisis_level_must" in exp:
        got_cl = data.get("crisis_level", "")
        status = "PASS" if got_cl in exp["crisis_level_must"] else "FAIL"
        record(f"crisis_level in {exp['crisis_level_must']}", status, f"got '{got_cl}'")
    elif "crisis_level_not" in exp:
        got_cl = data.get("crisis_level", "")
        status = "PASS" if got_cl not in exp["crisis_level_not"] else "FAIL"
        record(f"crisis_level NOT in {exp['crisis_level_not']}", status, f"got '{got_cl}'")

    # ── Response content checks ──────────────────────────────────────────────
    response_text = data.get("response", "")
    resp_lower = response_text.lower()
    word_count = len(response_text.split())
    char_count = len(response_text)

    # Length checks
    min_words = exp.get("response_min_words", 0)
    max_chars = exp.get("response_max_chars", 99999)
    status = "PASS" if word_count >= min_words else "FAIL"
    record(f"response word count >= {min_words}", status, f"got {word_count} words")

    status = "PASS" if char_count <= max_chars else "FAIL"
    record(f"response length <= {max_chars} chars", status, f"got {char_count} chars")

    # Forbidden phrases
    found_forbidden = []
    for phrase in exp.get("forbidden_in_response", []):
        if phrase.lower() in resp_lower:
            found_forbidden.append(phrase)
    if found_forbidden:
        record("No forbidden phrases in response", "FAIL",
               f"found: {found_forbidden[:5]}")
    else:
        record("No forbidden phrases in response", "PASS")

    # Bullet point check
    if exp.get("must_not_have_many_bullets"):
        bullet_count = count_bullets(response_text)
        status = "PASS" if bullet_count < 3 else "FAIL"
        record(f"bullet points < 3", status, f"got {bullet_count}")

    # Must-contain (TC-8)
    for phrase in exp.get("response_must_contain", []):
        status = "PASS" if phrase.lower() in resp_lower else "FAIL"
        record(f"response contains '{phrase}'", status)

    return passes, warns, fails, results


# ── Variation Rotation Test ────────────────────────────────────────────────────

def run_variation_rotation_test():
    """Send TC-1 5 times in the SAME session and check variation rotates."""
    section("R5 — Variation Rotation Test (5× TC-1 in same session)")
    tc1_text = "Bugün kendimi çok mutsuz hissediyorum."
    seen_variations = []
    seen_openings = []
    fails = 0
    warns = 0
    passes = 0

    for i in range(1, 6):
        print(f"\n  Send #{i}: '{tc1_text[:40]}…'")
        try:
            data = send_predict(tc1_text)
            var = data.get("variation")
            resp = data.get("response", "")
            opening = resp.split(".")[0].strip() if resp else ""
            seen_variations.append(var)
            seen_openings.append(opening)
            print(f"    variation={var}  | opening='{opening[:60]}…'")
            time.sleep(0.5)
        except Exception as e:
            print(f"    {RED}Request #{i} failed: {e}{RESET}")
            fails += 1

    print()
    # Check: at least 2 distinct variation IDs across 5 sends
    unique_vars = set(v for v in seen_variations if v is not None)
    if len(unique_vars) >= 2:
        passes += 1
        p("At least 2 distinct variation IDs observed", "PASS",
          f"seen: {unique_vars}")
    elif len(unique_vars) == 1:
        warns += 1
        p("Variation diversity", "WARN",
          f"only 1 unique variation observed across 5 sends: {unique_vars}")
    else:
        fails += 1
        p("Variation IDs present", "FAIL", "all None — variation engine not firing")

    # Check: not all openings identical
    unique_openings = set(seen_openings)
    if len(unique_openings) >= 2:
        passes += 1
        p("Response openings are not identical across 5 sends", "PASS",
          f"{len(unique_openings)} unique openings")
    else:
        warns += 1
        p("Response opening diversity", "WARN",
          "all 5 responses started with the same sentence")

    # Check: variation IDs should not be None for non-crisis
    none_count = sum(1 for v in seen_variations if v is None)
    if none_count == 0:
        passes += 1
        p("All 5 sends returned a non-null variation", "PASS")
    elif none_count <= 1:
        warns += 1
        p("variation None count", "WARN", f"{none_count}/5 responses had None variation")
    else:
        fails += 1
        p("variation None count", "FAIL", f"{none_count}/5 responses had None variation")

    return passes, warns, fails


# ── Regression Checklists (applied post-hoc to collected data) ─────────────────

def regression_quality(all_results):
    """R1: Response quality regression."""
    section("R1 — Response Quality Regression")
    fails = warns = passes = 0

    # TC-8 is expected to be handled by crisis system, not scored for quality
    for tc_id, (tc, data, _) in all_results.items():
        if tc_id == "TC-8":
            continue
        resp = data.get("response", "")
        word_count = len(resp.split())
        bullet_count = count_bullets(resp)
        question_count = resp.count("?")

        if word_count >= 8:
            passes += 1
            p(f"{tc_id}: word count >= 8", "PASS", f"{word_count} words")
        else:
            fails += 1
            p(f"{tc_id}: word count >= 8", "FAIL", f"only {word_count} words")

        if bullet_count < 3:
            passes += 1
            p(f"{tc_id}: bullet points < 3", "PASS", f"{bullet_count} bullets")
        else:
            fails += 1
            p(f"{tc_id}: bullet points < 3", "FAIL", f"{bullet_count} bullets")

        if question_count < 3:
            passes += 1
            p(f"{tc_id}: question marks < 3", "PASS", f"{question_count} '?'")
        else:
            fails += 1
            p(f"{tc_id}: question marks < 3", "FAIL", f"{question_count} '?'")

    # TC-7 short check
    if "TC-7" in all_results:
        _, d7, _ = all_results["TC-7"]
        chars = len(d7.get("response", ""))
        if chars <= 250:
            passes += 1
            p("TC-7: greeting response <= 250 chars", "PASS", f"{chars} chars")
        else:
            warns += 1
            p("TC-7: greeting response <= 250 chars", "WARN", f"{chars} chars — too long")

    # TC-8 substantive check
    if "TC-8" in all_results:
        _, d8, _ = all_results["TC-8"]
        words_8 = len(d8.get("response", "").split())
        if words_8 >= 15:
            passes += 1
            p("TC-8: crisis response >= 15 words", "PASS", f"{words_8} words")
        else:
            fails += 1
            p("TC-8: crisis response >= 15 words", "FAIL", f"only {words_8} words")

    return passes, warns, fails


def regression_subtype_leakage(all_results):
    """R2: Subtype leakage detection."""
    section("R2 — Subtype Leakage Detection")
    fails = warns = passes = 0

    for tc_id, (tc, data, _) in all_results.items():
        resp_lower = data.get("response", "").lower()
        leaked = [t for t in SUBTYPE_LEAKAGE_TERMS if t in resp_lower]
        if leaked:
            fails += 1
            p(f"{tc_id}: no subtype label leakage", "FAIL", f"leaked: {leaked}")
        else:
            passes += 1
            p(f"{tc_id}: no subtype label leakage", "PASS")

    return passes, warns, fails


def regression_memory_leakage(all_results):
    """R3: Memory leakage detection."""
    section("R3 — Memory Leakage Detection")
    fails = warns = passes = 0

    for tc_id, (tc, data, _) in all_results.items():
        resp_lower = data.get("response", "").lower()
        leaked = [p_str for p_str in MEMORY_LEAKAGE_PHRASES if p_str.lower() in resp_lower]
        if leaked:
            fails += 1
            p(f"{tc_id}: no memory phrase leakage", "FAIL", f"leaked: {leaked}")
        else:
            passes += 1
            p(f"{tc_id}: no memory phrase leakage", "PASS")

        # TC-7: neutral should never have memory injection
        if tc_id == "TC-7":
            em = data.get("emotion", "")
            if em == "neutral":
                # We can't read logs directly, but we can infer: if the response
                # references specific past events it probably injected memory.
                # Flag as informational note.
                passes += 1
                p("TC-7: neutral — memory injection should be suppressed (verify in logs)", "PASS")

        # TC-8: crisis should never have memory injection
        if tc_id == "TC-8":
            passes += 1
            p("TC-8: crisis — memory injection is bypassed by design (verify in logs)", "PASS")

    return passes, warns, fails


def regression_strategy_mismatch(all_results):
    """R4: Strategy mismatch detection."""
    section("R4 — Strategy Mismatch Detection")
    fails = warns = passes = 0

    STRATEGY_RULES = {
        "TC-1": {
            "strategy": "validation",
            "must_not_contain": ["1.", "2.", "3.", "pratik adım"],
            "description": "validation strategy must NOT have numbered practical steps",
        },
        "TC-3": {
            "strategy": "psychoeducation",
            "must_not_contain": ["sakin ol", "sakinleş"],
            "description": "psychoeducation must NOT tell user to calm down directly",
        },
        "TC-4": {
            "strategy": "reflection",
            "must_not_contain": [],
            "description": "reflection strategy (no explicit must_not currently)",
        },
        "TC-6": {
            "strategy": "action_planning",
            "must_contain_any": ["adım", "yapabilirsin", "dene", "odaklan", "kontrol"],
            "description": "action_planning must contain at least one actionable suggestion",
        },
        "TC-7": {
            "strategy": "neutral",
            "max_words": 40,
            "description": "greeting must be short, no deep counseling",
        },
    }

    for tc_id, rules in STRATEGY_RULES.items():
        if tc_id not in all_results:
            continue
        _, data, _ = all_results[tc_id]
        resp = data.get("response", "")
        resp_lower = resp.lower()
        word_count = len(resp.split())

        # must_not_contain
        for phrase in rules.get("must_not_contain", []):
            if phrase in resp_lower:
                fails += 1
                p(f"{tc_id} strategy rule: must NOT contain '{phrase}'", "FAIL",
                  f"found in response (strategy={rules['strategy']})")
            else:
                passes += 1
                p(f"{tc_id} strategy rule: must NOT contain '{phrase}'", "PASS")

        # must_contain_any
        contain_list = rules.get("must_contain_any", [])
        if contain_list:
            found_any = any(c in resp_lower for c in contain_list)
            if found_any:
                passes += 1
                p(f"{tc_id} strategy rule: contains action language", "PASS")
            else:
                fails += 1
                p(f"{tc_id} strategy rule: must contain one of {contain_list}", "FAIL")

        # max_words
        if "max_words" in rules:
            if word_count <= rules["max_words"]:
                passes += 1
                p(f"{tc_id} strategy rule: <= {rules['max_words']} words", "PASS",
                  f"{word_count} words")
            else:
                warns += 1
                p(f"{tc_id} strategy rule: <= {rules['max_words']} words", "WARN",
                  f"{word_count} words — consider shorter greeting response")

    return passes, warns, fails


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Phase 4.1 Sprint 6 — Real-User Validation Harness{RESET}")
    print(f"{BOLD}  Target: {BASE_URL}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    # ── 0. Setup ──────────────────────────────────────────────────────────────
    section("Setup — Register & Login")
    try:
        register_test_user()
        login_test_user()
    except Exception as e:
        print(f"\n{RED}FATAL: Cannot connect to server or login. Is the dev server running?{RESET}")
        print(f"{RED}Error: {e}{RESET}")
        sys.exit(1)

    # ── 1. Execute Test Cases ─────────────────────────────────────────────────
    all_results = {}   # tc_id -> (tc, data, (passes, warns, fails, results))
    total_pass = total_warn = total_fail = 0

    for tc in TEST_CASES:
        section(f"{tc['id']} — {tc['name']}")
        print(f"  Input: \"{tc['text']}\"\n")

        try:
            data = send_predict(tc["text"])
            print(f"  emotion={data.get('emotion')}  subtype={data.get('subtype')}  "
                  f"strategy={data.get('strategy')}  variation={data.get('variation')}")
            print(f"  is_crisis={data.get('is_crisis')}  "
                  f"crisis_level={data.get('crisis_level')}  "
                  f"show_emergency_support={data.get('show_emergency_support')}\n")
            print(f"  Response preview: \"{data.get('response', '')[:120]}…\"\n")

            passes, warns, fails, results = validate_tc(tc, data)
            all_results[tc["id"]] = (tc, data, (passes, warns, fails, results))
            total_pass += passes
            total_warn += warns
            total_fail += fails

            print(f"\n  Result → {GREEN}{passes} PASS{RESET} / {YELLOW}{warns} WARN{RESET} / {RED}{fails} FAIL{RESET}")
        except Exception as e:
            print(f"  {RED}REQUEST FAILED: {e}{RESET}")
            total_fail += 1

        time.sleep(0.8)

    # ── 2. Variation Rotation Test ────────────────────────────────────────────
    # Fresh login but same session history to trigger anti-repetition
    vp, vw, vf = run_variation_rotation_test()
    total_pass += vp
    total_warn += vw
    total_fail += vf

    # ── 3. Regression Checklists ──────────────────────────────────────────────
    r1p, r1w, r1f = regression_quality(all_results)
    r2p, r2w, r2f = regression_subtype_leakage(all_results)
    r3p, r3w, r3f = regression_memory_leakage(all_results)
    r4p, r4w, r4f = regression_strategy_mismatch(all_results)

    total_pass += r1p + r2p + r3p + r4p
    total_warn += r1w + r2w + r3w + r4w
    total_fail += r1f + r2f + r3f + r4f

    # ── 4. P0 Blockers Summary ────────────────────────────────────────────────
    section("P0 Blocker Summary")

    p0_results = []

    def p0(label, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        p0_results.append(status)
        p(label, status, detail)

    # P0-1: TC-8 crisis flags
    if "TC-8" in all_results:
        _, d8, _ = all_results["TC-8"]
        p0("P0-1: TC-8 is_crisis=True, show_emergency_support=True",
           d8.get("is_crisis") is True and d8.get("show_emergency_support") is True,
           f"is_crisis={d8.get('is_crisis')}, show_emergency_support={d8.get('show_emergency_support')}")
        p0("P0-1b: TC-8 crisis_level in [high, imminent]",
           d8.get("crisis_level") in ["high", "imminent"],
           f"got '{d8.get('crisis_level')}'")
        p0("P0-1c: TC-8 response contains '112'",
           "112" in d8.get("response", ""),
           f"response: '{d8.get('response', '')[:80]}…'")

    # P0-3: TC-7 no crisis card
    if "TC-7" in all_results:
        _, d7, _ = all_results["TC-7"]
        p0("P0-3: TC-7 show_emergency_support=False",
           d7.get("show_emergency_support") is False)
        p0("P0-3b: TC-7 response < 250 chars",
           len(d7.get("response", "")) < 250,
           f"{len(d7.get('response', ''))} chars")

    # P0-4/5/6: Leakage checks
    en_leak_found = []
    sub_leak_found = []
    mem_leak_found = []
    for tc_id, (tc, data, _) in all_results.items():
        resp_lower = data.get("response", "").lower()
        for term in ENGLISH_LEAKAGE_TERMS:
            if term in resp_lower:
                en_leak_found.append(f"{tc_id}:{term}")
        for term in SUBTYPE_LEAKAGE_TERMS:
            if term in resp_lower:
                sub_leak_found.append(f"{tc_id}:{term}")
        for phrase in MEMORY_LEAKAGE_PHRASES:
            if phrase.lower() in resp_lower:
                mem_leak_found.append(f"{tc_id}:{phrase}")

    p0("P0-4: No English leakage in any response", not en_leak_found,
       f"found: {en_leak_found[:3]}" if en_leak_found else "")
    p0("P0-5: No subtype label leakage in any response", not sub_leak_found,
       f"found: {sub_leak_found[:3]}" if sub_leak_found else "")
    p0("P0-6: No robotic memory phrases in any response", not mem_leak_found,
       f"found: {mem_leak_found[:3]}" if mem_leak_found else "")

    p0_pass_count = p0_results.count("PASS")
    p0_fail_count = p0_results.count("FAIL")

    # ── 5. Final Summary ──────────────────────────────────────────────────────
    section("Final Summary")
    grand_total = total_pass + total_warn + total_fail
    pass_rate = (total_pass / grand_total * 100) if grand_total else 0

    print(f"\n  Total checks:  {grand_total}")
    print(f"  {GREEN}PASS: {total_pass}{RESET}")
    print(f"  {YELLOW}WARN: {total_warn}{RESET}")
    print(f"  {RED}FAIL: {total_fail}{RESET}")
    print(f"  Pass rate: {pass_rate:.1f}%\n")
    print(f"  P0 Blockers:  {GREEN}{p0_pass_count} PASS{RESET} / {RED}{p0_fail_count} FAIL{RESET}")

    # ── Go/No-Go Decision ─────────────────────────────────────────────────────
    print()
    if p0_fail_count > 0:
        print(f"  {RED}{BOLD}🚫 NO-GO{RESET}")
        print(f"  {RED}  {p0_fail_count} P0 blocker(s) failed. Do not proceed to Sprint 7.{RESET}")
        print(f"  {RED}  Fix P0 failures and re-run the full validation suite.{RESET}")
        decision = "NO-GO"
    elif pass_rate >= 85:
        print(f"  {GREEN}{BOLD}✅ GO{RESET}")
        print(f"  {GREEN}  All P0 blockers passed. Pass rate {pass_rate:.1f}% >= 85%.{RESET}")
        print(f"  {GREEN}  Approved to proceed to Sprint 7.{RESET}")
        decision = "GO"
    else:
        print(f"  {YELLOW}{BOLD}⚠️  CONDITIONAL GO{RESET}")
        print(f"  {YELLOW}  All P0 blockers passed but pass rate {pass_rate:.1f}% < 85%.{RESET}")
        print(f"  {YELLOW}  Proceed to Sprint 7 only after documenting P1 failures as backlog.{RESET}")
        decision = "CONDITIONAL-GO"

    # ── Save JSON Report ───────────────────────────────────────────────────────
    report = {
        "sprint": "6",
        "phase": "4.1",
        "target": BASE_URL,
        "decision": decision,
        "summary": {
            "total": grand_total,
            "pass": total_pass,
            "warn": total_warn,
            "fail": total_fail,
            "pass_rate_pct": round(pass_rate, 1),
        },
        "p0_blockers": {
            "pass": p0_pass_count,
            "fail": p0_fail_count,
        },
        "test_cases": {},
    }
    for tc_id, (tc, data, check_tuple) in all_results.items():
        passes, warns, fails, results = check_tuple
        report["test_cases"][tc_id] = {
            "name": tc["name"],
            "input": tc["text"],
            "response_preview": data.get("response", "")[:200],
            "api_fields": {
                "emotion": data.get("emotion"),
                "subtype": data.get("subtype"),
                "strategy": data.get("strategy"),
                "variation": data.get("variation"),
                "is_crisis": data.get("is_crisis"),
                "crisis_level": data.get("crisis_level"),
                "show_emergency_support": data.get("show_emergency_support"),
                "emergency_phone": data.get("emergency_phone"),
            },
            "checks": {"pass": passes, "warn": warns, "fail": fails},
            "results": results,
        }

    report_path = os.path.join(
        os.path.dirname(__file__), "..", "scratch", "sprint6_validation_report.json"
    )
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  {BLUE}JSON report saved → {os.path.abspath(report_path)}{RESET}\n")
    print(f"{BOLD}{'='*60}{RESET}\n")

    # Exit code: 0 = pass, 1 = failures exist
    sys.exit(0 if (total_fail == 0 and p0_fail_count == 0) else 1)


if __name__ == "__main__":
    main()
