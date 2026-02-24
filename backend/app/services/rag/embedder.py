"""
Embedder Service

Generates vector embeddings for text using sentence-transformers.
Uses the model specified in config (BAAI/bge-small-en-v1.5).
"""
import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Union

from app.core.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """
    Generate embeddings for text chunks.
    
    Uses sentence-transformers with the configured model.
    Embeddings are cached in memory for efficiency.
    """
    
    def __init__(
        self,
        model_name: str = None,
        device: str = None
    ):
        """
        Initialize embedder.
        
        Args:
            model_name: HuggingFace model name (defaults to config)
            device: 'cpu', 'cuda', or 'mps' (defaults to config)
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.device = device or settings.EMBEDDING_DEVICE
        self.dimension = settings.EMBEDDING_DIM
        
        logger.info(f"🧠 Loading embedding model: {self.model_name}")
        logger.info(f"   Device: {self.device}")
        logger.info(f"   Dimension: {self.dimension}")
        
        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device
            )
            logger.info(f"✅ Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            raise
    
    def embed(self, text: str) -> np.ndarray:
        """
        Generate embedding for single text.
        
        Args:
            text: Input text
            
        Returns:
            Numpy array of shape (dimension,)
        """
        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            return embedding
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            raise
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            batch_size: Number of texts to process at once
            show_progress: Show progress bar
            
        Returns:
            Numpy array of shape (len(texts), dimension)
        """
        try:
            logger.info(f"📊 Generating embeddings for {len(texts)} texts...")
            
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=show_progress
            )
            
            logger.info(f"✅ Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Batch embedding generation failed: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension
    
    def get_model_name(self) -> str:
        """Get model name"""
        return self.model_name


# Singleton instance (lazy loading)
_embedder_instance = None


def get_embedder() -> Embedder:
    """
    Get singleton embedder instance.
    
    Lazy loading - model is only loaded when first used.
    """
    global _embedder_instance
    
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    
    return _embedder_instance
