"""
RAG API Routes

Endpoints for document upload and management.
"""
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.rag_document import RAGDocument
from app.services.rag.retriever import get_retriever
from app.schemas.rag import (
    UploadResponse,
    DocumentResponse,
    DocumentListResponse,
    TopicEnum,
    DocumentStatus,
    SearchResultItem,   
    SearchResponse,
    ChunkPreviewItem,       
    ChunkPreviewResponse,   
)
from app.core.deps import get_current_user
from app.core.config import settings
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    """
    Save uploaded file to disk.
    
    Args:
        upload_file: FastAPI UploadFile object
        destination: Path where to save file
    """
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    topic: TopicEnum = Form(...),
    title: Optional[str] = Form(None),
    is_public: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF document for RAG indexing.
    
    **User uploads their study materials (private or public).**
    
    - Validates file type and size
    - Saves file to disk
    - Creates database record
    - Queues background processing task
    - Returns immediately (async processing)
    
    **Privacy:**
    - is_public=False: Only you can access (default)
    - is_public=True: Everyone can access
    """
    logger.info(f"📤 Upload request from user {current_user.id}: {file.filename}")
    
    # 1. Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # 2. Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()  # Get position (file size)
    file.file.seek(0)  # Reset to beginning
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB"
        )
    
    logger.info(f"   File size: {file_size / 1024:.1f} KB")
    
    # 3. Generate title if not provided
    if not title:
        title = file.filename.replace('.pdf', '').replace('_', ' ').title()
    
    # 4. Save file to disk
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_id = f"{current_user.id}_{int(os.times().elapsed * 1000)}_{file.filename}"
    file_path = upload_dir / file_id
    
    try:
        save_upload_file(file, file_path)
        logger.info(f"   ✅ File saved: {file_path}")
    except Exception as e:
        logger.error(f"   ❌ Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")
    
    # 5. Create database record
    try:
        document = RAGDocument(
            title=title,
            filename=file.filename,
            topic=topic.value,
            user_id=current_user.id,
            is_public=is_public,
            collection_name=settings.QDRANT_COLLECTION,
            status="processing",
            file_size_bytes=file_size
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(f"   ✅ Database record created: ID={document.id}")
        
    except Exception as e:
        logger.error(f"   ❌ Database error: {e}")
        # Clean up file if database fails
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail="Database error")
    
    # 6. Queue Celery task for background processing
    try:
        celery_app.send_task(
            'app.tasks.rag_tasks.process_pdf_task',
            args=[document.id, str(file_path)]
        )
        logger.info(f"   ✅ Celery task queued for document {document.id}")
        
    except Exception as e:
        logger.error(f"   ❌ Failed to queue task: {e}")
        # Update document status
        document.status = "failed"
        document.error_message = "Failed to queue processing task"
        db.commit()
    
    # 7. Return response
    return UploadResponse(
        document_id=document.id,
        title=document.title,
        filename=document.filename,
        topic=document.topic,
        status=document.status
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    topic: Optional[TopicEnum] = Query(None, description="Filter by topic"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List user's uploaded documents.
    
    **Filters:**
    - topic: Filter by programming topic
    - status: Filter by processing status
    - Pagination: page and page_size
    
    **Returns only user's own documents** (privacy enforced)
    """
    # Build query
    query = db.query(RAGDocument).filter(RAGDocument.user_id == current_user.id)
    
    # Apply filters
    if topic:
        query = query.filter(RAGDocument.topic == topic.value)
    
    if status:
        query = query.filter(RAGDocument.status == status.value)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    documents = query.order_by(RAGDocument.created_at.desc()).offset(offset).limit(page_size).all()
    
    return DocumentListResponse(
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific document details.
    
    **Authorization:**
    - Users can only view their own documents
    - Admins can view all documents
    """
    document = db.query(RAGDocument).filter(RAGDocument.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check authorization
    if document.user_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this document")
    
    return DocumentResponse.from_orm(document)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a document.
    
    **Actions:**
    1. Delete from database
    2. Delete from Qdrant (vector DB)
    3. Delete file from disk
    
    **Authorization:**
    - Users can only delete their own documents
    - Admins can delete any document
    """
    from app.services.rag.indexer import get_indexer
    
    document = db.query(RAGDocument).filter(RAGDocument.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check authorization
    if document.user_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")
    
    logger.info(f"🗑️  Deleting document {document_id}")
    
    # 1. Delete from Qdrant
    try:
        indexer = get_indexer()
        indexer.delete_document(
            collection_name=settings.QDRANT_COLLECTION,
            document_id=document_id
        )
        logger.info(f"   ✅ Deleted from Qdrant")
    except Exception as e:
        logger.warning(f"   ⚠️  Failed to delete from Qdrant: {e}")
    
    # 2. Delete file from disk (if exists)
    try:
        upload_dir = Path(settings.UPLOAD_DIR)
        # Find file (filename pattern: {user_id}_{timestamp}_{original_filename})
        for file_path in upload_dir.glob(f"{document.user_id}_*_{document.filename}"):
            file_path.unlink()
            logger.info(f"   ✅ Deleted file: {file_path}")
            break
    except Exception as e:
        logger.warning(f"   ⚠️  Failed to delete file: {e}")
    
    # 3. Delete from database
    db.delete(document)
    db.commit()
    logger.info(f"   ✅ Deleted from database")
    
    return {"message": "Document deleted successfully", "document_id": document_id}


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    top_k: int = Query(default=None, ge=1, le=50, description="Number of results"),
    topic: Optional[TopicEnum] = Query(default=None, description="Filter by topic"),
    score_threshold: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic search across the user's uploaded documents.

    Unlike the RAG pipeline, this endpoint:
    - Uses a lower score threshold (exploratory browsing, not LLM injection)
    - Returns raw chunks with metadata (no LLM involved)
    - Returns more results (SEARCH_TOP_K vs RAG_TOP_K)
    """
    logger.info(f"🔍 Search request from user {current_user.id}: '{q[:60]}'")

    retriever = get_retriever()

    results = retriever.retrieve(
        query=q,
        user_id=current_user.id,
        top_k=top_k or settings.SEARCH_TOP_K,
        score_threshold=score_threshold or settings.SEARCH_SCORE_THRESHOLD,
        topic=topic.value if topic else None,
        include_public=True,
    )

    items = [
        SearchResultItem(
            chunk_text=r["chunk_text"],
            score=r["score"],
            document_id=r["document_id"],
            title=r["title"],
            chunk_type=r.get("chunk_type", "prose"),
            page_numbers=r.get("page_numbers", []),
            chunk_index=r.get("chunk_index", 0),
        )
        for r in results
    ]

    logger.info(f"✅ Search returned {len(items)} results")

    return SearchResponse(query=q, results=items, total=len(items))


@router.get("/chunks", response_model=ChunkPreviewResponse)
async def get_chunk_preview(
    document_id: int = Query(..., description="Document ID"),
    chunk_index: int = Query(..., ge=0, description="Target chunk index"),
    window: int = Query(default=2, ge=0, le=5, description="Neighbors on each side"),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch a chunk and its neighbors for the preview panel.

    Returns the target chunk plus `window` chunks before and after it,
    ordered by chunk_index. The target chunk is flagged with is_target=True.
    """
    retriever = get_retriever()
    result = retriever.retrieve_chunk_preview(document_id, chunk_index, window, current_user.id)

    if not result:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return ChunkPreviewResponse(**result)
