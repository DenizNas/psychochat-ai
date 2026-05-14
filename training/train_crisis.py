import os
import argparse
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau

from src.data.dataset import load_and_split_data, TextClassificationDataset
from src.models.model_builder import get_model_and_tokenizer
from training.utils.trainer import ModelTrainer
from training.common import set_seed, enable_deterministic_training, get_device, setup_logger, load_config

def main():
    parser = argparse.ArgumentParser(description="Production Crisis Training Pipeline")
    parser.add_argument("--config", type=str, default="training/configs/crisis_config.json", help="Path to config file")
    args = parser.parse_args()

    logger = setup_logger("train_crisis", "training/logs")
    logger.info("Starting Crisis Training Pipeline...")
    
    try:
        config = load_config(args.config)
        logger.info(f"Loaded config from {args.config}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    set_seed(config.get("seed", 42))
    enable_deterministic_training()
    device = get_device(logger)

    try:
        logger.info("Loading dataset and creating splits...")
        (train_texts, train_labels), (val_texts, val_labels), (test_texts, test_labels), label_encoder = load_and_split_data(
            config["data_path"], text_col="text", label_col="label"
        )
        
        num_classes = len(label_encoder.classes_)
        logger.info(f"Found {num_classes} classes: {list(label_encoder.classes_)}")
        logger.info(f"Train size: {len(train_texts)} | Val size: {len(val_texts)} | Test size: {len(test_texts)}")

        logger.info(f"Initializing Model ({config['model_name']}) and Tokenizer...")
        model, tokenizer = get_model_and_tokenizer(model_name=config["model_name"], num_labels=num_classes)
        model.to(device)

        train_dataset = TextClassificationDataset(train_texts, train_labels, tokenizer, max_length=config.get("max_length", 128))
        val_dataset = TextClassificationDataset(val_texts, val_labels, tokenizer, max_length=config.get("max_length", 128))
        test_dataset = TextClassificationDataset(test_texts, test_labels, tokenizer, max_length=config.get("max_length", 128))

        train_loader = DataLoader(train_dataset, batch_size=config["batch_size"], shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=config["batch_size"])
        test_loader = DataLoader(test_dataset, batch_size=config["batch_size"])

        optimizer = AdamW(model.parameters(), lr=config["learning_rate"])
        
        scheduler = ReduceLROnPlateau(
            optimizer, 
            mode='min', 
            factor=config.get("scheduler_factor", 0.5), 
            patience=config.get("scheduler_patience", 2),
            verbose=True
        )

        trainer = ModelTrainer(
            model=model, 
            optimizer=optimizer, 
            scheduler=scheduler, 
            device=device,
            num_classes=num_classes,
            target_names=label_encoder.classes_,
            logger=logger,
            task_name="crisis",
            early_stopping_patience=config.get("early_stopping_patience", 3),
            early_stopping_min_delta=config.get("early_stopping_min_delta", 0.001),
            save_dir=config["save_dir"]
        )

        logger.info("Starting Training Loop...")
        trainer.train(epochs=config["epochs"], train_loader=train_loader, val_loader=val_loader, tokenizer=tokenizer)

        logger.info("Starting Final Test Evaluation...")
        trainer.evaluate(test_loader, phase="Test")

        logger.info("Training Pipeline Finished Successfully!")

    except Exception as e:
        logger.exception(f"FATAL ERROR during training pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
