"""
RAG Schemas (Request/Response Models)

Pydantic models for RAG API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class TopicEnum(str, Enum):
    """Supported programming topics."""

    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    CPP = "cpp"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SQL = "sql"
    WEB = "web"
    DATA_SCIENCE = "data-science"
    MACHINE_LEARNING = "machine-learning"
    ALGORITHMS = "algorithms"
    SYSTEM_DESIGN = "system-design"


class DocumentStatus(str, Enum):
    """Document processing status."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadResponse(BaseModel):
    """Response after uploading a document."""

    document_id: int
    title: str
    filename: str
    topic: str
    status: str
    message: str = "Document uploaded successfully. Processing in background."

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Single document details."""

    id: int
    title: str
    filename: str
    topic: str
    user_id: Optional[int]
    is_public: bool
    status: str
    error_message: Optional[str]
    chunks_count: Optional[int]
    file_size_bytes: Optional[int]
    pages_count: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """List of documents with pagination."""

    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentUploadRequest(BaseModel):
    """Request for document upload (form data)."""

    title: Optional[str] = Field(
        None, description="Document title (auto-generated if not provided)"
    )
    topic: TopicEnum = Field(..., description="Programming topic")
    is_public: bool = Field(False, description="Make document publicly accessible")

    @validator("title")
    def validate_title(cls, v):
        if v and len(v) > 200:
            raise ValueError("Title must be less than 200 characters")
        return v


class SearchResultItem(BaseModel):
    """A single chunk result from document search."""

    chunk_text: str
    score: float
    document_id: int
    title: str
    chunk_type: str = "prose"  # 'prose' | 'code' | 'table'
    page_numbers: List[int] = []
    chunk_index: int = 0


class SearchResponse(BaseModel):
    """Response from the document search endpoint."""

    query: str
    results: List[SearchResultItem]
    total: int


class ChunkPreviewItem(BaseModel):
    """A single chunk in the preview panel (target or neighbor)."""

    chunk_text: str
    chunk_index: int
    chunk_type: str = "prose"
    page_numbers: List[int] = []
    is_target: bool = False


class ChunkPreviewResponse(BaseModel):
    """Response from the chunk preview endpoint."""

    document_id: int
    title: str
    chunks: List[ChunkPreviewItem]
