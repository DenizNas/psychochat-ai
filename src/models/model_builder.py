from transformers import BertTokenizer, BertForSequenceClassification

def get_model_and_tokenizer(model_name="dbmdz/bert-base-turkish-cased", num_labels=2):
    """
    Initializes and returns a tokenizer and an empty BERT model configured 
    for sequence classification.
    
    Args:
        model_name (str): Hugging Face model identifier
        num_labels (int): Number of output classes (e.g. 5 for Emotion, 2 for Crisis)
        
    Returns:
        tuple: (model, tokenizer)
    """
    tokenizer = BertTokenizer.from_pretrained(model_name)
    model = BertForSequenceClassification.from_pretrained(
        model_name, 
        num_labels=num_labels
    )
    return model, tokenizer
