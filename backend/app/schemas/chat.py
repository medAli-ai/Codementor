from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single message in a conversation"""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
