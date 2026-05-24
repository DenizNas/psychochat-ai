import requests
import json
import sys

base_url = "http://127.0.0.1:8001"

# 1. Register test user
print("\n--- [Step 1] Registering test user ---")
username = "qa_tester_deniz"
password = "qa_password_123"
res_reg = requests.post(f"{base_url}/register", json={"username": username, "password": password})
print(f"Register Status: {res_reg.status_code}")
if res_reg.status_code not in [201, 409]:
    print(f"Register failed: {res_reg.text}")
    sys.exit(1)

# 2. Login and get token
print("\n--- [Step 2] Logging in ---")
res_log = requests.post(f"{base_url}/login", json={"username": username, "password": password})
print(f"Login Status: {res_log.status_code}")
if res_log.status_code != 200:
    print(f"Login failed: {res_log.text}")
    sys.exit(1)
token = res_log.json()["access_token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json; charset=utf-8"
}

# 3. GET /profile
print("\n--- [Step 3] Verification: GET /profile ---")
res_get = requests.get(f"{base_url}/profile", headers=headers)
print(f"GET Profile Status: {res_get.status_code}")
profile = res_get.json()
print("Returned Profile:")
print(json.dumps(profile, indent=2, ensure_ascii=False))

# Assert default values
assert profile["username"] == username
assert profile["preferred_language"] == "tr"
assert profile["response_style"] == "supportive"
assert profile["privacy_mode"] is False
assert profile["answer_length_preference"] == "medium"
print("✓ Default profile values asserted successfully!")

# 4. PUT /profile (Partial and Full updates, UTF-8 Turkish character validation)
print("\n--- [Step 4] Verification: PUT /profile (UTF-8, partial updates) ---")
update_data = {
    "display_name": "Deniz Nas",
    "bio": "Türkçe karakter testi: şıöçğÜİ - empati arıyorum.",
    "preferred_language": "tr",
    "response_style": "direct",
    "answer_length_preference": "short",
    "privacy_mode": True
}
res_put = requests.put(f"{base_url}/profile", headers=headers, json=update_data)
print(f"PUT Profile Status: {res_put.status_code}")
updated_profile = res_put.json()
print("Updated Profile:")
print(json.dumps(updated_profile, indent=2, ensure_ascii=False))

# Assert updated values and Turkish character preservation
assert updated_profile["display_name"] == "Deniz Nas"
assert "şıöçğÜİ" in updated_profile["bio"]
assert updated_profile["preferred_language"] == "tr"
assert updated_profile["response_style"] == "direct"
assert updated_profile["answer_length_preference"] == "short"
assert updated_profile["privacy_mode"] is True
print("✓ Updated profile values and Turkish character encoding verified!")

# 5. POST /profile/photo validation (Invalid payload, size limits, type check)
print("\n--- [Step 5] Verification: POST /profile/photo (Validation errors) ---")
# Send an invalid file type
files_invalid = {'file': ('test.txt', 'dummy content text', 'text/plain')}
res_photo_inv = requests.post(f"{base_url}/profile/photo", headers={"Authorization": f"Bearer {token}"}, files=files_invalid)
print(f"Upload Invalid Type Status (Expected 400): {res_photo_inv.status_code}")
print(f"Detail: {res_photo_inv.text}")
assert res_photo_inv.status_code == 400
assert "Sadece JPEG, PNG veya WEBP dosyaları kabul edilir" in res_photo_inv.json()["message"]
print("✓ File type validation check passed!")

# Send oversized file (2.5MB)
large_content = b"a" * (3 * 1024 * 1024) # 3MB
files_large = {'file': ('test.png', large_content, 'image/png')}
res_photo_large = requests.post(f"{base_url}/profile/photo", headers={"Authorization": f"Bearer {token}"}, files=files_large)
print(f"Upload Oversized File Status (Expected 400): {res_photo_large.status_code}")
print(f"Detail: {res_photo_large.text}")
assert res_photo_large.status_code == 400
assert "boyutu 2 MB" in res_photo_large.json()["message"]
print("✓ File size validation check passed!")

# 6. PUT /profile input validation constraints
print("\n--- [Step 6] Verification: PUT /profile input validation constraints ---")
# Empty display name
res_put_empty_name = requests.put(f"{base_url}/profile", headers=headers, json={"display_name": "   "})
print(f"PUT Empty Name Status (Expected 400): {res_put_empty_name.status_code}")
assert res_put_empty_name.status_code == 400
assert "Görünen ad boş bırakılamaz" in res_put_empty_name.json()["message"]

# Too long display name (>50 chars)
res_put_long_name = requests.put(f"{base_url}/profile", headers=headers, json={"display_name": "A" * 51})
print(f"PUT Long Name Status (Expected 400): {res_put_long_name.status_code}")
assert res_put_long_name.status_code == 400
assert "50 karakterden uzun olamaz" in res_put_long_name.json()["message"]

# Too long bio (>250 chars)
res_put_long_bio = requests.put(f"{base_url}/profile", headers=headers, json={"bio": "B" * 251})
print(f"PUT Long Bio Status (Expected 400): {res_put_long_bio.status_code}")
assert res_put_long_bio.status_code == 400
assert "250 karakterden uzun olamaz" in res_put_long_bio.json()["message"]

# Unsupported preference values
res_put_unsupported_lang = requests.put(f"{base_url}/profile", headers=headers, json={"preferred_language": "fr"})
print(f"PUT Unsupported Language Status (Expected 400): {res_put_unsupported_lang.status_code}")
assert res_put_unsupported_lang.status_code == 400
assert "Desteklenmeyen dil" in res_put_unsupported_lang.json()["message"]

print("✓ Input validation constraint checks passed!")

# 7. Direct Response Engine Prompt Building Verification (Mocking preference values)
print("\n--- [Step 7] Verification: Prompt and personal preferences AI injection ---")
from src.response_engine.prompts import build_system_prompt

# Test supportive + medium preferences prompt assembly
supportive_prefs = {
    "response_style": "supportive",
    "answer_length_preference": "medium"
}
prompt_supportive, meta_sup = build_system_prompt(language="tr", emotion="sadness", risk="Normal", preferences=supportive_prefs)
print(f"Assembled supportive system prompt sections: {meta_sup['prompt_sections']}")
assert "preferences" in meta_sup["prompt_sections"]
assert "KULLANICI TERCİHLERİ: Yanıtın nazik, teşvik edici ve umut verici olsun. Yanıtın orta uzunlukta olsun (3-5 cümle)." in prompt_supportive
print("✓ Supportive + Medium prompt preferences successfully verified!")

# Test direct + short preferences prompt assembly
direct_prefs = {
    "response_style": "direct",
    "answer_length_preference": "short"
}
prompt_direct, meta_dir = build_system_prompt(language="tr", emotion="sadness", risk="Normal", preferences=direct_prefs)
print(f"Assembled direct system prompt sections: {meta_dir['prompt_sections']}")
assert "KULLANICI TERCİHLERİ: Yanıtın net, pratik ve dolambaçsız olsun. Gereksiz teselli ifadelerinden kaçın. Yanıtını çok kısa tut (maksimum 1-2 cümle)." in prompt_direct
print("✓ Direct + Short prompt preferences successfully verified!")

# Test preferred_language response lang instruction
prompt_en, meta_en = build_system_prompt(language="en", emotion="neutral", risk="Normal", preferences=direct_prefs)
assert "Lütfen yanıtını tamamen 'en' dilinde ver." in prompt_en
print("✓ preferred_language is accurately injected as a direct instruction to the AI!")

# 8. Crisis overrides verification (Crisis situation ignores preferences completely)
print("\n--- [Step 8] Verification: Crisis override of preferences ---")
prompt_crisis, meta_crisis = build_system_prompt(language="tr", emotion="sadness", risk="kriz", preferences=direct_prefs)
print(f"Crisis prompt sections: {meta_crisis['prompt_sections']}")
assert "crisis" in meta_crisis["prompt_sections"]
assert "preferences" not in meta_crisis["prompt_sections"]
assert "KRİZ DURUMU — ÖNCELIK KURALI:" in prompt_crisis
assert "KULLANICI TERCİHLERİ" not in prompt_crisis
print("✓ Crisis overrides personal preferences completely in system prompts!")

# 9. Privacy Mode verification (privacy_mode=True disables memory extraction and injection)
print("\n--- [Step 9] Verification: Privacy Mode and memory manager interaction ---")
from src.response_engine.memory_manager import process_memory, clear_user_memory

# Clear any previous memory first
clear_user_memory(username)

# Try memory extraction while privacy_mode = True
print("Extracting with privacy_mode = True...")
meta_priv = process_memory(
    user_id=username,
    text="nefes egzersizi yapmak bana çok iyi geliyor.",
    emotion="neutral",
    risk="Normal",
    privacy_mode=True
)
print("Privacy Mode process_memory meta:", meta_priv)
assert meta_priv["memory_count"] == 0
assert meta_priv["selected_memory_count"] == 0
assert meta_priv["memory_injected"] is False
assert meta_priv["injection_text"] == ""

# Try memory extraction while privacy_mode = False
print("Extracting with privacy_mode = False...")
meta_pub = process_memory(
    user_id=username,
    text="nefes egzersizi yapmak bana çok iyi geliyor.",
    emotion="neutral",
    risk="Normal",
    privacy_mode=False
)
print("Public Mode process_memory meta:", meta_pub)
assert meta_pub["memory_count"] > 0
assert meta_pub["selected_memory_count"] > 0
assert meta_pub["memory_injected"] is True
assert "Kullanıcı başa çıkma yöntemi olarak şunları ifade etti: nefes egzersizi yapmak bana çok iyi" in meta_pub["injection_text"]
print("✓ Privacy Mode constraints successfully verified! Memory pipeline turns off completely when privacy_mode is active.")

print("\n==============================================")
print("★ ALL FAZ 6 personal preferences QA verification steps passed successfully! ★")
print("==============================================")
