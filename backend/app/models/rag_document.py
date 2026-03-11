from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class RAGDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    topic = Column(String(50), nullable=False, index=True)  # 🆕 ADDED

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    is_public = Column(Boolean, default=False, nullable=False, index=True)

    collection_name = Column(String(100), nullable=False)
    chunks_count = Column(Integer)

    status = Column(String(20), nullable=False, default="processing", index=True)
    error_message = Column(String(500))

    file_size_bytes = Column(Integer)
    pages_count = Column(Integer)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="rag_documents")
