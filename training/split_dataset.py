import os
import argparse
import pandas as pd
from sklearn.model_selection import train_test_split
import sys

def check_columns(df, required_cols):
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Eksik kolonlar: {missing}")

def do_stratified_split(df, stratify_col, test_ratio, val_ratio, seed):
    # train, temp split
    train_ratio = 1.0 - test_ratio - val_ratio
    temp_ratio = test_ratio + val_ratio
    
    try:
        train_df, temp_df = train_test_split(
            df, test_size=temp_ratio, stratify=df[stratify_col], random_state=seed
        )
        
        # We need to split temp_df into val and test
        val_prop = val_ratio / temp_ratio
        
        val_df, test_df = train_test_split(
            temp_df, test_size=(1.0 - val_prop), stratify=temp_df[stratify_col], random_state=seed
        )
    except ValueError as e:
        print(f"\n[HATA] '{stratify_col}' kolonu icin stratified split yapilirken hata olustu.")
        print(f"Detay: {e}")
        print("Bunun sebebi bazi siniflarda yeterli ornek olmamasi (oransal split icin sinif basina yetersiz veri) olabilir.")
        print("Dengesiz siniflari cogaltin veya ornek sayisi az olan siniflari birlestirin.")
        sys.exit(1)
        
    return train_df, val_df, test_df

def print_distribution(name, split_name, df, col):
    print(f"\n--- {name.upper()} {split_name.upper()} SPLIT Sınıf Dağılımı ---")
    print(f"Toplam Kayıt: {len(df)}")
    dist = df[col].value_counts(normalize=True).mul(100).round(2)
    for class_name, pct in dist.items():
        print(f"  - {class_name}: {pct}%")

def main():
    parser = argparse.ArgumentParser(description="Dataset Stratified Splitter")
    parser.add_argument("--input", type=str, required=True, help="Temiz dataset CSV yolu")
    parser.add_argument("--output-dir", type=str, required=True, help="Çıktı klasörü yolu")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    
    args = parser.parse_args()
    
    if abs((args.train_ratio + args.val_ratio + args.test_ratio) - 1.0) > 1e-5:
        print("HATA: Oranlarin toplami 1.0 olmalidir!")
        sys.exit(1)
        
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Dataset okunuyor: {args.input}")
    try:
        df = pd.read_csv(args.input, encoding="utf-8")
    except Exception as e:
        print(f"HATA: Dosya okunamadi: {e}")
        sys.exit(1)
        
    check_columns(df, ["text", "emotion", "crisis"])
    
    initial_len = len(df)
    df = df.drop_duplicates(subset=["text"])
    dedup_len = len(df)
    if initial_len != dedup_len:
        print(f"Bilgi: {initial_len - dedup_len} adet duplicate text kaydı silindi.")
    
    print("\n" + "="*40)
    print("[EMOTION] Split İşlemi Başlıyor...")
    print("="*40)
    e_train, e_val, e_test = do_stratified_split(df, "emotion", args.test_ratio, args.val_ratio, args.seed)
    
    print_distribution("Emotion", "Train", e_train, "emotion")
    print_distribution("Emotion", "Validation", e_val, "emotion")
    print_distribution("Emotion", "Test", e_test, "emotion")
    
    print("\n" + "="*40)
    print("[CRISIS] Split İşlemi Başlıyor...")
    print("="*40)
    c_train, c_val, c_test = do_stratified_split(df, "crisis", args.test_ratio, args.val_ratio, args.seed)
    
    print_distribution("Crisis", "Train", c_train, "crisis")
    print_distribution("Crisis", "Validation", c_val, "crisis")
    print_distribution("Crisis", "Test", c_test, "crisis")
    
    # Save splits
    print("\nDosyalar kaydediliyor...")
    
    # Emotion
    e_train.to_csv(os.path.join(args.output_dir, "emotion_train.csv"), index=False, encoding="utf-8")
    e_val.to_csv(os.path.join(args.output_dir, "emotion_val.csv"), index=False, encoding="utf-8")
    e_test.to_csv(os.path.join(args.output_dir, "emotion_test.csv"), index=False, encoding="utf-8")
    
    # Crisis
    c_train.to_csv(os.path.join(args.output_dir, "crisis_train.csv"), index=False, encoding="utf-8")
    c_val.to_csv(os.path.join(args.output_dir, "crisis_val.csv"), index=False, encoding="utf-8")
    c_test.to_csv(os.path.join(args.output_dir, "crisis_test.csv"), index=False, encoding="utf-8")
    
    print(f"\nİşlem tamamlandı! Bütün split dosyaları (utf-8 formatında) şu dizine kaydedildi: {args.output_dir}")

if __name__ == "__main__":
    main()
