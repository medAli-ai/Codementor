from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

from app.core.config import settings
from app.routes import health, chat


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AI-powered coding tutor for exam preparation",
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc",  # ReDoc UI
)

# Add CORS middleware (allows frontend to communicate with backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React app (future)
        "http://localhost:8000",  # Same origin
        "http://127.0.0.1:8000",  # Alternative localhost
        "null"  # For file:// protocol (development only!)
    ],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.on_event("startup")
async def startup_event():
    """Runs when the application starts"""
    logger.info(f"🚀 Starting {settings.APP_NAME} v1.0.0")
    logger.info(f"📝 Debug mode: {settings.DEBUG}")
    logger.info(f"🤖 LLM model: {settings.OLLAMA_MODEL}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Runs when the application shuts down"""
    logger.info("👋 Shutting down...")

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - returns basic API info
    """
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs"
    }

# Include routers
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Simple test endpoint
@app.get("/api/test")
async def test():
    """
    Test endpoint to verify API is working
    """
    return {
        "message": "API is working!",
        "model": settings.OLLAMA_MODEL
    }