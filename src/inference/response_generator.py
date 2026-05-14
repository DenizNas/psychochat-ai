import warnings
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput

def generate_response(text: str, emotion: str, risk: str, user_id: str = "default", language: str = "tr") -> str:
    """
    DEPRECATED: Use src.response_engine.engine.ResponseEngine instead.
    This wrapper is kept for backward compatibility.
    """
    warnings.warn(
        "src.inference.response_generator.generate_response is deprecated. "
        "Use src.response_engine.engine.ResponseEngine instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    engine_input = EngineInput(
        text=text,
        emotion=emotion,
        risk=risk,
        user_id=user_id,
        language=language
    )
    
    output = response_engine.generate_response(engine_input)
    return output.final_text
