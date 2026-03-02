"""
Indexer Service

Processes PDFs and indexes them into Qdrant vector database.

Pipeline:
1. Extract text from PDF (pymupdf) with page boundary tracking
2. Chunk text (SemanticChunker)
3. Map chunks to page numbers via character positions
4. Generate embeddings (sentence-transformers)
5. Upload to Qdrant with metadata
"""
import logging
import pymupdf  # PyMuPDF (fitz)
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
        Extract text from PDF using PyMuPDF's built-in text extraction.
        
        Uses page.get_text("text") for clean extraction and tracks
        character positions of each page for post-chunking page mapping.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (full_text, metadata_dict)
            metadata includes page_boundaries: [(start_char, page_num), ...]
        """
        try:
            logger.info(f"📄 Extracting text from: {pdf_path}")
            
            doc = pymupdf.open(pdf_path)
            
            metadata = {
                "pages_count": len(doc),
                "file_size_bytes": Path(pdf_path).stat().st_size,
            }
            
            # Extract text per page, tracking character positions
            page_boundaries = []  # [(start_char, page_num), ...]
            cleaned_parts = []
            current_pos = 0
            
            for page_num, page in enumerate(doc, 1):
                page_text = page.get_text("text").strip()
                if page_text:
                    page_boundaries.append((current_pos, page_num))
                    cleaned_parts.append(page_text)
                    current_pos += len(page_text) + 2  # +2 for "\n\n" separator
            
            doc.close()
            
            full_text = "\n\n".join(cleaned_parts)
            metadata["page_boundaries"] = page_boundaries
            
            logger.info(f"✅ Extracted {len(full_text)} characters from {metadata['pages_count']} pages")
            logger.info(f"   Pages with text: {len(page_boundaries)}/{metadata['pages_count']}")
            
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"❌ PDF extraction failed: {e}")
            raise
    
    def _get_chunk_pages(
        self,
        chunk: str,
        full_text: str,
        page_boundaries: list[tuple[int, int]],
        search_from: int = 0
    ) -> tuple[list[int], int]:
        """
        Map a chunk to its page number(s) using character positions.
        
        Finds the chunk in full_text, then checks which page boundaries
        it overlaps with.
        
        Args:
            chunk: The text chunk to locate
            full_text: The complete document text
            page_boundaries: List of (start_char, page_num) tuples
            search_from: Start searching from this position (sequential matching)
            
        Returns:
            Tuple of (page_numbers list, next_search_position)
        """
        # Find chunk position (search sequentially to handle duplicate text)
        start = full_text.find(chunk, search_from)
        if start == -1:
            # Fallback: search from beginning
            start = full_text.find(chunk)
        if start == -1:
            return [], search_from
        
        end = start + len(chunk)
        
        # Find which pages this chunk overlaps
        pages = set()
        for i, (boundary_start, page_num) in enumerate(page_boundaries):
            # Determine where this page ends
            if i + 1 < len(page_boundaries):
                boundary_end = page_boundaries[i + 1][0]
            else:
                boundary_end = len(full_text)
            
            # Check if chunk overlaps with this page's range
            if start < boundary_end and end > boundary_start:
                pages.add(page_num)
        
        return sorted(pages), end
    
    def _ensure_collection(self, collection_name: str, vector_size: int = None):
        """
        Create Qdrant collection if it doesn't exist.
        
        Args:
            collection_name: Name of the collection
            vector_size: Embedding dimension (defaults to embedder dimension)
        """
        vector_size = vector_size or self.embedder.get_dimension()
        
        try:
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
        Complete indexing pipeline: Extract → Chunk → Map Pages → Embed → Upload.
        
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
            
            # 1. Extract text from PDF (with page boundaries)
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
            
            # 5. Prepare points for Qdrant (with page mapping)
            logger.info(f"📊 Preparing points for upload...")
            points = []
            
            # Extract page boundaries (remove from metadata before storing in Qdrant)
            page_boundaries = pdf_metadata.pop("page_boundaries", [])
            
            search_pos = 0
            chunks_with_pages = 0
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Map chunk to page number(s) by character position
                page_numbers, search_pos = self._get_chunk_pages(
                    chunk, text, page_boundaries, search_pos
                )
                
                if page_numbers:
                    chunks_with_pages += 1
                
                point_metadata = {
                    **metadata,  # user_id, title, language, is_public, document_id
                    "chunk_index": i,
                    "chunk_text": chunk,
                    "page_numbers": page_numbers,
                    "pages_count": pdf_metadata["pages_count"],
                    "file_size_bytes": pdf_metadata["file_size_bytes"]
                }
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
                    payload=point_metadata
                )
                
                points.append(point)
            
            logger.info(f"📄 Page mapping: {chunks_with_pages}/{len(chunks)} chunks have page numbers")
            
            # 6. Upload to Qdrant
            logger.info(f"⬆️  Uploading {len(points)} points to Qdrant...")
            
            self.client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True
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