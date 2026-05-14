import os
from pathlib import Path

# Absolute path resolution for the project root
# paths.py is located at: <root>/src/core/paths.py
# Using parent.parent.parent navigates back to <root>
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Centralized model paths
MODELS_DIR = PROJECT_ROOT / "models"
EMOTION_MODEL_DIR = MODELS_DIR / "emotion_model"
CRISIS_MODEL_DIR = MODELS_DIR / "crisis_model"

# String conversions for compatibility with libraries expecting strings
PROJECT_ROOT_STR = str(PROJECT_ROOT)
MODELS_DIR_STR = str(MODELS_DIR)
EMOTION_MODEL_DIR_STR = str(EMOTION_MODEL_DIR)
CRISIS_MODEL_DIR_STR = str(CRISIS_MODEL_DIR)
