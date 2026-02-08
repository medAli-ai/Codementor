from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user in responses (no password!)"""
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True  # Allows SQLAlchemy model conversion


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token"""
    email: Optional[str] = None