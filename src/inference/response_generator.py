import os
import openai
from dotenv import load_dotenv
from src.services.database import get_chat_history, save_chat_message

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    openai.api_key = api_key
else:
    print("Warning: OPENAI_API_KEY not found in environment variables.")

MAX_MEMORY_LENGTH = 6 # Keep last 3 exchanges (3 user, 3 assistant)

def generate_response(text: str, emotion: str, risk: str, user_id: str = "default", language: str = "tr") -> str:
    if not openai.api_key:
        return "Üzgünüm, şu an sistemde bir bağlantı sorunu yaşıyorum (API Key eksik)."
        
    system_prompt = (
        "Sen anlayışlı, empatik ve profesyonel bir psikolojik destek asistanısın. "
        "Kullanıcının duygusal durumunu ve kriz riskini göz önünde bulundurarak ona en uygun, "
        "kısa ama etkili, destekleyici ve güvende hissettiren bir yanıt vermelisin. "
        "Asla tıbbi veya kesin klinik bir tanı koymamalısın. "
        f"Lütfen yanıtını tamamen '{language}' dilinde ver."
    )

    if str(risk).lower() in ["1", "crisis", "kriz"]:
        user_prompt = f"""Kullanıcı: '{text}'
Duygu: {emotion} | Kriz Riski: YÜKSEK
Görev: Kullanıcı kriz riskinde! Empatik ol, güvende hissettir ve onu yargılamadan dinlediğini belli et."""
    elif str(emotion).lower() in ["üzgün", "sad", "kaygılı", "fear", "öfkeli", "anger"]:
        user_prompt = f"""Kullanıcı: '{text}'
Duygu: {emotion} | Kriz Riski: Normal
Görev: Kullanıcı {emotion} hissediyor. Empatik bir dille ona destek ol."""
    else:
        user_prompt = f"""Kullanıcı: '{text}'
Duygu: {emotion} | Kriz Riski: Normal
Görev: Samimi ve sıcak bir sohbet yanıtı ver."""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Load history from SQLite
    history = get_chat_history(user_id, limit=MAX_MEMORY_LENGTH)
    messages.extend(history)
    
    # Add current
    messages.append({"role": "user", "content": user_prompt})

    # Try gpt-4o first, fallback to gpt-3.5-turbo
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=250,
            timeout=10 # Fast fail for crisis responsiveness
        )
        final_text = response.choices[0].message.content.strip()
    except Exception as e_4o:
        print(f"GPT-4o failed: {e_4o}. Falling back to gpt-3.5-turbo...")
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=250,
                timeout=10
            )
            final_text = response.choices[0].message.content.strip()
        except Exception as e_3_5:
            print(f"GPT-3.5 fallback also failed: {e_3_5}")
            return "Üzgünüm, şu an sana yanıt üretmekte zorlanıyorum. Lütfen daha sonra tekrar dene."

    # Update memory in DB
    save_chat_message(user_id, "user", text) # Store the clean text, not prompt
    save_chat_message(user_id, "assistant", final_text)

    return final_text
