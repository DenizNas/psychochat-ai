import pandas as pd
import torch
import argparse
import logging
import os
import json
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Custom Dataset Class
class CrisisDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels.reset_index(drop=True)

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item

    def __len__(self):
        return len(self.labels)

def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="binary")
    acc = accuracy_score(labels, preds)
    return {
        "accuracy": acc,
        "f1": f1,
        "precision": precision,
        "recall": recall
    }

def main():
    # Argparse configuration
    parser = argparse.ArgumentParser(description="Train BERT Crisis Classification Model")
    parser.add_argument("--data_path", type=str, default="/app/data/cleaned_crisis.csv", help="Path to training data CSV")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size for training and eval")
    parser.add_argument("--learning_rate", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--hf_model_dir", type=str, default="/app/models/crisis_model", help="Path to save the HuggingFace model output")
    parser.add_argument("--pt_path", type=str, default="/app/models/crisis_model.pt", help="Path to save the PyTorch .pt model file")
    
    args = parser.parse_args()

    # To support running locally vs inside Docker, we adapt paths dynamically if absolute paths fail
    # E.g., if "/app/data" doesn't exist, try local path "data/"
    if not os.path.exists(args.data_path) and args.data_path.startswith("/app/"):
        local_fallback = args.data_path.replace("/app/", "./")
        if os.path.exists(local_fallback):
            logger.info(f"Container path {args.data_path} not found. Using local path {local_fallback}")
            args.data_path = local_fallback
            args.hf_model_dir = args.hf_model_dir.replace("/app/", "./")
            args.pt_path = args.pt_path.replace("/app/", "./")

    # Create paths if they don't exist
    os.makedirs(os.path.dirname(args.hf_model_dir), exist_ok=True)
    os.makedirs(os.path.dirname(args.pt_path), exist_ok=True)
    
    logger.info(f"Hyperparameters: Epochs={args.epochs}, Batch Size={args.batch_size}, LR={args.learning_rate}")
    
    logger.info(f"Loading data from {args.data_path}")
    if not os.path.exists(args.data_path):
        raise FileNotFoundError(f"Dataset {args.data_path} could not be found.")
        
    df = pd.read_csv(args.data_path)
    
    if "text" not in df.columns or "label" not in df.columns:
         raise ValueError("CSV must contain 'text' and 'label' columns.")

    # TRAIN / TEST SPLIT
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        df["text"],
        df["label"],
        test_size=0.2,
        random_state=42
    )

    MODEL_NAME = "dbmdz/bert-base-turkish-cased"
    logger.info(f"Loading tokenizer: {MODEL_NAME}")
    tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)

    logger.info("Tokenizing datasets...")
    train_encodings = tokenizer(train_texts.tolist(), truncation=True, padding=True)
    test_encodings = tokenizer(test_texts.tolist(), truncation=True, padding=True)

    train_dataset = CrisisDataset(train_encodings, train_labels)
    test_dataset = CrisisDataset(test_encodings, test_labels)

    logger.info(f"Loading pre-trained model: {MODEL_NAME} for binary classification (2 classes).")
    model = BertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    training_args = TrainingArguments(
        output_dir="./results_crisis",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        logging_dir="./logs_crisis",
        eval_strategy="epoch",  # Automatically evaluate every epoch
        save_strategy="epoch",
        logging_steps=10
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        compute_metrics=compute_metrics
    )

    logger.info("Starting training loop...")
    trainer.train()

    logger.info("Running final evaluation...")
    metrics = trainer.evaluate()
    logger.info(f"Final Evaluation Metrics: {metrics}")

    # The predictor in predict.py requires HuggingFace structure
    logger.info(f"Saving HF format model to: {args.hf_model_dir}")
    model.save_pretrained(args.hf_model_dir)
    tokenizer.save_pretrained(args.hf_model_dir)

    # Adding a label_mapping.json as requested by predict.py design
    mapping = {"0": "Normal", "1": "Crisis"}
    with open(os.path.join(args.hf_model_dir, "label_mapping.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f)

    # Save as custom .pt file as explicitly requested
    logger.info(f"Saving PyTorch .pt model state_dict to: {args.pt_path}")
    torch.save(model.state_dict(), args.pt_path)

    logger.info("✅ Crisis Model training completed and saved successfully!")

if __name__ == "__main__":
    main()
