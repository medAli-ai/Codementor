"""
RAG Service (High-Level Orchestration)

Business logic layer for Retrieval Augmented Generation.
Handles topic detection, context retrieval, and seamless integration.
"""

import logging
from typing import Dict, List, Optional

from app.core.config import settings
from app.services.rag.indexer import get_indexer
from app.services.rag.retriever import get_retriever

logger = logging.getLogger(__name__)


# Predefined topics for MVP
SUPPORTED_TOPICS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "cpp",
    "csharp",
    "go",
    "rust",
    "php",
    "ruby",
    "swift",
    "kotlin",
    "sql",
    "web",
    "data-science",
    "machine-learning",
    "algorithms",
    "system-design",
]


# Topic detection keywords
TOPIC_KEYWORDS = {
    "python": [
        "python",
        "django",
        "flask",
        "fastapi",
        "pandas",
        "numpy",
        "decorator",
        "generator",
        "pip",
        "virtualenv",
        "pytest",
        "anaconda",
    ],
    "java": [
        "java",
        "spring",
        "maven",
        "gradle",
        "jvm",
        "inheritance",
        "polymorphism",
        "interface",
        "abstract",
        "ocp",
        "jdk",
        "servlet",
    ],
    "javascript": [
        "javascript",
        "js",
        "node",
        "react",
        "vue",
        "angular",
        "express",
        "typescript",
        "npm",
        "webpack",
        "babel",
        "async",
        "promise",
        "closure",
    ],
    "typescript": ["typescript", "ts", "interface", "generic", "type", "enum", "decorator"],
    "cpp": [
        "c++",
        "cpp",
        "pointer",
        "template",
        "stl",
        "namespace",
        "virtual",
        "destructor",
        "constructor",
        "vector",
        "iterator",
    ],
    "csharp": [
        "c#",
        "csharp",
        ".net",
        "dotnet",
        "linq",
        "entity framework",
        "asp.net",
        "xamarin",
        "blazor",
    ],
    "go": ["golang", "go", "goroutine", "channel", "defer", "interface", "package", "module"],
    "rust": ["rust", "cargo", "ownership", "borrow", "lifetime", "trait", "crate", "macro"],
    "php": ["php", "laravel", "symfony", "composer", "namespace", "trait"],
    "ruby": ["ruby", "rails", "gem", "bundler", "rake", "rspec"],
    "swift": ["swift", "ios", "xcode", "swiftui", "optional", "protocol"],
    "kotlin": ["kotlin", "android", "coroutine", "data class", "sealed class"],
    "web": [
        "html",
        "css",
        "sass",
        "scss",
        "bootstrap",
        "tailwind",
        "responsive",
        "dom",
        "browser",
        "frontend",
    ],
    "data-science": [
        "data science",
        "pandas",
        "numpy",
        "matplotlib",
        "jupyter",
        "scikit-learn",
        "statistics",
        "analysis",
        "visualization",
    ],
    "machine-learning": [
        "machine learning",
        "ml",
        "deep learning",
        "neural network",
        "tensorflow",
        "pytorch",
        "model",
        "training",
        "ai",
    ],
    "sql": [
        "sql",
        "database",
        "query",
        "select",
        "join",
        "index",
        "postgres",
        "mysql",
        "mongodb",
        "nosql",
    ],
    "algorithms": [
        "algorithm",
        "sorting",
        "searching",
        "graph",
        "tree",
        "dynamic programming",
        "recursion",
        "complexity",
        "big o",
    ],
    "system-design": [
        "system design",
        "architecture",
        "scalability",
        "microservices",
        "load balancing",
        "caching",
        "database design",
        "distributed",
    ],
}


# Programming-related keywords (broader detection)
PROGRAMMING_KEYWORDS = [
    # General programming
    "code",
    "coding",
    "program",
    "programming",
    "software",
    "develop",
    "function",
    "method",
    "class",
    "object",
    "variable",
    "array",
    "loop",
    "condition",
    "algorithm",
    "debug",
    "error",
    "exception",
    # Concepts
    "api",
    "rest",
    "http",
    "json",
    "xml",
    "database",
    "cache",
    "testing",
    "deployment",
    "version control",
    "git",
    # Common terms
    "syntax",
    "compile",
    "runtime",
    "memory",
    "thread",
    "process",
    "framework",
    "library",
    "module",
    "package",
    "dependency",
]


class RAGService:
    """
    High-level RAG orchestration service.

    Provides seamless integration of document retrieval into chat.
    Users don't need to know RAG is happening - it just works.
    """

    def __init__(self):
        """Initialize RAG service with core components."""
        self.indexer = get_indexer()
        self.retriever = get_retriever()
        logger.info("✅ RAG Service initialized")

    def is_programming_question(self, query: str) -> bool:
        """
        Detect if query is programming-related.

        Imitates Claude's behavior: Be helpful and inclusive,
        not too strict about detection.

        Args:
            query: User's question

        Returns:
            True if programming-related, False otherwise
        """
        query_lower = query.lower()

        # Check for programming keywords
        for keyword in PROGRAMMING_KEYWORDS:
            if keyword in query_lower:
                logger.info(f"🎯 Programming question detected (keyword: '{keyword}')")
                return True

        # Check for topic-specific keywords
        for topic, keywords in TOPIC_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    logger.info(f"🎯 Programming question detected (topic: {topic})")
                    return True

        logger.info("ℹ️  Not detected as programming question")
        return False

    def detect_topic(self, query: str) -> Optional[str]:
        """
        Auto-detect programming topic from query.

        Imitates Claude: Smart detection with graceful fallback.
        If unsure, returns None (search all topics).

        Args:
            query: User's question

        Returns:
            Detected topic or None (search all)
        """
        query_lower = query.lower()

        # Track keyword matches per topic
        topic_matches = {}

        for topic, keywords in TOPIC_KEYWORDS.items():
            matches = sum(1 for keyword in keywords if keyword in query_lower)
            if matches > 0:
                topic_matches[topic] = matches

        if not topic_matches:
            logger.info("ℹ️  No specific topic detected, will search all documents")
            return None

        # Return topic with most matches
        best_topic = max(topic_matches, key=topic_matches.get)
        match_count = topic_matches[best_topic]

        logger.info(f"🎯 Detected topic: '{best_topic}' ({match_count} keyword matches)")

        return best_topic

    def get_context(
        self, query: str, user_id: int, conversation_context: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get RAG context for a query (seamless, automatic).

        This is the main method chat service calls.
        It handles everything: detection, retrieval, formatting.

        Args:
            query: User's question
            user_id: Current user ID
            conversation_context: Previous conversation (for future use)

        Returns:
            Dict with context info, or None if RAG not applicable
        """
        try:
            # 1. Check if programming-related
            if not self.is_programming_question(query):
                logger.info("⏭️  Skipping RAG (not programming-related)")
                return None

            # 2. Detect topic (optional filter)
            topic = self.detect_topic(query)

            # 3. Retrieve relevant chunks
            logger.info(f"🔍 Retrieving context for user {user_id}...")
            results = self.retriever.retrieve(
                query=query,
                user_id=user_id,
                topic=topic,
                top_k=settings.RAG_TOP_K,
                score_threshold=settings.RAG_SCORE_THRESHOLD,
            )

            if not results:
                logger.info("ℹ️  No relevant context found")
                return None

            # 4. Format context for LLM
            context_text = self._format_context(results)

            logger.info(
                f"✅ Retrieved {len(results)} chunks from {len(set(r['document_id'] for r in results))} documents"
            )

            return {
                "context": context_text,
                "chunks_count": len(results),
                "detected_topic": topic,
                "sources": [
                    {
                        "title": r["title"],
                        "document_id": r["document_id"],
                        "score": r["score"],
                        "page_numbers": r.get("page_numbers", []),
                        "chunk_type": r.get("chunk_type", "prose"),
                        "chunk_index": r.get("chunk_index", None),
                    }
                    for r in results
                ],
            }

        except Exception as e:
            logger.error(f"❌ Error getting context: {e}")
            import traceback

            traceback.print_exc()
            # Fail gracefully - chat continues without RAG
            return None

    def _format_context(self, results: List[Dict]) -> str:
        """
        Format retrieved chunks into context for LLM.

        Groups by document and presents cleanly.

        Args:
            results: Retrieved chunks from Qdrant

        Returns:
            Formatted context string
        """
        context_parts = []

        # Group chunks by document
        docs = {}
        for result in results:
            doc_title = result["title"]
            if doc_title not in docs:
                docs[doc_title] = []
            docs[doc_title].append(result)

        # Format each document's chunks
        for doc_title, chunks in docs.items():
            context_parts.append(f"From '{doc_title}':")
            for chunk in chunks:
                chunk_text = chunk["chunk_text"].strip()
                chunk_type = chunk.get("chunk_type", "prose")
                page_nums = chunk.get("page_numbers", [])
                page_label = f"[Page {', '.join(str(p) for p in page_nums)}] " if page_nums else ""

                if chunk_type == "code":
                    context_parts.append(f"  {page_label}```\n{chunk_text}\n```")
                elif chunk_type == "table":
                    context_parts.append(f"  {page_label}[Table]\n{chunk_text}")
                else:
                    context_parts.append(f"  {page_label}{chunk_text}")
            context_parts.append("")

        return "\n".join(context_parts)

    def enhance_prompt(
        self, query: str, user_id: int, conversation_context: Optional[str] = None
    ) -> tuple[str, Optional[Dict]]:
        """
        Enhance user prompt with RAG context (if applicable).

        Seamless integration - user doesn't know RAG is happening.

        Args:
            query: User's original question
            user_id: Current user ID
            conversation_context: Previous conversation

        Returns:
            Tuple of (enhanced_prompt, rag_metadata)
            - enhanced_prompt: With context injected or original
            - rag_metadata: Info about sources (for UI) or None
        """
        # Get context
        rag_result = self.get_context(query, user_id, conversation_context)

        if not rag_result:
            # No RAG context - return original query
            return query, None

        # Enhance prompt with context
        enhanced = f"""Based on the following reference materials from your uploaded documents:

{rag_result["context"]}

Question: {query}

Please answer using the information from these materials when relevant."""

        logger.info(
            f"✅ Enhanced prompt with {rag_result['chunks_count']} chunks from {len(rag_result['sources'])} documents"
        )

        # Return enhanced prompt and metadata
        return enhanced, {
            "sources": rag_result["sources"],
            "chunks_count": rag_result["chunks_count"],
            "detected_topic": rag_result["detected_topic"],
        }


# Singleton instance
_rag_service_instance = None


def get_rag_service() -> RAGService:
    """
    Get singleton RAG service instance.

    Lazy loading - only initialized when first used.
    """
    global _rag_service_instance

    if _rag_service_instance is None:
        _rag_service_instance = RAGService()

    return _rag_service_instance
