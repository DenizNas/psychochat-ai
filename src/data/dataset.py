import torch
import pandas as pd
from torch.utils.data import Dataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

class TextClassificationDataset(Dataset):
    """Generic dataset for text classification with Hugging Face tokenizers."""
    def __init__(self, texts, labels, tokenizer, max_length=128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            return_token_type_ids=False,
            padding='max_length',
            truncation=True,
            return_attention_mask=True,
            return_tensors='pt',
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

def load_and_split_data(csv_path, text_col='text', label_col='label', test_size=0.1, val_size=0.1, random_state=42):
    """
    Loads data from a CSV, encodes labels (handles strings/ints dynamically),
    and creates an 80/10/10 Stratified Split.
    Returns:
       (train_docs, train_labels), (val_docs, val_labels), (test_docs, test_labels), label_encoder
    """
    df = pd.read_csv(csv_path)
    # Drop rows missing text or label
    df = df.dropna(subset=[text_col, label_col])
    
    # Label encoding (converts strings like 'joy' or integers like '0' uniformly to 0..N-1)
    le = LabelEncoder()
    df['encoded_label'] = le.fit_transform(df[label_col].astype(str))
    
    texts = df[text_col].tolist()
    labels = df['encoded_label'].tolist()
    
    # 1. Split off test set (10%)
    train_val_texts, test_texts, train_val_labels, test_labels = train_test_split(
        texts, labels, 
        test_size=test_size, 
        random_state=random_state, 
        stratify=labels
    )
    
    # 2. Extract relative validation size from remaining 90% (e.g. 10/90 = 0.1111)
    val_ratio = val_size / (1.0 - test_size)
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        train_val_texts, train_val_labels, 
        test_size=val_ratio, 
        random_state=random_state, 
        stratify=train_val_labels
    )
    
    return (train_texts, train_labels), (val_texts, val_labels), (test_texts, test_labels), le
