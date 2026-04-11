import os
import argparse
import torch
from torch.utils.data import DataLoader
from transformers import AdamW, get_linear_schedule_with_warmup

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.dataset import load_and_split_data, TextClassificationDataset
from src.models.model_builder import get_model_and_tokenizer
from src.training.trainer import ModelTrainer

def main():
    parser = argparse.ArgumentParser(description="Train Emotion Classification Model")
    parser.add_argument("--data", type=str, default="data/processed/emotion_dataset_final.csv", help="Path to csv")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--model_name", type=str, default="dbmdz/bert-base-turkish-cased", help="HF Base Model")
    parser.add_argument("--save_dir", type=str, default="models/emotion_model", help="Path to save the trained model")
    
    args = parser.parse_args()

    # Device configuration
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # 1. Load data
    print("Loading data and creating splits...")
    (train_texts, train_labels), (val_texts, val_labels), (test_texts, test_labels), label_encoder = load_and_split_data(
        args.data, text_col="text", label_col="label"
    )
    
    num_classes = len(label_encoder.classes_)
    print(f"Found {num_classes} classes: {list(label_encoder.classes_)}")
    print(f"Train size: {len(train_texts)} | Val size: {len(val_texts)} | Test size: {len(test_texts)}")

    # 2. Get Model & Tokenizer
    print("Initializing Model and Tokenizer...")
    model, tokenizer = get_model_and_tokenizer(model_name=args.model_name, num_labels=num_classes)
    model.to(device)

    # 3. Create Datasets and Dataloaders
    train_dataset = TextClassificationDataset(train_texts, train_labels, tokenizer)
    val_dataset = TextClassificationDataset(val_texts, val_labels, tokenizer)
    test_dataset = TextClassificationDataset(test_texts, test_labels, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size)

    # 4. Optimizer & Scheduler
    optimizer = AdamW(model.parameters(), lr=args.lr, correct_bias=False)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=0, num_training_steps=total_steps
    )

    # 5. Initialize Trainer
    trainer = ModelTrainer(
        model=model, 
        optimizer=optimizer, 
        scheduler=scheduler, 
        device=device,
        num_classes=num_classes,
        target_names=label_encoder.classes_
    )

    # 6. Train model
    print("Starting Training Loop...")
    trainer.train(epochs=args.epochs, train_loader=train_loader, val_loader=val_loader)

    # 7. Final Test Evaluation
    print("\nStarting Final Test Evaluation...")
    trainer.evaluate(test_loader, phase="Test")

    # 8. Save Model
    print(f"Saving model to {args.save_dir}")
    os.makedirs(args.save_dir, exist_ok=True)
    model.save_pretrained(args.save_dir)
    tokenizer.save_pretrained(args.save_dir)
    
    # Save the label encoder mapping locally inside the model dir
    import json
    with open(os.path.join(args.save_dir, "label_mapping.json"), "w", encoding="utf-8") as f:
         mapping = {str(i): cls for i, cls in enumerate(label_encoder.classes_)}
         json.dump(mapping, f, ensure_ascii=False)
    
    print("Training Pipeline Finished Successfully!")

if __name__ == "__main__":
    main()
