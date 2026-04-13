"""
RAG API Routes
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.rag_document import RAGDocument
from app.models.user import User
from app.schemas.rag import (
    ChunkPreviewResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatus,
    SearchResponse,
    SearchResultItem,
    TaskStatusResponse,
    TopicEnum,
    UploadResponse,
)
from app.services.rag.retriever import get_retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
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
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"📤 Upload request from user {current_user.id}: {file.filename}")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB",
        )

    if not title:
        title = file.filename.replace(".pdf", "").replace("_", " ").title()

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = f"{current_user.id}_{int(os.times().elapsed * 1000)}_{file.filename}"
    file_path = upload_dir / file_id

    try:
        save_upload_file(file, file_path)
    except Exception as e:
        logger.error(f"❌ Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")

    try:
        document = RAGDocument(
            title=title,
            filename=file.filename,
            topic=topic.value,
            user_id=current_user.id,
            is_public=is_public,
            collection_name=settings.QDRANT_COLLECTION,
            status="processing",
            file_size_bytes=file_size,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail="Database error")

    try:
        task = celery_app.send_task(
            "app.tasks.rag_tasks.process_pdf_task",
            args=[document.id, str(file_path)],
            kwargs={
                "user_id": document.user_id,
                "title": document.title,
                "topic": document.topic,
                "is_public": document.is_public,
            },
        )
        document.task_id = task.id

        await db.commit()
        logger.info(f"✅ Celery task queued for document {document.id}")
    except Exception as e:
        logger.error(f"❌ Failed to queue task: {e}")
        document.status = "failed"
        document.error_message = "Failed to queue processing task"
        await db.commit()

    return UploadResponse(
        document_id=document.id,
        title=document.title,
        filename=document.filename,
        topic=document.topic,
        status=document.status,
        task_id=document.task_id,
    )


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    _: User = Depends(get_current_user),
):
    result = AsyncResult(task_id, app=celery_app)
    state = result.state
    stage = detail = None

    if state == "PROGRESS" and isinstance(result.info, dict):
        stage = result.info.get("stage")
        detail = result.info.get("detail")

    return TaskStatusResponse(task_id=task_id, state=state, stage=stage, detail=detail)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    topic: Optional[TopicEnum] = Query(None),
    status: Optional[DocumentStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RAGDocument).where(RAGDocument.user_id == current_user.id)

    if topic:
        stmt = stmt.where(RAGDocument.topic == topic.value)
    if status:
        stmt = stmt.where(RAGDocument.status == status.value)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(RAGDocument.created_at.desc()).offset(offset).limit(page_size)
    )
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RAGDocument).where(RAGDocument.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.user_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this document")

    return DocumentResponse.from_orm(document)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.rag.indexer import get_indexer

    result = await db.execute(select(RAGDocument).where(RAGDocument.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.user_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    try:
        indexer = get_indexer()
        indexer.delete_document(collection_name=settings.QDRANT_COLLECTION, document_id=document_id)
    except Exception as e:
        logger.warning(f"⚠️ Failed to delete from Qdrant: {e}")

    try:
        upload_dir = Path(settings.UPLOAD_DIR)
        for file_path in upload_dir.glob(f"{document.user_id}_*_{document.filename}"):
            file_path.unlink()
    except Exception as e:
        logger.warning(f"⚠️ Failed to delete file: {e}")

    await db.delete(document)
    await db.commit()

    return {"message": "Document deleted successfully", "document_id": document_id}


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(default=None, ge=1, le=50),
    topic: Optional[TopicEnum] = Query(default=None),
    score_threshold: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_user),
):
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

    return SearchResponse(query=q, results=items, total=len(items))


@router.get("/chunks", response_model=ChunkPreviewResponse)
async def get_chunk_preview(
    document_id: int = Query(...),
    chunk_index: int = Query(..., ge=0),
    window: int = Query(default=2, ge=0, le=5),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RAGDocument).where(RAGDocument.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    retriever = get_retriever()
    result = retriever.retrieve_chunk_preview(document_id, chunk_index, window)

    if not result:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return ChunkPreviewResponse(**result)
