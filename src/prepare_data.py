import pandas as pd
from sklearn.model_selection import train_test_split

# 1️⃣ VERİYİ OKU
df = pd.read_csv("data/emotions.csv")

print("İlk Veriler:")
print(df.head())

# 2️⃣ LABEL → ANLAM
label_map = {
    0:"sadness",
    1:"joy",
    2:"love",
    3:"anger",
    4:"fear",
    5:"suprise"
}

df["emotion"] = df["label"].map(label_map)

# 3️⃣ PROJEYE UYGUN HALE GETİR
new_map = {
    "joy": "mutlu",
    "love": "mutlu",
    "sadness": "üzgün",
    "anger": "öfkeli",
    "fear": "kaygılı",
    "surprise": "nötr"
}

df["new_label"] = df["emotion"].map(new_map)

# 4️⃣ SAYISAL LABEL
final_map = {
    "mutlu": 0,
    "üzgün": 1,
    "kaygılı": 2,
    "öfkeli": 3,
    "nötr": 4
}

df["label"] = df["new_label"].map(final_map)
df = df.dropna()
df["label"] = df["label"].astype(int)

# 5️⃣ TEMİZLEME
df["text"] = df["text"].str.lower()
df = df.dropna()
df = df.drop_duplicates()

# 6️⃣ TRAIN / TEST SPLIT
train_texts, test_texts, train_labels, test_labels = train_test_split(
    df["text"],
    df["label"],
    test_size=0.2,
    random_state=42
)

# 7️⃣ TEMİZ VERİYİ KAYDET
df.to_csv("data/cleaned_emotions.csv", index=False)

print("Temiz veri kaydedildi ✅")
print(df["label"].value_counts())