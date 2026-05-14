import pandas as pd
import argparse
import os
import sys

# src modüllerinin çağrılabilmesi için proje root'unu path'e ekliyoruz.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.ai.preprocessing import prepare_model_input

VALID_EMOTIONS = {"happy", "sadness", "anger", "fear", "neutral"}

def validate_and_clean_row(row):
    text = row.get("text")
    emotion = row.get("emotion")
    crisis = row.get("crisis")
    
    # 1. Boş Text Kontrolü
    if pd.isna(text) or str(text).strip() == "":
        return None, "empty_text"
        
    # 2. Metin Temizliği ve Preprocessing
    try:
        clean_txt = prepare_model_input(str(text))
    except ValueError as e:
        # validate_input_text içinden dönen anlamsız metin hataları
        err_msg = str(e).lower()
        if "anlamlı" in err_msg or "emoji" in err_msg:
            return None, "meaningless_input"
        return None, "preprocessing_failed"
        
    # 3. Emotion Etiket Doğrulaması
    if pd.isna(emotion):
        return None, "invalid_emotion_label"
    emotion = str(emotion).strip().lower()
    if emotion not in VALID_EMOTIONS:
        return None, "invalid_emotion_label"
        
    # 4. Crisis Etiket Doğrulaması (0/1)
    if pd.isna(crisis):
        return None, "invalid_crisis_value"
    
    crisis_str = str(crisis).strip()
    if crisis_str not in ["0", "1", "0.0", "1.0"]:
        return None, "invalid_crisis_value"
        
    try:
        crisis_val = int(float(crisis_str))
    except ValueError:
        return None, "invalid_crisis_value"
        
    # Hataları aşan satırı temiz haliyle dönüyoruz
    cleaned_row = {
        "text": clean_txt,
        "emotion": emotion,
        "crisis": crisis_val
    }
    return cleaned_row, None

def main():
    parser = argparse.ArgumentParser(description="AI Psikolog Dataset Cleaning & Validation Pipeline")
    parser.add_argument("--input", type=str, default="data/raw/dataset.csv", help="Input dataset CSV path")
    parser.add_argument("--output", type=str, default="data/processed/clean_dataset.csv", help="Output dataset CSV path")
    
    args = parser.parse_args()
    invalid_rows_path = "data/processed/invalid_rows.csv"
    
    print(f"Reading dataset from: {args.input} (UTF-8)")
    
    if not os.path.exists(args.input):
        print(f"Error: Input file not found at {args.input}")
        sys.exit(1)
        
    try:
        df = pd.read_csv(args.input, encoding="utf-8")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)
        
    req_cols = {"text", "emotion", "crisis"}
    if not req_cols.issubset(df.columns):
        missing = req_cols - set(df.columns)
        print(f"Error: Missing columns in dataset: {missing}")
        sys.exit(1)
        
    total_initial = len(df)
    clean_records = []
    invalid_records = []
    seen_texts = set()
    
    for idx, row in df.iterrows():
        cleaned_dict, error_reason = validate_and_clean_row(row)
        
        if error_reason:
            invalid_row = row.to_dict()
            invalid_row["error_reason"] = error_reason
            invalid_records.append(invalid_row)
        else:
            text_val = cleaned_dict["text"]
            # 5. Duplicate Kontrolü
            if text_val in seen_texts:
                invalid_row = row.to_dict()
                invalid_row["error_reason"] = "duplicate_text"
                invalid_records.append(invalid_row)
            else:
                seen_texts.add(text_val)
                clean_records.append(cleaned_dict)
                
    clean_df = pd.DataFrame(clean_records)
    invalid_df = pd.DataFrame(invalid_records)
    
    # Çıktı Dizini Oluşturma
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(invalid_rows_path), exist_ok=True)
    
    # Temiz veriyi UTF-8 ile kaydet
    if not clean_df.empty:
        clean_df.to_csv(args.output, index=False, encoding="utf-8")
        print(f"Saved {len(clean_df)} clean rows to {args.output}")
    else:
        print("Warning: Clean dataset is empty!")
        
    # Hatalı (invalid) veriyi hata sebebiyle beraber kaydet
    if not invalid_df.empty:
        invalid_df.to_csv(invalid_rows_path, index=False, encoding="utf-8")
        print(f"Saved {len(invalid_df)} invalid rows to {invalid_rows_path}")
        
    # İstatistik Raporu
    print("\n" + "="*45)
    print("   DATASET CLEANING & VALIDATION REPORT   ")
    print("="*45)
    print(f"Initial Total Rows : {total_initial}")
    print(f"Final Clean Rows   : {len(clean_df)}")
    print(f"Invalid/Dropped    : {len(invalid_df)}")
    
    if not clean_df.empty:
        print("\n[Emotion Distribution]")
        print(clean_df["emotion"].value_counts().to_string())
        
        print("\n[Crisis Distribution]")
        print(clean_df["crisis"].value_counts().to_string())
        
    if not invalid_df.empty:
        print("\n[Invalid Reasons Distribution]")
        print(invalid_df["error_reason"].value_counts().to_string())
        
if __name__ == "__main__":
    main()
