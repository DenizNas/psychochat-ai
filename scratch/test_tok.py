import torch
from transformers import BertTokenizer, BertForSequenceClassification
import torch.nn.functional as F

sentences = [
    "Kendimi çok çaresiz hissediyorum, hiçbir şeyin anlamı kalmadı.",
    "Bugün hava çok güzel, kendimi harika hissediyorum!",
    "Çok öfkeliyim, herkes üstüme geliyor.",
    "Sadece ağlamak istiyorum.",
    "Sınav sonuçlarımı bekliyorum, çok heyecanlıyım."
]

emo_labels = {0: "Anger", 1: "Anxiety", 2: "Fear", 3: "Happiness", 4: "Neutral", 5: "Sadness"}
cri_labels = {0: "Normal", 1: "Crisis"}

m_emo = BertForSequenceClassification.from_pretrained('models/emotion_model')
m_cri = BertForSequenceClassification.from_pretrained('models/crisis_model')

for tok_name in ['bert-base-uncased', 'bert-base-cased']:
    print(f"\n=== Tokenizer: {tok_name} ===")
    t = BertTokenizer.from_pretrained(tok_name)
    for s in sentences:
        inputs = t(s, return_tensors='pt')
        with torch.no_grad():
            out_emo = m_emo(**inputs)
            out_cri = m_cri(**inputs)
            
            prob_emo = F.softmax(out_emo.logits, dim=1)
            prob_cri = F.softmax(out_cri.logits, dim=1)
            
            val_emo, idx_emo = torch.max(prob_emo, dim=1)
            val_cri, idx_cri = torch.max(prob_cri, dim=1)
            
            print(f"Text: {s}")
            print(f"  Emotion: {emo_labels[idx_emo.item()]} (conf: {val_emo.item():.4f})")
            print(f"  Crisis : {cri_labels[idx_cri.item()]} (conf: {val_cri.item():.4f})")
