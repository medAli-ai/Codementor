from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    The @lru_cache on get_settings() ensures we only load config once.
    """
    # Application
    APP_NAME: str = "CodeMentor"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # LLM Configuration
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.3"


    # Database (NEW)
    DATABASE_URL: str
    
    # Security (NEW)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
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