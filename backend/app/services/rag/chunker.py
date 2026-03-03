"""
Chunker Service

Splits text into semantic chunks using Chonkie's SemanticChunker.
Uses semantic similarity to group related sentences together.
"""
import logging
from typing import List
from chonkie import SemanticChunker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Chunker:
    """
    Split text into semantic chunks using SemanticChunker.
    
    The chunker:
    1. Splits text into sentences
    2. Calculates semantic similarity between sentences
    3. Groups similar sentences into chunks
    4. Respects chunk_size limits
    """
    
    def __init__(
        self,
        embedding_model: str = None,
        threshold: float = None,
        chunk_size: int = None,
        skip_window: int = 1
    ):
        """
        Initialize SemanticChunker.
        
        Args:
            embedding_model: HuggingFace model for embeddings (defaults to config)
            threshold: Similarity threshold 0-1, lower = larger groups (defaults to config)
            chunk_size: Maximum tokens per chunk (defaults to config)
            skip_window: Number of groups to skip when merging (1 = look past code blocks)
        """
        self.embedding_model = embedding_model or settings.EMBEDDING_MODEL
        self.threshold = threshold or settings.RAG_CHUNK_THRESHOLD  # FIXED: was RAG_SCORE_THRESHOLD
        self.chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        self.skip_window = skip_window
        
        logger.info(f"✂️  Initializing SemanticChunker:")
        logger.info(f"   Embedding Model: {self.embedding_model}")
        logger.info(f"   Threshold: {self.threshold} (0-1, lower = larger chunks)")
        logger.info(f"   Chunk Size: {self.chunk_size} tokens")
        logger.info(f"   Skip Window: {self.skip_window}")
        
        try:
            self.chunker = SemanticChunker(
                embedding_model=self.embedding_model,
                threshold=self.threshold,
                chunk_size=self.chunk_size,
                min_sentences_per_chunk=1,
                skip_window=self.skip_window
            )
            logger.info(f"✅ SemanticChunker initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize chunker: {e}")
            raise
    
    def chunk(self, text: str) -> List[str]:
        """
        Split text into semantic chunks.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of text chunks
        """
        try:
            if not text or not text.strip():
                logger.warning("⚠️  Empty text provided to chunker")
                return []
            
            logger.info(f"✂️  Chunking text ({len(text)} chars)...")
            
            # Chunk the text
            chunks_obj = self.chunker.chunk(text)
            
            # Extract text from Chunk objects
            chunks = [chunk.text for chunk in chunks_obj]
            
            # Log statistics
            logger.info(f"✅ Created {len(chunks)} chunks")
            if chunks:
                avg_chars = sum(len(c) for c in chunks) / len(chunks)
                avg_tokens = sum(chunk.token_count for chunk in chunks_obj) / len(chunks_obj)
                logger.info(f"   Avg size: {avg_chars:.0f} chars, {avg_tokens:.0f} tokens")
            
            return chunks
            
        except Exception as e:
            logger.error(f"❌ Chunking failed: {e}")
            raise
    
    def chunk_batch(self, texts: List[str]) -> List[List[str]]:
        """
        Chunk multiple texts efficiently.
        
        Args:
            texts: List of texts to chunk
            
        Returns:
            List of chunk lists (one per input text)
        """
        try:
            logger.info(f"✂️  Batch chunking {len(texts)} documents...")
            
            # Use Chonkie's batch processing
            batch_results = self.chunker.chunk_batch(texts)
            
            # Convert to list of string lists
            all_chunks = []
            for doc_chunks in batch_results:
                chunks = [chunk.text for chunk in doc_chunks]
                all_chunks.append(chunks)
            
            total_chunks = sum(len(chunks) for chunks in all_chunks)
            logger.info(f"✅ Batch processing complete: {total_chunks} total chunks")
            
            return all_chunks
            
        except Exception as e:
            logger.error(f"❌ Batch chunking failed: {e}")
            raise
    
    def get_stats(self, chunks: List[str]) -> dict:
        """
        Get statistics about chunks.
        
        Args:
            chunks: List of text chunks
            
        Returns:
            Dictionary with statistics
        """
        if not chunks:
            return {
                "count": 0,
                "total_chars": 0,
                "avg_chars": 0,
                "min_chars": 0,
                "max_chars": 0
            }
        
        char_counts = [len(c) for c in chunks]
        
        return {
            "count": len(chunks),
            "total_chars": sum(char_counts),
            "avg_chars": sum(char_counts) / len(chunks),
            "min_chars": min(char_counts),
            "max_chars": max(char_counts)
        }


# Singleton instance
_chunker_instance = None


def get_chunker() -> Chunker:
    """
    Get singleton chunker instance.
    
    Lazy loading - model is only loaded when first used.
    """
    global _chunker_instance
    
    if _chunker_instance is None:
        _chunker_instance = Chunker()
    
    return _chunker_instance