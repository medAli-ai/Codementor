# backend/app/core/config.py

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ============ Application ============
    APP_NAME: str = "CodeMentor"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ============ Database ============
    DATABASE_URL: str
    
    # ============ JWT ============
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # ============ LLM (Ollama) ============
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"
    
    # ============ RAG - Qdrant ============
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = "http://localhost:6333"  # Constructed URL
    QDRANT_COLLECTION: str = "codementor_rag"
    QDRANT_USE_GRPC: bool = False
    
    # ============ RAG - Embeddings ============
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384
    EMBEDDING_DEVICE: str = "cpu"
    
    # ============ RAG - Retrieval ============
    RAG_TOP_K: int = 3
    RAG_SCORE_THRESHOLD: float = 0.7
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 50
    
    # ============ RAG - Directories ============
    RAG_DATA_DIR: str = "rag_data"
    RAG_BOOKS_DIR: str = "rag_data/books"
    RAG_PROCESSED_DIR: str = "rag_data/processed"
    RAG_COLLECTION_NAME: str = "codementor_rag"
    
    # ============ RAG - Redis ============
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # ============ RAG - Celery ============
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # ============ RAG - File Upload ============
    UPLOAD_DIR: str = "/tmp/codementor_uploads"
    MAX_UPLOAD_SIZE: int = 52428800  # 50MB
    
    # ============ Default Superadmin ============
    DEFAULT_SUPERADMIN_EMAIL: Optional[str] = None
    DEFAULT_SUPERADMIN_USERNAME: Optional[str] = None
    DEFAULT_SUPERADMIN_PASSWORD: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()