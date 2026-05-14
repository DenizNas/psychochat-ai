import os
import random
import numpy as np
import torch
import transformers
import json
import logging
from datetime import datetime

def set_seed(seed=42):
    """Global random seed fixing for reproducible training."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    transformers.set_seed(seed)

def enable_deterministic_training():
    """Activates deterministic training on CUDA."""
    if torch.cuda.is_available():
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

def get_device(logger=None):
    """Auto-detects device and logs the outcome."""
    if torch.cuda.is_available():
        device = torch.device('cuda')
        device_name = torch.cuda.get_device_name(0)
        msg = f"Device detected: CUDA ({device_name})"
    else:
        device = torch.device('cpu')
        msg = "Device detected: CPU (CUDA not available)"
    
    if logger:
        logger.info(msg)
    else:
        print(msg)
        
    return device

def setup_logger(name, log_dir="training/logs"):
    """Creates a UTF-8 safe logger writing to both console and file."""
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{name}_{timestamp}.log")
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # File Handler (UTF-8)
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.INFO)
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
    return logger

def load_config(config_path):
    """Loads a JSON configuration file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
