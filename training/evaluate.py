import os
import argparse
import json
import torch
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix
from transformers import BertTokenizer, BertForSequenceClassification
from torch.utils.data import DataLoader

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.common import setup_logger, get_device
from src.data.dataset import TextClassificationDataset

def evaluate_model(model_dir, test_csv, task_name, logger, device):
    logger.info("="*50)
    logger.info(f"Evaluating {task_name.upper()} Model")
    logger.info("="*50)
    
    if not os.path.exists(model_dir):
        logger.error(f"Model directory not found: {model_dir}")
        return
        
    if not os.path.exists(test_csv):
        logger.error(f"Test CSV not found: {test_csv}")
        return

    logger.info(f"Loading model and tokenizer from {model_dir}...")
    try:
        tokenizer = BertTokenizer.from_pretrained(model_dir)
        model = BertForSequenceClassification.from_pretrained(model_dir)
        model.to(device)
        model.eval()
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    logger.info(f"Loading test data from {test_csv}...")
    df = pd.read_csv(test_csv, encoding="utf-8")
    
    label_col = task_name.lower()
    if label_col not in df.columns:
        logger.error(f"Column '{label_col}' not found in {test_csv}")
        return
        
    texts = df["text"].tolist()
    labels_str = df[label_col].astype(str).tolist()

    # Create mapping from labels seen in test set
    unique_labels = sorted(list(set(labels_str)))
    label2id = {label: i for i, label in enumerate(unique_labels)}
    id2label = {i: label for label, i in label2id.items()}
    
    labels_int = [label2id[l] for l in labels_str]
    
    dataset = TextClassificationDataset(texts, labels_int, tokenizer, max_length=128)
    loader = DataLoader(dataset, batch_size=32, shuffle=False)
    
    all_preds = []
    all_labels = []
    
    logger.info("Running inference on test set...")
    with torch.no_grad():
        for batch in loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            targets = batch['labels'].numpy()
            
            outputs = model(input_ids, attention_mask=attention_mask)
            preds = torch.argmax(outputs.logits, dim=1).cpu().numpy()
            
            all_preds.extend(preds)
            all_labels.extend(targets)

    # Compute metrics
    acc = accuracy_score(all_labels, all_preds)
    prec = precision_score(all_labels, all_preds, average="macro", zero_division=0)
    rec = recall_score(all_labels, all_preds, average="macro", zero_division=0)
    f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    
    logger.info(f"{task_name.upper()} Overall Metrics -> Accuracy: {acc:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f} | F1 (Macro): {f1:.4f}")
    
    # Class Imbalance Check
    class_counts = df[label_col].value_counts()
    min_class_ratio = class_counts.min() / len(df)
    if min_class_ratio < 0.1:
        logger.warning(f"Class Imbalance Detected in {task_name.upper()} test set! Smallest class ratio is {min_class_ratio:.2%}.")
        
    # Crisis specific recall warning
    if task_name.lower() == "crisis":
        crisis_target_idx = None
        for lbl, idx in label2id.items():
            if str(lbl) in ["1", "Crisis", "crisis", "True"]:
                crisis_target_idx = idx
                break
        
        if crisis_target_idx is not None:
            rec_crisis = recall_score(all_labels, all_preds, labels=[crisis_target_idx], average=None, zero_division=0)[0]
            logger.info(f"CRISIS METRIC HIGHLIGHT: Class '{id2label[crisis_target_idx]}' Recall: {rec_crisis:.4f}")
            if rec_crisis < 0.85:
                logger.warning(f"CRITICAL RISK: Crisis recall is {rec_crisis:.4f} (Target > 0.85). The model is missing actual crisis cases. Adjust class weights or threshold!")
        else:
            logger.warning("Could not identify the positive 'Crisis' class (e.g. '1' or 'Crisis') to check specific recall.")

    # Classification Report
    report_dict = classification_report(all_labels, all_preds, target_names=[str(l) for l in unique_labels], output_dict=True, zero_division=0)
    report_str = classification_report(all_labels, all_preds, target_names=[str(l) for l in unique_labels], zero_division=0)
    
    logger.info(f"Classification Report:\n{report_str}")
    
    # Save JSON
    log_dir = "training/logs"
    os.makedirs(log_dir, exist_ok=True)
    json_path = os.path.join(log_dir, f"evaluation_{task_name.lower()}.json")
    
    results = {
        "task": task_name,
        "metrics": {
            "accuracy": acc,
            "macro_precision": prec,
            "macro_recall": rec,
            "macro_f1": f1
        },
        "classification_report": report_dict
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    logger.info(f"Results saved to {json_path}")
    
    # Confusion Matrix Plot
    cm = confusion_matrix(all_labels, all_preds)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=[str(l) for l in unique_labels], yticklabels=[str(l) for l in unique_labels])
    plt.title(f"{task_name.upper()} Confusion Matrix")
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    
    png_path = os.path.join(log_dir, f"confusion_matrix_{task_name.lower()}.png")
    plt.savefig(png_path, dpi=300)
    plt.close()
    logger.info(f"Confusion matrix saved to {png_path}\n")

def main():
    parser = argparse.ArgumentParser(description="Model Evaluation Script")
    parser.add_argument("--emotion-test", required=True, help="Path to emotion test split")
    parser.add_argument("--crisis-test", required=True, help="Path to crisis test split")
    parser.add_argument("--emotion-model", required=True, help="Path to emotion model checkpoint")
    parser.add_argument("--crisis-model", required=True, help="Path to crisis model checkpoint")
    args = parser.parse_args()

    logger = setup_logger("evaluate", "training/logs")
    device = get_device(logger)
    
    evaluate_model(args.emotion_model, args.emotion_test, "emotion", logger, device)
    evaluate_model(args.crisis_model, args.crisis_test, "crisis", logger, device)
    
    logger.info("Evaluation Pipeline Finished!")
    
if __name__ == "__main__":
    main()
