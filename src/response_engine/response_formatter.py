import unicodedata

def format_response(text: str) -> str:
    """
    Cleans and formats the raw GPT response.
    - Removes trailing/leading whitespaces
    - Normalizes unicode characters
    - Ensures UTF-8 safety
    """
    if not text:
        return ""
        
    # Remove extra whitespaces
    text = text.strip()
    
    # Normalize unicode to NFC (canonical composition) to prevent encoding issues
    text = unicodedata.normalize("NFC", text)
    
    # Optional: more aggressive cleanup could go here
    # e.g., replacing multiple newlines with a single newline
    
    return text
