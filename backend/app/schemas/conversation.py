from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict

# ============ Message Schemas ============

class MessageBase(BaseModel):
    """Base message schema"""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., min_length=1)

class MessageCreate(MessageBase):
    """Schema for creating a message"""
    pass

class MessageResponse(MessageBase):
    """Schema for message in responses"""
    id: int
    conversation_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============ Conversation Schemas ============

class ConversationBase(BaseModel):
    """Base conversation schema"""
    title: str = Field(default="New Conversation", max_length=200)

class ConversationCreate(ConversationBase):
    """Schema for creating a conversation"""
    pass

class ConversationUpdate(BaseModel):
    """Schema for updating a conversation"""
    title: Optional[str] = Field(None, max_length=200)

class ConversationResponse(ConversationBase):
    """Schema for conversation in responses"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ConversationWithMessages(ConversationResponse):
    """Conversation with all its messages"""
    messages: List[MessageResponse] = []
    
    class Config:
        from_attributes = True

# ============ Chat Schemas (Updated with RAG) ============

class ChatRequest(BaseModel):
    """Request for chat endpoint"""
    conversation_id: Optional[int] = Field(None, description="Existing conversation ID, or None for new")
    message: str = Field(..., min_length=1, max_length=10000)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    use_rag: bool = Field(default=True, description="Whether to use RAG context from uploaded documents")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": 1,
                "message": "Explain inheritance in Python",
                "temperature": 0.7,
                "use_rag": True
            }
        }

class RAGSource(BaseModel):
    """Source document used for RAG context"""
    title: str
    document_id: int
    score: float
    page_numbers: list[int] = []
    chunk_type: str = "prose"  # e.g. 'prose', 'code', 'table'

class ChatResponse(BaseModel):
    """Response from chat endpoint"""
    conversation_id: int
    message_id: int
    response: str
    model: str
    sources: Optional[List[RAGSource]] = None  # 🆕 NEW: RAG sources used
    rag_used: bool = False  # 🆕 NEW: Whether RAG context was used
