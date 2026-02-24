"""
Indexer Service

Processes PDFs and indexes them into Qdrant vector database.

Pipeline:
1. Extract text from PDF (pymupdf)
2. Clean and normalize text
3. Chunk text (SemanticChunker)
4. Generate embeddings (sentence-transformers)
5. Upload to Qdrant with metadata
"""
import logging
import pymupdf  # PyMuPDF (fitz)
import re
from pathlib import Path
from typing import List, Dict, Optional
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)

from app.core.config import settings
from app.services.rag.embedder import get_embedder
from app.services.rag.chunker import get_chunker

logger = logging.getLogger(__name__)


class Indexer:
    """
    Index PDFs into Qdrant vector database.
    
    Focused on clean text extraction for RAG retrieval.
    """
    
    def __init__(
        self,
        qdrant_url: str = None,
        collection_name: str = None
    ):
        """
        Initialize Indexer.
        
        Args:
            qdrant_url: Qdrant server URL (defaults to config)
            collection_name: Default collection name (defaults to config)
        """
        self.qdrant_url = qdrant_url or settings.QDRANT_URL
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        
        logger.info(f"📊 Initializing Indexer:")
        logger.info(f"   Qdrant URL: {self.qdrant_url}")
        logger.info(f"   Collection: {self.collection_name}")
        
        # Initialize clients
        try:
            self.client = QdrantClient(url=self.qdrant_url)
            self.embedder = get_embedder()
            self.chunker = get_chunker()
            logger.info(f"✅ Indexer initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize indexer: {e}")
            raise
    
    def extract_pdf_text(self, pdf_path: str) -> tuple[str, dict]:
        """
        Extract clean text from PDF using PyMuPDF.
        
        Inspired by rag-ingest approach but simplified for RAG.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, metadata_dict)
        """
        try:
            logger.info(f"📄 Extracting text from: {pdf_path}")
            
            # Open PDF
            doc = pymupdf.open(pdf_path)
            
            # Extract metadata
            metadata = {
                "pages_count": len(doc),
                "file_size_bytes": Path(pdf_path).stat().st_size,
                "pdf_title": doc.metadata.get("title", ""),
                "pdf_author": doc.metadata.get("author", "")
            }
            
            # Extract text from all pages
            text_parts = []
            
            for page_num, page in enumerate(doc, 1):
                # Get page dimensions
                page_rect = page.rect
                page_height = page_rect.height
                
                # Extract text blocks
                blocks = page.get_text("dict")["blocks"]
                page_text_parts = []
                
                for block in blocks:
                    if block["type"] == 0:  # Text block
                        block_rect = block["bbox"]
                        
                        # Skip headers and footers (top 50px, bottom 50px)
                        if block_rect[1] < 50 or block_rect[3] > page_height - 50:
                            continue
                        
                        # Extract text from lines
                        block_text = []
                        for line in block["lines"]:
                            line_text = ""
                            for span in line["spans"]:
                                text = span["text"].strip()
                                if text:
                                    line_text += text + " "
                            
                            if line_text.strip():
                                block_text.append(line_text.strip())
                        
                        # Join lines with space
                        if block_text:
                            page_text_parts.append(" ".join(block_text))
                
                # Join blocks with double newline
                if page_text_parts:
                    page_text = "\n\n".join(page_text_parts)
                    text_parts.append(page_text)
                    logger.debug(f"   Page {page_num}: {len(page_text)} chars extracted")
            
            doc.close()
            
            # Combine all pages
            full_text = "\n\n".join(text_parts)
            
            # Clean the text
            full_text = self._clean_text(full_text)
            
            logger.info(f"✅ Extracted {len(full_text)} characters from {metadata['pages_count']} pages")
            
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"❌ PDF extraction failed: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines (keep max 2)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove page numbers (standalone digits)
        text = re.sub(r'\n\d+\n', '\n', text)
        
        # Fix common OCR issues
        text = text.replace('ﬁ', 'fi')
        text = text.replace('ﬂ', 'fl')
        text = text.replace('–', '-')
        text = text.replace('—', '-')
        
        # Remove multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Strip and return
        return text.strip()
    
    def _ensure_collection(self, collection_name: str, vector_size: int = None):
        """
        Create Qdrant collection if it doesn't exist.
        
        Args:
            collection_name: Name of the collection
            vector_size: Embedding dimension (defaults to embedder dimension)
        """
        vector_size = vector_size or self.embedder.get_dimension()
        
        try:
            # Get existing collections
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if collection_name not in collection_names:
                logger.info(f"📦 Creating collection: {collection_name}")
                
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                
                logger.info(f"✅ Collection created successfully")
            else:
                logger.info(f"✅ Collection already exists: {collection_name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection: {e}")
            raise
    
    def index_pdf(
        self,
        pdf_path: str,
        collection_name: str,
        metadata: dict
    ) -> int:
        """
        Complete indexing pipeline: Extract → Chunk → Embed → Upload.
        
        Args:
            pdf_path: Path to PDF file
            collection_name: Qdrant collection name
            metadata: Additional metadata (user_id, title, is_public, etc.)
        
        Returns:
            Number of chunks indexed
        """
        try:
            logger.info(f"🔄 Starting PDF indexing pipeline")
            logger.info(f"   PDF: {pdf_path}")
            logger.info(f"   Collection: {collection_name}")
            
            # 1. Extract text from PDF
            text, pdf_metadata = self.extract_pdf_text(pdf_path)
            
            if not text or len(text) < 100:
                raise ValueError(f"Insufficient text extracted: {len(text)} chars")
            
            # 2. Chunk text
            logger.info(f"✂️  Chunking text...")
            chunks = self.chunker.chunk(text)
            
            if not chunks:
                raise ValueError("No chunks generated from text")
            
            logger.info(f"✅ Generated {len(chunks)} chunks")
            
            # 3. Generate embeddings
            logger.info(f"🧠 Generating embeddings...")
            embeddings = self.embedder.embed_batch(
                chunks,
                batch_size=32,
                show_progress=True
            )
            
            logger.info(f"✅ Generated {len(embeddings)} embeddings")
            
            # 4. Ensure collection exists
            self._ensure_collection(collection_name)
            
            # 5. Prepare points for Qdrant
            logger.info(f"📊 Preparing points for upload...")
            points = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Merge PDF metadata with provided metadata
                point_metadata = {
                    **metadata,  # user_id, title, language, is_public, document_id
                    "chunk_index": i,
                    "chunk_text": chunk,
                    "pages_count": pdf_metadata["pages_count"],
                    "file_size_bytes": pdf_metadata["file_size_bytes"]
                }
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
                    payload=point_metadata
                )
                
                points.append(point)
            
            # 6. Upload to Qdrant
            logger.info(f"⬆️  Uploading {len(points)} points to Qdrant...")
            
            self.client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True  # Wait for indexing to complete
            )
            
            logger.info(f"✅ Upload complete!")
            logger.info(f"📊 Indexed {len(chunks)} chunks from {pdf_path}")
            
            return len(chunks)
            
        except Exception as e:
            logger.error(f"❌ Indexing failed: {e}")
            raise
    
    def delete_document(
        self,
        collection_name: str,
        document_id: int
    ) -> bool:
        """
        Delete all chunks for a specific document.
        
        Args:
            collection_name: Qdrant collection name
            document_id: Document ID to delete
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"🗑️  Deleting document {document_id} from {collection_name}")
            
            # Delete points with matching document_id
            self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            
            logger.info(f"✅ Document {document_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete document: {e}")
            return False


# Singleton instance
_indexer_instance = None


def get_indexer() -> Indexer:
    """
    Get singleton indexer instance.
    
    Lazy loading - Qdrant client is only created when first used.
    """
    global _indexer_instance
    
    if _indexer_instance is None:
        _indexer_instance = Indexer()
    
    return _indexer_instance
