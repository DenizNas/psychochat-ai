from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class EngineConfig(BaseModel):
    """Configuration for the Response Engine"""
    timeout_seconds: int = Field(default=10, description="Timeout for GPT API calls")
    max_memory_length: int = Field(default=12, description="Max raw history messages to fetch from DB")
    max_context_chars: int = Field(default=4000, description="Total char budget for conversation history")
    max_single_msg_chars: int = Field(default=800, description="Per-message char truncation limit")
    primary_model: str = Field(default="gpt-4o", description="Primary GPT model")
    fallback_model: str = Field(default="gpt-3.5-turbo", description="Fallback GPT model")
    temperature: float = Field(default=0.7, description="Generation temperature")
    max_tokens: int = Field(default=250, description="Maximum tokens for generation")
    max_retries: int = Field(default=1, description="Max quality-based retries (non-crisis only; keeps GPT cost bounded)")

class EngineInput(BaseModel):
    """Input payload for the Response Engine"""
    text: str = Field(..., description="User input text")
    emotion: str = Field(..., description="Detected emotion label")
    risk: str = Field(..., description="Detected crisis risk label")
    user_id: str = Field(default="default", description="User identifier")
    language: str = Field(default="tr", description="Language for response")

class EngineOutput(BaseModel):
    """Output payload from the Response Engine"""
    final_text: str = Field(..., description="The generated and formatted response")
    is_fallback: bool = Field(default=False, description="Whether fallback mechanism was used")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata")
