import torch
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, classification_report
try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

class ModelTrainer:
    """
    A reusable PyTorch Training loop for Hugging Face transformer models.
    Handles training, validation, metric calculations, and logging.
    """
    def __init__(self, model, optimizer, scheduler, device, num_classes=2, target_names=None):
        self.model = model
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.device = device
        self.num_classes = num_classes
        self.target_names = target_names

    def train_epoch(self, train_loader):
        self.model.train()
        total_loss = 0
        
        # Use simple iteration if tqdm is not installed, otherwise use progress bar
        progress_bar = tqdm(train_loader, desc="Training")
        
        for batch in progress_bar:
            self.optimizer.zero_grad()
            
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            labels = batch['labels'].to(self.device)
            
            outputs = self.model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            
            total_loss += loss.item()
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            self.scheduler.step()
            
            if hasattr(progress_bar, 'set_postfix'):
                progress_bar.set_postfix({'loss': f"{loss.item():.4f}"})
                
        return total_loss / len(train_loader)

    def evaluate(self, dataloader, phase="Validation"):
        self.model.eval()
        total_loss = 0
        all_preds = []
        all_labels = []
        
        progress_bar = tqdm(dataloader, desc=f"{phase}")
        
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
        f1 = f1_score(all_labels, all_preds, average='macro' if self.num_classes > 2 else 'binary')
        
        print(f"\n{phase} Results - Loss: {avg_loss:.4f} | Accuracy: {acc:.4f} | F1-Score: {f1:.4f}")
        print(f"Classification Report ({phase}):")
        
        # Format the classification report with encoded names if provided
        target_names_list = None
        if self.target_names is not None:
             target_names_list = [str(self.target_names[i]) for i in range(len(self.target_names))]

        print(classification_report(all_labels, all_preds, target_names=target_names_list, zero_division=0))
        
        return avg_loss, acc, f1

    def train(self, epochs, train_loader, val_loader):
        """Standard full loops training."""
        for epoch in range(1, epochs + 1):
            print(f"\n======== Epoch {epoch} / {epochs} ========")
            train_loss = self.train_epoch(train_loader)
            print(f"Average Training Loss: {train_loss:.4f}")
            
            self.evaluate(val_loader, phase="Validation")
