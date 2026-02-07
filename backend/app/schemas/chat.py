from pydantic import BaseModel, Field
from typing import List, Dict

from pydantic import BaseModel, Field
from typing import List, Dict


class ChatMessage(BaseModel):
    """Single message in a conversation"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request for chat endpoint"""
    message: str = Field(..., description="User's message", min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Sampling temperature")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Explain inheritance in Java",
                "temperature": 0.7
            }
        }


class ChatResponse(BaseModel):
    """Response from chat endpoint"""
    response: str = Field(..., description="AI's response")
    model: str = Field(..., description="Model used for generation")