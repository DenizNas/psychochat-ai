import os
import re
import random
import argparse
import pandas as pd
from collections import defaultdict
import sys

# Turkish character preserving sets
TR_CHARS = "çğıöşüÇĞİÖŞÜ"

# Synonym dictionaries (Extremely safe to preserve semantic meaning)
SYNONYMS = {
    "çok": ["oldukça", "fazlasıyla", "epey", "aşırı"],
    "kötü": ["berbat", "fena", "korkunç"],
    "iyi": ["harika", "güzel", "mükemmel"],
    "üzgün": ["mutsuz", "kederli", "kırgın"],
    "sinirli": ["öfkeli", "gergin", "kızgın"],
    "korkuyorum": ["endişeliyim", "panikteyim", "tedirginim"],
    "yardım": ["destek", "imdat"],
    "çaresiz": ["umutsuz"],
    "sürekli": ["devamlı", "durmadan"]
}

# Emotion-based Emojis
EMOJIS = {
    "Sadness": ["😔", "😢", "🥀"],
    "Anger": ["😡", "🤬", "😤"],
    "Anxiety": ["😰", "😨", "😟"],
    "Fear": ["😱", "😨", "🥶"],
    "Happiness": ["😊", "😁", "🌟"],
    "Neutral": ["...", "🙂"],
    "Crisis": ["🆘", "💔", "⚠️"]
}

# Typo maps (Common TR keyboard typos)
TYPO_MAP = {
    "i": "ı", "ı": "i",
    "o": "ö", "ö": "o",
    "u": "ü", "ü": "u",
    "s": "ş", "ş": "s",
    "c": "ç", "ç": "c",
    "g": "ğ", "ğ": "g"
}

def set_seed(seed):
    random.seed(seed)
    # pandas ve numpy default seed
    import numpy as np
    np.random.seed(seed)

def augment_synonym(text):
    words = text.split()
    augmented = False
    for i, word in enumerate(words):
        clean_word = re.sub(r'[^\w\s]', '', word.lower())
        if clean_word in SYNONYMS:
            replacement = random.choice(SYNONYMS[clean_word])
            if word.istitle():
                replacement = replacement.capitalize()
            words[i] = word.replace(clean_word, replacement, 1) if clean_word in word else replacement
            augmented = True
            break
    return " ".join(words) if augmented else text

def augment_typo(text):
    if len(text) < 5: return text
    chars = list(text)
    valid_indices = [i for i, c in enumerate(chars) if c.lower() in TYPO_MAP]
    if not valid_indices: return text
    idx = random.choice(valid_indices)
    char = chars[idx]
    is_upper = char.isupper()
    typo_char = TYPO_MAP[char.lower()]
    chars[idx] = typo_char.upper() if is_upper else typo_char
    return "".join(chars)

def augment_emoji(text, emotion, crisis):
    emoji_list = EMOJIS["Crisis"] if str(crisis) == "1" else EMOJIS.get(str(emotion), ["🤔"])
    return text + " " + random.choice(emoji_list)

def augment_punctuation(text):
    if text.endswith("."):
        return text[:-1] + "..."
    elif text.endswith("!"):
        return text + "!"
    elif not text.endswith(".") and not text.endswith("!") and not text.endswith("?"):
        return text + random.choice(["...", "!", "."])
    return text

def augment_paraphrase(text):
    prefixes = ["Açıkçası, ", "Bence ", "Şu an ", "Gerçekten "]
    if not any(text.startswith(p) for p in prefixes):
        return random.choice(prefixes) + text.lower()
    return text

def validate_text(text):
    if not text or len(text.strip()) < 3: return False
    if not any(c.isalpha() for c in text): return False
    return True

def generate_augmentations(row, techniques, crisis_multiplier=2):
    text = str(row['text'])
    emotion = str(row.get('emotion', 'Neutral'))
    crisis = str(row.get('crisis', '0'))
    
    augs = []
    num_augs = crisis_multiplier if crisis == "1" else 1
    
    for _ in range(num_augs):
        tech = random.choice(techniques)
        aug_text = text
        
        if tech == "synonym": aug_text = augment_synonym(text)
        elif tech == "typo": aug_text = augment_typo(text)
        elif tech == "emoji": aug_text = augment_emoji(text, emotion, crisis)
        elif tech == "punctuation": aug_text = augment_punctuation(text)
        elif tech == "paraphrase": aug_text = augment_paraphrase(text)
        
        if aug_text != text and validate_text(aug_text):
            augs.append((aug_text, tech))
            
    return augs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    
    print(f"Dataset okunuyor: {args.input}")
    try:
        df = pd.read_csv(args.input, encoding='utf-8')
    except Exception as e:
        print(f"HATA: Dosya okunamadi: {e}")
        sys.exit(1)
        
    required_cols = ['text', 'emotion', 'crisis']
    for col in required_cols:
        if col not in df.columns:
            print(f"HATA: Eksik kolon {col}")
            sys.exit(1)
            
    existing_texts = set(df['text'].astype(str).str.lower().str.strip().tolist())
    
    augmented_rows = []
    stats = defaultdict(int)
    duplicates_prevented = 0
    
    techniques = ["synonym", "typo", "emoji", "punctuation", "paraphrase"]
    
    print("Augmentation işlemi başlıyor...")
    for idx, row in df.iterrows():
        augs = generate_augmentations(row, techniques, crisis_multiplier=3)
        for aug_text, tech in augs:
            clean_aug = aug_text.lower().strip()
            if clean_aug in existing_texts:
                duplicates_prevented += 1
                continue
                
            existing_texts.add(clean_aug)
            stats[tech] += 1
            
            new_row = row.copy()
            new_row['text'] = aug_text
            new_row['is_augmented'] = True
            augmented_rows.append(new_row)
            
    df['is_augmented'] = False
    
    if augmented_rows:
        aug_df = pd.DataFrame(augmented_rows)
        final_df = pd.concat([df, aug_df], ignore_index=True)
    else:
        final_df = df
        
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    final_df.to_csv(args.output, index=False, encoding='utf-8')
    
    print("\n" + "="*40)
    print("AUGMENTATION RAPORU")
    print("="*40)
    print(f"Orijinal Kayıt Sayısı : {len(df)}")
    print(f"Üretilen Yeni Kayıt   : {len(augmented_rows)}")
    print(f"Toplam Kayıt Sayısı   : {len(final_df)}")
    print(f"Engellenen Kopya(Dup) : {duplicates_prevented}")
    print("\nKullanılan Teknikler:")
    for k, v in stats.items():
        print(f" - {k.capitalize():12} : {v}")
    print("="*40)
    print(f"Sonuç dosyası kaydedildi: {args.output}\n")

if __name__ == "__main__":
    main()
