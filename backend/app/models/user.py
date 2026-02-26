from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    """
    User roles for RBAC (Role-Based Access Control).
    
    USER: Regular users (can upload own PDFs, use chat)
    ADMIN: Admins (can add public books, see all data)
    SUPERADMIN: Super admins (can create admins, full control)
    """
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    role = Column(
        SQLEnum(
            UserRole,
            name='userrole',  # Match the PostgreSQL enum type name
            values_callable=lambda x: [e.value for e in x],  # Use lowercase values
            create_constraint=False  # Enum already created by migration
        ),
        default=UserRole.USER,
        nullable=False,
        server_default='user'
    )
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    rag_documents = relationship("RAGDocument", back_populates="user", cascade="all, delete-orphan")
    refresh_token = Column(String, nullable=True)