import os
import json
import torch
import warnings
from transformers import BertTokenizer, BertForSequenceClassification

class EmotionCrisisPredictor:
    """Wrapper to run inference using both Emotion and Crisis models."""
    def __init__(self, emotion_model_dir="models/emotion_model", crisis_model_dir="models/crisis_model"):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.emotion_model = None
        self.emotion_tokenizer = None
        self.emotion_labels = {}
        
        self.crisis_model = None
        self.crisis_tokenizer = None
        self.crisis_labels = {}
        
        self._load_emotion_model(emotion_model_dir)
        self._load_crisis_model(crisis_model_dir)
        
    def _load_label_mapping(self, model_dir):
        mapping_path = os.path.join(model_dir, "label_mapping.json")
        if os.path.exists(mapping_path):
             with open(mapping_path, "r", encoding="utf-8") as f:
                  return json.load(f)
        return None

    def _load_emotion_model(self, path):
        if not os.path.exists(path):
             warnings.warn(f"Emotion model not found at {path}. Please train it first.")
             return
             
        self.emotion_tokenizer = BertTokenizer.from_pretrained(path)
        self.emotion_model = BertForSequenceClassification.from_pretrained(path)
        self.emotion_model.to(self.device).eval()
        
        self.emotion_labels = self._load_label_mapping(path) or {str(i): f"C_{i}" for i in range(5)}
        
    def _load_crisis_model(self, path):
         if not os.path.exists(path):
             warnings.warn(f"Crisis model not found at {path}. Please train it first.")
             return
             
         self.crisis_tokenizer = BertTokenizer.from_pretrained(path)
         self.crisis_model = BertForSequenceClassification.from_pretrained(path)
         self.crisis_model.to(self.device).eval()
         
         self.crisis_labels = self._load_label_mapping(path) or {"0": "Normal", "1": "Crisis"}

    def predict_emotion(self, text):
        if not self.emotion_model:
            return {"error": "Model not loaded"}
            
        inputs = self.emotion_tokenizer(text, return_tensors='pt', truncation=True, max_length=128, padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.emotion_model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=1)
            confidence, predicted_idx = torch.max(probs, dim=1)
            
        idx_str = str(predicted_idx.item())
        label_str = self.emotion_labels.get(idx_str, idx_str)
        return {
             "label": label_str,
             "confidence": confidence.item()
        }
        
    def predict_crisis(self, text):
        if not self.crisis_model:
            return {"error": "Model not loaded"}
            
        inputs = self.crisis_tokenizer(text, return_tensors='pt', truncation=True, max_length=128, padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.crisis_model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=1)
            confidence, predicted_idx = torch.max(probs, dim=1)
            
        idx_str = str(predicted_idx.item())
        label_str = self.crisis_labels.get(idx_str, idx_str)
        return {
             "label": label_str,
             "confidence": confidence.item()
        }
        
    def predict_both(self, text):
         """Convenience method to get both analyses at once."""
         return {
             "text": text,
             "emotion": self.predict_emotion(text),
             "crisis_detection": self.predict_crisis(text)
         }

if __name__ == "__main__":
    predictor = EmotionCrisisPredictor()
    
    test_sentences = [
         "Kendimi çok çaresiz hissediyorum, hiçbir şeyin anlamı kalmadı.",
         "Bugün hava çok güzel, kendimi harika hissediyorum!",
         "Çok öfkeliyim, herkes üstüme geliyor.",
         "Sadece ağlamak istiyorum.",
         "Sınav sonuçlarımı bekliyorum, çok heyecanlıyım."
    ]
    
    print("======== Inference Test (Test Cümleleri) ========")
    for sent in test_sentences:
         result = predictor.predict_both(sent)
         print(f"\nText: {result['text']}")
         print(f"  --> Emotion: {result['emotion']}")
         print(f"  --> Crisis : {result['crisis_detection']}")
