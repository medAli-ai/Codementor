import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.middleware.timing import add_process_time_header
from app.routes import admin, auth, chat, conversations, health, rag, websocket
from app.services.rag.retriever import get_retriever

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info(f"🚀 Starting {settings.APP_NAME} v1.0.0")
    logger.info(f"📝 Debug mode: {settings.DEBUG}")
    logger.info(f"🤖 LLM model: {settings.OLLAMA_MODEL}")
    get_retriever()
    logger.info("🔍 Retriever initialized")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("👋 Shutting down...")
    retriever = get_retriever()
    await retriever.close()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AI-powered coding tutor for exam preparation",
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc",  # ReDoc UI
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Add CORS middleware (allows frontend to communicate with backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # React app (future)
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)
app.add_middleware(BaseHTTPMiddleware, dispatch=add_process_time_header)


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - returns basic API info
    """
    return {"app": settings.APP_NAME, "version": "1.0.0", "status": "running", "docs": "/api/docs"}


# Include routers
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(rag.router, prefix="/api")


@app.get("/api/test")
async def test():
    """
    Test endpoint to verify API is working
    """
    return {"message": "API is working!", "model": settings.OLLAMA_MODEL}
