from fastapi import APIRouter

from app.core.config import settings
from app.services.llm import llm_service

router = APIRouter()


@router.get("/")
async def health_check():
    """
    Basic health check endpoint.

    Returns:
        Simple status message indicating API is running
    """
    return {"status": "healthy", "app": settings.APP_NAME, "version": "1.0.0"}


@router.get("/llm")
async def llm_health():
    """
    Check LLM service status.

    Returns:
        Status of Ollama connection and model information
    """
    is_healthy = llm_service.health_check()

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "model": settings.OLLAMA_MODEL,
        "host": settings.OLLAMA_HOST,
        "service": "ollama",
    }
