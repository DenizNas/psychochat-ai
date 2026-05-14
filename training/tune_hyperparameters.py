import os
import argparse
import sys
import json
import itertools
import pandas as pd
from uuid import uuid4
import traceback
import torch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.metrics import classification_report

from src.data.dataset import load_and_split_data, TextClassificationDataset
from src.models.model_builder import get_model_and_tokenizer
from training.utils.trainer import ModelTrainer
from training.common import set_seed, enable_deterministic_training, get_device, setup_logger, load_config

# 1. Grid Search Parameters
PARAM_GRID = {
    "learning_rate": [1e-5, 2e-5, 3e-5],
    "batch_size": [8, 16],
    "epochs": [3, 5],
    "max_length": [96, 128],
    "weight_decay": [0.0, 0.01],
    "warmup_ratio": [0.0, 0.1],
    "early_stopping_patience": [2, 3]
}

def generate_experiments(max_runs):
    keys, values = zip(*PARAM_GRID.items())
    experiments = [dict(zip(keys, v)) for v in itertools.product(*values)]
    if max_runs and max_runs < len(experiments):
        import random
        random.shuffle(experiments)
        experiments = experiments[:max_runs]
    return experiments

def run_experiment(exp_config, base_config, model_type, exp_id, logger, device):
    set_seed(base_config.get("seed", 42))
    enable_deterministic_training()
    
    config = base_config.copy()
    config.update(exp_config)
    
    (train_texts, train_labels), (val_texts, val_labels), (test_texts, test_labels), label_encoder = load_and_split_data(
        config["data_path"], text_col="text", label_col="label"
    )
    
    num_classes = len(label_encoder.classes_)
    model, tokenizer = get_model_and_tokenizer(model_name=config["model_name"], num_labels=num_classes)
    model.to(device)

    train_dataset = TextClassificationDataset(train_texts, train_labels, tokenizer, max_length=config["max_length"])
    val_dataset = TextClassificationDataset(val_texts, val_labels, tokenizer, max_length=config["max_length"])

    train_loader = DataLoader(train_dataset, batch_size=config["batch_size"], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=config["batch_size"])

    optimizer = AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    
    scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2, verbose=False)

    trainer = ModelTrainer(
        model=model, 
        optimizer=optimizer, 
        scheduler=scheduler, 
        device=device,
        num_classes=num_classes,
        target_names=label_encoder.classes_,
        logger=logger,
        task_name=model_type,
        early_stopping_patience=config["early_stopping_patience"],
        early_stopping_min_delta=0.001,
        save_dir=f"training/checkpoints/tuning_{model_type}/{exp_id}"
    )

    trainer.train(epochs=config["epochs"], train_loader=train_loader, val_loader=val_loader, tokenizer=tokenizer)

    # Evaluate on validation set
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in val_loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)
            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            preds = torch.argmax(outputs.logits, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())
            
    report_dict = classification_report(all_labels, all_preds, target_names=[str(c) for c in label_encoder.classes_], output_dict=True, zero_division=0)
    
    macro_f1 = report_dict['macro avg']['f1-score']
    crisis_recall = 0.0
    crisis_f1 = 0.0
    
    if model_type == "crisis":
        for lbl in label_encoder.classes_:
            if str(lbl) in ["1", "Crisis", "crisis", "True"]:
                crisis_recall = report_dict[str(lbl)]['recall']
                crisis_f1 = report_dict[str(lbl)]['f1-score']
                break
                
    result = {
        "macro_f1": macro_f1,
        "crisis_recall": crisis_recall,
        "crisis_f1": crisis_f1,
        "status": "success"
    }
    return result

def main():
    parser = argparse.ArgumentParser(description="Hyperparameter Tuning System")
    parser.add_argument("--model-type", type=str, required=True, choices=["emotion", "crisis"])
    parser.add_argument("--base-config", type=str, required=True)
    parser.add_argument("--max-runs", type=int, default=10)
    args = parser.parse_args()

    log_dir = f"training/logs/tuning/{args.model_type}"
    os.makedirs(log_dir, exist_ok=True)
    
    logger = setup_logger(f"tune_{args.model_type}", log_dir)
    device = get_device(logger)
    
    try:
        base_config = load_config(args.base_config)
    except Exception as e:
        logger.error(f"Failed to load base config: {e}")
        sys.exit(1)

    experiments = generate_experiments(args.max_runs)
    logger.info(f"Generated {len(experiments)} experiments for {args.model_type}.")
    
    results_summary = []
    
    for i, exp_config in enumerate(experiments):
        exp_id = f"exp_{uuid4().hex[:6]}_lr{exp_config['learning_rate']}_bs{exp_config['batch_size']}"
        logger.info(f"\n[{i+1}/{len(experiments)}] Starting Experiment {exp_id}")
        logger.info(f"Config: {exp_config}")
        
        config_path = os.path.join(log_dir, f"{exp_id}_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(exp_config, f, indent=4)
            
        try:
            result = run_experiment(exp_config, base_config, args.model_type, exp_id, logger, device)
        except Exception as e:
            logger.error(f"Experiment {exp_id} FAILED: {e}")
            result = {"macro_f1": 0.0, "crisis_recall": 0.0, "crisis_f1": 0.0, "status": "failed", "error": str(e)}
            
        result_path = os.path.join(log_dir, f"{exp_id}_result.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)
            
        summary_row = {"experiment_id": exp_id}
        summary_row.update(exp_config)
        summary_row.update(result)
        results_summary.append(summary_row)
        
    df_summary = pd.DataFrame(results_summary)
    summary_path = os.path.join(log_dir, "summary.csv")
    df_summary.to_csv(summary_path, index=False, encoding="utf-8")
    logger.info(f"\nAll experiments finished. Summary saved to {summary_path}")
    
    # Find best config
    df_success = df_summary[df_summary["status"] == "success"]
    if not df_success.empty:
        if args.model_type == "crisis":
            # Crisis için Recall odaklı seçim (Eğer eşitse F1'e bak)
            df_success = df_success.sort_values(by=["crisis_recall", "crisis_f1", "macro_f1"], ascending=False)
        else:
            # Emotion için Macro F1 odaklı seçim
            df_success = df_success.sort_values(by="macro_f1", ascending=False)
            
        best_exp = df_success.iloc[0]
        best_exp_id = best_exp["experiment_id"]
        logger.info(f"=== BEST EXPERIMENT: {best_exp_id} ===")
        if args.model_type == "crisis":
            logger.info(f"Best Crisis Recall: {best_exp['crisis_recall']:.4f} (F1: {best_exp['crisis_f1']:.4f})")
        else:
            logger.info(f"Best Macro F1: {best_exp['macro_f1']:.4f}")
            
        # En iyi config'i kaydet
        best_config_path = f"training/configs/best_{args.model_type}_config.json"
        best_config = base_config.copy()
        for k in PARAM_GRID.keys():
            best_config[k] = best_exp[k]
            
        with open(best_config_path, "w", encoding="utf-8") as f:
            json.dump(best_config, f, indent=4)
        logger.info(f"Best config saved to {best_config_path}")
    else:
        logger.warning("All experiments failed. No best config generated.")

if __name__ == "__main__":
    main()
