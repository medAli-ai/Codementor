from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm import llm_service
from app.core.config import settings
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Basic chat endpoint (non-streaming).
    Returns complete response at once.
    """
    try:
        logger.info(f"📩 Received chat request: {request.message[:50]}...")
        
        messages = [{"role": "user", "content": request.message}]
        response_text = llm_service.chat(
            messages=messages,
            temperature=request.temperature
        )
        
        logger.info(f"✅ Generated response ({len(response_text)} chars)")
        
        return ChatResponse(
            response=response_text,
            model=settings.OLLAMA_MODEL
        )
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate response: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint.
    
    Returns response token-by-token using Server-Sent Events (SSE).
    
    Client receives chunks in real-time as they're generated.
    """
    async def generate():
        """Generator function that yields response chunks"""
        try:
            logger.info(f"🌊 Starting streaming chat: {request.message[:50]}...")
            
            messages = [{"role": "user", "content": request.message}]
            
            # Stream response chunks
            async for chunk in llm_service.chat_stream(
                messages=messages,
                temperature=request.temperature
            ):
                # Format as Server-Sent Event
                # Each chunk is sent as: data: {"content": "chunk"}\n\n
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # Send done signal
            yield f"data: {json.dumps({'done': True})}\n\n"
            
            logger.info("✅ Streaming complete")
            
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )