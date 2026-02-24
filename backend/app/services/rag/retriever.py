"""
Retriever Service

Searches Qdrant vector database for relevant context.
Filters by user ownership (private) and public documents.
"""
import logging
from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    QueryResponse,
    ScoredPoint
)

from app.core.config import settings
from app.services.rag.embedder import get_embedder

logger = logging.getLogger(__name__)


class Retriever:
    """
    Retrieve relevant chunks from Qdrant based on query.
    
    Supports:
    - Semantic search using embeddings
    - Filtering by user ownership
    - Public document access
    - Score thresholding
    """
    
    def __init__(
        self,
        qdrant_url: str = None,
        collection_name: str = None,
        top_k: int = None,
        score_threshold: float = None
    ):
        """
        Initialize Retriever.
        
        Args:
            qdrant_url: Qdrant server URL (defaults to config)
            collection_name: Collection to search (defaults to config)
            top_k: Number of results to return (defaults to config)
            score_threshold: Minimum similarity score (defaults to config)
        """
        self.qdrant_url = qdrant_url or settings.QDRANT_URL
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.top_k = top_k or settings.RAG_TOP_K
        self.score_threshold = score_threshold or settings.RAG_SCORE_THRESHOLD
        
        logger.info(f"🔍 Initializing Retriever:")
        logger.info(f"   Qdrant URL: {self.qdrant_url}")
        logger.info(f"   Collection: {self.collection_name}")
        logger.info(f"   Top K: {self.top_k}")
        logger.info(f"   Score Threshold: {self.score_threshold}")
        
        try:
            self.client = QdrantClient(url=self.qdrant_url)
            self.embedder = get_embedder()
            logger.info(f"✅ Retriever initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize retriever: {e}")
            raise
    
    def retrieve(
        self,
        query: str,
        user_id: Optional[int] = None,
        top_k: Optional[int] = None,
        topic: Optional[str] = None,
        score_threshold: Optional[float] = None,
        include_public: bool = True
    ) -> List[Dict]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User's question/query
            user_id: User ID (to filter private documents). If None, only public docs.
            top_k: Number of results (overrides default)
            score_threshold: Minimum score (overrides default)
            topic: Topic to filter by (optional)
            
        Returns:
            List of dicts with:
              - chunk_text: The text chunk
              - score: Similarity score
              - document_id: Document ID
              - title: Document title
              - metadata: Additional metadata
        """
        try:
            top_k = top_k or self.top_k
            score_threshold = score_threshold or self.score_threshold
            
            logger.info(f"🔍 Retrieving context for query: '{query[:50]}...'")
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Top K: {top_k}")
            logger.info(f"   Score threshold: {score_threshold}")
            
            # 1. Generate query embedding
            logger.info(f"🧠 Generating query embedding...")
            query_embedding = self.embedder.embed(query)
            logger.info(f"✅ Query embedding generated: shape {query_embedding.shape}")
            
            # 2. Build filter (user's docs OR public docs)
            search_filter = self._build_filter(user_id, include_public, topic)
            
            # 3. Search Qdrant using query_points (NEW API)
            logger.info(f"📊 Searching Qdrant...")
            
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding.tolist(),
                query_filter=search_filter,
                limit=top_k,
                score_threshold=score_threshold
            )
            
            # Extract points from response
            points = search_results.points if hasattr(search_results, 'points') else search_results
            
            logger.info(f"✅ Found {len(points)} results")
            
            # 4. Format results
            results = self._format_results(points)
            
            # 5. Log results
            for i, result in enumerate(results, 1):
                logger.info(f"   Result {i}: score={result['score']:.3f}, "
                          f"doc={result['document_id']}, "
                          f"title='{result['title']}'")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Retrieval failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _build_filter(
        self,
        user_id: Optional[int],
        include_public: bool,
        topic: Optional[str] = None
) -> Optional[Filter]:
        """
        Build Qdrant filter for user ownership, public docs, and topic.

        Filter logic:
        - Privacy: (user_id = X) OR (is_public = true)
        - Topic: topic = Y (if specified) - AND condition
        """
        # Privacy conditions (OR logic)
        should_conditions = []

        if user_id is not None:
            should_conditions.append(
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            )

        if include_public:
            should_conditions.append(
                FieldCondition(key="is_public", match=MatchValue(value=True))
            )

        # Topic condition (AND logic)
        must_conditions = []
        if topic:
            must_conditions.append(
                FieldCondition(key="topic", match=MatchValue(value=topic))
            )

        # Build filter
        if not should_conditions and not must_conditions:
            return None

        filter_dict = {}
        if should_conditions:
            filter_dict["should"] = should_conditions
        if must_conditions:
            filter_dict["must"] = must_conditions

        return Filter(**filter_dict)
    
    def _format_results(self, search_results: List[ScoredPoint]) -> List[Dict]:
        """
        Format Qdrant search results into clean dicts.
        
        Args:
            search_results: Raw Qdrant search results
            
        Returns:
            List of formatted result dicts
        """
        formatted = []
        
        for result in search_results:
            formatted.append({
                "chunk_text": result.payload.get("chunk_text", ""),
                "score": result.score,
                "document_id": result.payload.get("document_id"),
                "title": result.payload.get("title", "Unknown"),
                "language": result.payload.get("language", "java"),
                "chunk_index": result.payload.get("chunk_index", 0),
                "is_public": result.payload.get("is_public", False),
                "metadata": {
                    "pages_count": result.payload.get("pages_count"),
                    "file_size_bytes": result.payload.get("file_size_bytes"),
                    "user_id": result.payload.get("user_id")
                }
            })
        
        return formatted
    
    def retrieve_by_document(
        self,
        document_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Retrieve chunks from a specific document.
        
        Useful for viewing document contents.
        
        Args:
            document_id: Document ID to retrieve from
            limit: Maximum number of chunks
            
        Returns:
            List of chunks from the document
        """
        try:
            logger.info(f"📄 Retrieving chunks from document {document_id}")
            
            # Scroll through collection filtering by document_id
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            logger.info(f"✅ Retrieved {len(results)} chunks from document {document_id}")
            
            # Format results (no scores since this isn't search)
            formatted = []
            for point in results:
                formatted.append({
                    "chunk_text": point.payload.get("chunk_text", ""),
                    "chunk_index": point.payload.get("chunk_index", 0),
                    "document_id": document_id,
                    "title": point.payload.get("title", "Unknown")
                })
            
            # Sort by chunk index
            formatted.sort(key=lambda x: x["chunk_index"])
            
            return formatted
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve document chunks: {e}")
            raise


# Singleton instance
_retriever_instance = None


def get_retriever() -> Retriever:
    """
    Get singleton retriever instance.
    
    Lazy loading - Qdrant client is only created when first used.
    """
    global _retriever_instance
    
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    
    return _retriever_instance
