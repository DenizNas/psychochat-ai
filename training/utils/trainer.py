import torch
import numpy as np
import time
import os
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

class EarlyStopping:
    def __init__(self, patience=3, min_delta=0.001):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.early_stop = False

    def __call__(self, val_loss):
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss > self.best_loss - self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_loss = val_loss
            self.counter = 0

class ModelTrainer:
    """
    A reusable PyTorch Training loop for Hugging Face transformer models.
    Handles training, validation, metric calculations, logging, and early stopping.
    """
    def __init__(self, model, optimizer, scheduler, device, num_classes=2, target_names=None, logger=None, 
                 task_name="emotion", early_stopping_patience=3, early_stopping_min_delta=0.001, save_dir="training/checkpoints/best"):
        self.model = model
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.device = device
        self.num_classes = num_classes
        self.target_names = target_names
        self.logger = logger
        self.task_name = task_name.lower()
        self.save_dir = save_dir
        
        self.early_stopping = EarlyStopping(patience=early_stopping_patience, min_delta=early_stopping_min_delta)
        
        self.label2id = {}
        if target_names is not None:
             self.label2id = {str(name): i for i, name in enumerate(target_names)}

    def _log(self, msg, level="info"):
        if self.logger:
            if level == "info": self.logger.info(msg)
            elif level == "warning": self.logger.warning(msg)
            elif level == "error": self.logger.error(msg)
        else:
            print(msg)

    def train_epoch(self, train_loader):
        self.model.train()
        total_loss = 0
        
        progress_bar = tqdm(train_loader, desc="Training", leave=False)
        
        for batch in progress_bar:
            self.optimizer.zero_grad()
            
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            labels = batch['labels'].to(self.device)
            
            outputs = self.model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            
            total_loss += loss.item()
            loss.backward()
            
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            
            if hasattr(progress_bar, 'set_postfix'):
                progress_bar.set_postfix({'loss': f"{loss.item():.4f}"})
                
        return total_loss / len(train_loader)

    def evaluate(self, dataloader, phase="Validation"):
        self.model.eval()
        total_loss = 0
        all_preds = []
        all_labels = []
        
        progress_bar = tqdm(dataloader, desc=f"{phase}", leave=False)
        
        with torch.no_grad():
            for batch in progress_bar:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)
                
                outputs = self.model(input_ids, attention_mask=attention_mask, labels=labels)
                loss = outputs.loss
                total_loss += loss.item()
                
                logits = outputs.logits
                preds = torch.argmax(logits, dim=1).cpu().numpy()
                
                all_preds.extend(preds)
                all_labels.extend(labels.cpu().numpy())
                
                if hasattr(progress_bar, 'set_postfix'):
                    progress_bar.set_postfix({'loss': f"{loss.item():.4f}"})
                    
        avg_loss = total_loss / len(dataloader)
        acc = accuracy_score(all_labels, all_preds)
        prec = precision_score(all_labels, all_preds, average='macro', zero_division=0)
        rec = recall_score(all_labels, all_preds, average='macro', zero_division=0)
        f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0)
        
        self._log(f"[{phase}] Loss: {avg_loss:.4f} | Accuracy: {acc:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f} | F1: {f1:.4f}")
        
        if self.task_name == "crisis" and phase == "Validation":
            crisis_target_idx = None
            for lbl, idx in self.label2id.items():
                if lbl in ["1", "Crisis", "crisis", "True"]:
                    crisis_target_idx = idx
                    break
            if crisis_target_idx is not None:
                rec_crisis = recall_score(all_labels, all_preds, labels=[crisis_target_idx], average=None, zero_division=0)[0]
                if rec_crisis < 0.85:
                    self._log(f"CRITICAL CRISIS RECALL WARNING: Class '{list(self.label2id.keys())[crisis_target_idx]}' recall is {rec_crisis:.4f} (< 0.85)", level="warning")
        
        return avg_loss, acc, prec, rec, f1

    def train(self, epochs, train_loader, val_loader, tokenizer):
        """Standard full loops training with exception handling, early stopping, and best model saving."""
        best_val_loss = float('inf')
        prev_train_loss = float('inf')
        
        try:
            for epoch in range(1, epochs + 1):
                self._log(f"======== Epoch {epoch} / {epochs} ========")
                start_time = time.time()
                
                train_loss = self.train_epoch(train_loader)
                val_loss, val_acc, val_prec, val_rec, val_f1 = self.evaluate(val_loader, phase="Validation")
                
                epoch_time = time.time() - start_time
                current_lr = self.optimizer.param_groups[0]['lr']
                
                self._log(f"Epoch {epoch} Summary | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Time: {epoch_time:.2f}s | LR: {current_lr}")
                
                if train_loss < prev_train_loss and val_loss > best_val_loss:
                    self._log(f"OVERFITTING WARNING: Train loss decreased ({train_loss:.4f}) but Validation loss increased ({val_loss:.4f})!", level="warning")
                
                prev_train_loss = train_loss
                
                if isinstance(self.scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                    self.scheduler.step(val_loss)
                else:
                    self.scheduler.step()
                
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    self._log(f"New best validation loss: {best_val_loss:.4f}. Saving best model checkpoint...")
                    
                    best_model_dir = os.path.join(self.save_dir, "best_model")
                    os.makedirs(best_model_dir, exist_ok=True)
                    self.model.save_pretrained(best_model_dir)
                    tokenizer.save_pretrained(best_model_dir)
                    import json
                    mapping = {str(i): cls for cls, i in self.label2id.items()}
                    with open(os.path.join(best_model_dir, "label_mapping.json"), "w", encoding="utf-8") as f:
                        json.dump(mapping, f, ensure_ascii=False)
                
                self.early_stopping(val_loss)
                if self.early_stopping.early_stop:
                    self._log(f"Early stopping triggered after {epoch} epochs due to no improvement in validation loss.", level="warning")
                    break
                    
        except Exception as e:
            if self.logger:
                self.logger.exception(f"Training interrupted due to error: {e}")
            else:
                import traceback
                traceback.print_exc()
            raise e
