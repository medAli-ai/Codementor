"""
RAG Background Tasks

Celery tasks for processing PDFs asynchronously.
"""
import logging
from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.rag_document import RAGDocument
from app.services.rag.indexer import get_indexer
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_pdf_task(self, document_id: int, file_path: str):
    """
    Process PDF file: extract text, chunk, embed, and index.
    
    Args:
        document_id: RAGDocument ID in database
        file_path: Path to uploaded PDF file
    
    This task runs in background (Celery worker).
    """
    db = SessionLocal()
    
    try:
        logger.info(f"📄 Processing document {document_id} from {file_path}")
        
        # Get document from database
        document = db.query(RAGDocument).filter(RAGDocument.id == document_id).first()
        
        if not document:
            logger.error(f"❌ Document {document_id} not found in database")
            return
        
        # Update status to processing
        document.status = "processing"
        db.commit()
        
        # Initialize indexer
        indexer = get_indexer()
        
        # Index the PDF
        logger.info(f"🔄 Starting indexing for document {document_id}")
        chunks_count = indexer.index_pdf(
            pdf_path=file_path,
            collection_name=settings.QDRANT_COLLECTION,
            metadata={
                "document_id": document.id,
                "user_id": document.user_id,
                "title": document.title,
                "language": "java",  # Legacy field (TODO: remove)
                "topic": document.topic,  # 🆕 NEW!
                "is_public": document.is_public
            }
        )
        
        logger.info(f"✅ Indexed {chunks_count} chunks for document {document_id}")
        
        # Update document status
        document.status = "completed"
        document.chunks_count = chunks_count
        db.commit()
        
        logger.info(f"✅ Document {document_id} processed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error processing document {document_id}: {e}")
        
        # Update document with error
        try:
            document = db.query(RAGDocument).filter(RAGDocument.id == document_id).first()
            if document:
                document.status = "failed"
                document.error_message = str(e)[:500]  # Limit error message length
                db.commit()
        except Exception as update_error:
            logger.error(f"❌ Failed to update error status: {update_error}")
        
        # Retry task
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"❌ Max retries exceeded for document {document_id}")
    
    finally:
        db.close()
        
        # Clean up uploaded file (optional)
        # import os
        # if os.path.exists(file_path):
        #     os.remove(file_path)
        #     logger.info(f"🗑️  Cleaned up file: {file_path}")
