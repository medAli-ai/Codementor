from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    The @lru_cache on get_settings() ensures we only load config once.
    """
    # ========== Application ==========
    APP_NAME: str = "CodeMentor"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ========== LLM Configuration ==========
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.3"
    
    # ========== Database ==========
    DATABASE_URL: str
    
    # ========== Security ==========
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # ========== RAG Configuration ==========
    # Qdrant Vector Database
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "programming_books"
    QDRANT_USE_GRPC: bool = False
    
    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384
    EMBEDDING_DEVICE: str = "cpu"  # "cpu" or "cuda"
    
    # Retrieval
    RAG_TOP_K: int = 3              # How many chunks to retrieve
    RAG_SCORE_THRESHOLD: float = 0.7  # Minimum similarity score (0-1)
    
    # Chunking
    RAG_CHUNK_SIZE: int = 512       # Tokens per chunk
    RAG_CHUNK_OVERLAP: int = 50     # Overlap between chunks
    
    # Data Paths
    RAG_DATA_DIR: str = "rag_data"
    RAG_BOOKS_DIR: str = "rag_data/books"
    RAG_PROCESSED_DIR: str = "rag_data/processed"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    
    lru_cache ensures this is only called once, even if
    get_settings() is called multiple times.
    """
    return Settings()


# Export a singleton instance for convenience
settings = get_settings()