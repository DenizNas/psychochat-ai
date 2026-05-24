import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__))) # in case we run from scratch
sys.path.append(os.path.abspath(".")) # from root

from src.services.database import get_chat_history, SessionLocal, ChatHistory

try:
    print("Testing get_chat_history...")
    history = get_chat_history("testuser_engine")
    print("Success! History length:", len(history))
except Exception as e:
    print("Error caught during get_chat_history:")
    import traceback
    traceback.print_exc()
