import os
import torch
import json
from transformers import BertTokenizer, BertForSequenceClassification

# Mappings based on requested classes
EMOTION_MAP = {
    0: "mutlu",
    1: "üzgün",
    2: "kaygılı",
    3: "öfkeli",
    4: "nötr"
}

RISK_MAP = {
    0: "normal",
    1: "kriz"
}

class PsychochatPredictor:
    def __init__(self, emotion_model_path="models/emotion_model", crisis_model_path="models/crisis_model"):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load Emotion Model
        if os.path.exists(emotion_model_path):
            print(f"Loading emotion model from {emotion_model_path}...")
            self.emotion_tokenizer = BertTokenizer.from_pretrained(emotion_model_path)
            self.emotion_model = BertForSequenceClassification.from_pretrained(emotion_model_path)
        else:
            print(f"Warning: {emotion_model_path} not found. Using dbmdz/bert-base-turkish-cased base for demonstration.")
            self.emotion_tokenizer = BertTokenizer.from_pretrained("dbmdz/bert-base-turkish-cased")
            self.emotion_model = BertForSequenceClassification.from_pretrained("dbmdz/bert-base-turkish-cased", num_labels=5)
            
        self.emotion_model.to(self.device)
        self.emotion_model.eval()

        # Load Crisis Model
        if os.path.exists(crisis_model_path):
            print(f"Loading crisis model from {crisis_model_path}...")
            self.crisis_tokenizer = BertTokenizer.from_pretrained(crisis_model_path)
            self.crisis_model = BertForSequenceClassification.from_pretrained(crisis_model_path)
        else:
            print(f"Warning: {crisis_model_path} not found. Using dbmdz/bert-base-turkish-cased base for demonstration.")
            self.crisis_tokenizer = BertTokenizer.from_pretrained("dbmdz/bert-base-turkish-cased")
            self.crisis_model = BertForSequenceClassification.from_pretrained("dbmdz/bert-base-turkish-cased", num_labels=2)
            
        self.crisis_model.to(self.device)
        self.crisis_model.eval()

    def predict(self, text):
        # 1. Emotion Prediction
        emo_inputs = self.emotion_tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128).to(self.device)
        with torch.no_grad():
            emo_outputs = self.emotion_model(**emo_inputs)
            emo_logits = emo_outputs.logits
            emo_pred = torch.argmax(emo_logits, dim=1).item()
            
        emotion_label = EMOTION_MAP.get(emo_pred, "bilinmiyor")

        # 2. Crisis Prediction
        crisis_inputs = self.crisis_tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128).to(self.device)
        with torch.no_grad():
            crisis_outputs = self.crisis_model(**crisis_inputs)
            crisis_logits = crisis_outputs.logits
            crisis_pred = torch.argmax(crisis_logits, dim=1).item()
            
        risk_label = RISK_MAP.get(crisis_pred, "bilinmiyor")

        result = {
            "emotion": emotion_label,
            "risk": risk_label
        }
        
        return result

def run_tests():
    print("Initializing predictor...\n")
    predictor = PsychochatPredictor()
    
    test_sentences = [
        "Bugün harika bir gün, her şey çok yolunda!", # mutlu, normal
        "Kendimi çok umutsuz ve çaresiz hissediyorum, artık yaşamak istemiyorum.", # üzgün, kriz (intihar eğilimi)
        "Sınav sonuçlarım açıklanacak diye stresten ölüyorum, mideme kramplar giriyor.", # kaygılı, normal
        "Bana yapılan bu haksızlığa tahammül edemiyorum, çıldıracağım!", # öfkeli, normal
        "Bugün evde oturdum ve biraz kitap okudum, dümdüz bir gündü.", # nötr, normal
        "Canım çok yanıyor, kendime zarar vermeyi düşünüyorum.", # kriz
        "İşten kovuldum, ne yapacağımı bilemiyorum, çok kötüyüm.", # üzgün, normal
        "Kimse beni anlamıyor, tamamen yalnızım ve bu acı hiç bitmeyecek.", # kriz
        "Yarınki toplantı için hazırlıklarımı tamamladım ama yine de endişeliyim.", # kaygılı, normal
        "Çok sinirliyim, kimseyi gözüm görmüyor." # öfkeli, normal
    ]

    print("\n--- Inference Tests ---")
    for idx, sentence in enumerate(test_sentences, 1):
        prediction = predictor.predict(sentence)
        print(f"\nTest {idx}: {sentence}")
        print(json.dumps(prediction, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    run_tests()
