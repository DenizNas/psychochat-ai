import sys
import os

sys.path.insert(0, ".")

from src.response_engine.prompts import build_system_prompt

test_prompts = [
    ("Bugün çok üzgünüm çünkü hiçbir şey yolunda gitmiyor.", "sadness"),
    ("İçimde garip bir sıkışma var ve kaygım artıyor.", "anxiety"),
    ("Kendimi yalnız hissediyorum ama kimseye anlatamıyorum.", "sadness")
]

print("================ MANUAL PROMPT GENERATION VERIFICATION ================\n")

for text, emotion in test_prompts:
    prompt, meta = build_system_prompt(
        language="tr",
        emotion=emotion,
        risk="Normal",
        text=text
    )
    
    print(f"--- USER TEXT: \"{text}\" (Simulated Emotion: {emotion.upper()}) ---")
    print(f"Detected Category: {meta['counseling_category'].upper()}")
    print(f"Prompt Version: {meta['prompt_version']}")
    print(f"Prompt Sections: {meta['prompt_sections']}")
    print("-" * 50)
    # Find response style rules and few-shot examples inside the generated system prompt
    style_idx = prompt.find("TEPKİ STİLİ VE YANSITMA KURALLARI")
    few_shot_idx = prompt.find("DANIŞAN-ASİSTAN YANIT ÖRNEKLERİ")
    
    if style_idx != -1:
        print("[STYLE RULES SECTION SAMPLE]")
        print(prompt[style_idx:style_idx+400])
        print("...")
    if few_shot_idx != -1:
        print("\n[FEW-SHOT EXAMPLES SECTION]")
        print(prompt[few_shot_idx:])
    
    print("=" * 80 + "\n")
