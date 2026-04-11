import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

class PsychoChatInference:
    def __init__(self, emotion_model_path="models/emotion_model", crisis_model_path="models/crisis_model"):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        try:
            print("Yükleniyor: Emotion Model...")
            self.emotion_tokenizer = AutoTokenizer.from_pretrained(emotion_model_path)
            self.emotion_model = AutoModelForSequenceClassification.from_pretrained(emotion_model_path)
            self.emotion_model.to(self.device)
            self.emotion_model.eval()
            self.emotion_loaded = True
        except Exception as e:
            print(f"Emotion modeli yüklenemedi. (Lütfen önce train_emotion.py'yi çalıştırın). Hata: {e}")
            self.emotion_loaded = False
            
        try:
            print("Yükleniyor: Crisis Model...")
            self.crisis_tokenizer = AutoTokenizer.from_pretrained(crisis_model_path)
            self.crisis_model = AutoModelForSequenceClassification.from_pretrained(crisis_model_path)
            self.crisis_model.to(self.device)
            self.crisis_model.eval()
            self.crisis_loaded = True
        except Exception as e:
            print(f"Crisis modeli yüklenemedi. (Lütfen önce train_crisis.py'yi çalıştırın). Hata: {e}")
            self.crisis_loaded = False
            
        # 0: mutlu, 1: üzgün, 2: kaygılı, 3: öfkeli, 4: nötr
        self.emotion_labels = {0: "Mutlu", 1: "Üzgün", 2: "Kaygılı", 3: "Öfkeli", 4: "Nötr"}
            
    def predict(self, text):
        result = {"text": text, "emotion": None, "crisis": None}
        
        # 1. Predict Emotion
        if self.emotion_loaded:
            inputs = self.emotion_tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128).to(self.device)
            with torch.no_grad():
                logits = self.emotion_model(**inputs).logits
                predicted_class = torch.argmax(logits, dim=1).item()
            result["emotion"] = self.emotion_labels.get(predicted_class, f"Bilinmeyen ({predicted_class})")
            
        # 2. Predict Crisis
        if self.crisis_loaded:
            inputs = self.crisis_tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128).to(self.device)
            with torch.no_grad():
                logits = self.crisis_model(**inputs).logits
                predicted_class = torch.argmax(logits, dim=1).item()
            result["crisis"] = "🔴 Yüksek Risk (Kriz)" if predicted_class == 1 else "🟢 Normal Risk"
            
        return result

def run_tests():
    texts = [
        "I just got a promotion at work! I am so thrilled.",
        "I feel completely hopeless and tired of this pain, I just want it to end.",
        "I am a little bit scared about the exam tomorrow, it makes me nervous.",
        "She didn't text me back, I am absolutely furious!",
        "Life goes on like normal, reading a nice book today."
    ]
    
    predictor = PsychoChatInference()
    
    if not predictor.emotion_loaded and not predictor.crisis_loaded:
        print("\nModeller henüz eğitilmediği için testler atlanıyor. Lütfen önce `src/training` altındaki betikleri çalıştırın.")
        return
        
    print("\n========= TEST SONUÇLARI =========")
    for text in texts:
        print(f"\nMesaj: '{text}'")
        pred = predictor.predict(text)
        print(f"Tespit Edilen Duygu: {pred['emotion']}")
        print(f"Risk Durumu: {pred['crisis']}")
        print("-" * 30)

if __name__ == "__main__":
    run_tests()
