"""
RAG Background Tasks

Celery tasks for processing PDFs asynchronously.
"""

import logging
import uuid

from qdrant_client.models import PointStruct

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.rag_document import RAGDocument
from app.services.rag.indexer import get_indexer

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_pdf_task(
    self,
    document_id: int,
    file_path: str,
    user_id: int,
    title: str,
    topic: str,
    is_public: bool,
):
    """
    Process PDF file: extract text, chunk, embed, and index into Qdrant.
    Metadata is passed directly from the route — no DB read needed at startup.
    Progress is tracked via Celery state in Redis.
    Only terminal state (completed/failed) is written to Postgres.
    """
    db = SessionLocal()

    try:
        logger.info(f"📄 Processing document {document_id} from {file_path}")

        indexer = get_indexer()

        metadata = {
            "document_id": document_id,
            "user_id": user_id,
            "title": title,
            "topic": topic,
            "is_public": is_public,
        }

        # ── Stage 1: Extract ──────────────────────────────────────────
        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "extracting",
                "detail": "Extracting text, code blocks, and tables from PDF...",
            },
        )
        elements, pdf_meta = indexer.extract_pdf_elements(file_path)

        if not elements:
            raise ValueError("No elements extracted from PDF")

        # ── Stage 2: Chunk ────────────────────────────────────────────
        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "chunking",
                "detail": f"Chunking {len(elements)} elements...",
            },
        )
        chunks = indexer._chunk_elements(elements)

        if not chunks:
            raise ValueError("No chunks generated from elements")

        # ── Stage 3: Embed ────────────────────────────────────────────
        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "embedding",
                "detail": f"Generating embeddings for {len(chunks)} chunks...",
            },
        )
        chunk_texts = [c["text"] for c in chunks]
        embeddings = indexer.embedder.embed_batch(
            chunk_texts, batch_size=settings.EMBEDDING_BATCH_SIZE, show_progress=True
        )

        # ── Stage 4: Upload ───────────────────────────────────────────
        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "uploading",
                "detail": f"Uploading {len(chunks)} vectors to Qdrant...",
            },
        )
        indexer._ensure_collection(settings.QDRANT_COLLECTION)

        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
                    payload={
                        **metadata,
                        "chunk_index": i,
                        "chunk_text": chunk["text"],
                        "chunk_type": chunk["chunk_type"],
                        "page_numbers": chunk["page_numbers"],
                        "pages_count": pdf_meta["pages_count"],
                        "file_size_bytes": pdf_meta["file_size_bytes"],
                    },
                )
            )

        indexer.client.upload_points(
            collection_name=settings.QDRANT_COLLECTION,
            points=points,
            batch_size=256,
            parallel=1,
        )

        chunks_count = len(chunks)
        logger.info(f"✅ Indexed {chunks_count} chunks for document {document_id}")

        # ── Terminal write: success ───────────────────────────────────
        document = db.query(RAGDocument).filter(RAGDocument.id == document_id).first()
        if document:
            document.status = "completed"
            document.chunks_count = chunks_count
            db.commit()

        logger.info(f"✅ Document {document_id} processed successfully")

    except Exception as e:
        logger.error(f"❌ Error processing document {document_id}: {e}")

        try:
            countdown = 60 * (2**self.request.retries)
            logger.info(
                f"🔄 Retrying document {document_id} "
                f"(attempt {self.request.retries + 1}/{self.max_retries}), "
                f"next retry in {countdown}s"
            )
            self.retry(exc=e, countdown=countdown)

        except self.MaxRetriesExceededError:
            logger.error(f"❌ Max retries exceeded for document {document_id}")

            # ── Terminal write: failure ───────────────────────────────
            try:
                document = db.query(RAGDocument).filter(RAGDocument.id == document_id).first()
                if document:
                    document.status = "failed"
                    document.error_message = str(e)[:500]
                    db.commit()
            except Exception as update_error:
                logger.error(f"❌ Failed to update error status: {update_error}")

    finally:
        db.close()
