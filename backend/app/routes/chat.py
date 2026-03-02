from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio

from app.schemas.conversation import ChatRequest, ChatResponse, RAGSource
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.core.deps import get_current_active_user
from app.services import chat_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Chat endpoint (non-streaming) - saves messages to database.
    🆕 NEW: Includes RAG context from user's uploaded documents.
    
    Requires authentication.
    """
    try:
        # Call chat service (now returns RAG result too)
        conversation_id, message_id, response, rag_result = chat_service.process_chat_message(
            user_message=request.message,
            conversation_id=request.conversation_id,
            user_id=current_user.id,
            temperature=request.temperature,
            db=db
        )
        
        # Format RAG sources if available
        sources = None
        rag_used = False
        
        if rag_result:
            sources = [
                RAGSource(
                    title=src['title'],
                    document_id=src['document_id'],
                    score=src['score'],
                    page_numbers=src.get('page_numbers', [])
                )
                for src in rag_result['sources']
            ]
            rag_used = True
        
        return ChatResponse(
            conversation_id=conversation_id,
            message_id=message_id,
            response=response,
            model=settings.OLLAMA_MODEL,
            sources=sources,  # 🆕 NEW: RAG sources
            rag_used=rag_used  # 🆕 NEW: Whether RAG was used
        )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Streaming chat endpoint - saves messages to database.
    🆕 NEW: Includes RAG context from user's uploaded documents.
    
    Requires authentication.
    """
    async def generate():
        try:
            logger.info(f"🌊 User {current_user.email} streaming: {request.message[:50]}...")
            
            stream_generator = chat_service.process_chat_message_stream(
                user_message=request.message,
                conversation_id=request.conversation_id,
                user_id=current_user.id,
                temperature=request.temperature,
                db=db
            )
            
            async for item in stream_generator:
                if item["type"] == "chunk":
                    # Send content chunks
                    yield f"data: {json.dumps({'content': item['content']})}\n\n"
                    await asyncio.sleep(0.08)  # Visible streaming delay
                    
                elif item["type"] == "done":
                    # Got final metadata
                    conversation_id = item["conversation_id"]
                    message_id = item["message_id"]
                    rag_result = item.get("rag_result")  # 🆕 NEW: Get RAG metadata
                    
                    # Format RAG sources if available
                    sources = None
                    rag_used = False
                    
                    if rag_result:
                        sources = [
                            {
                                "title": src['title'],
                                "document_id": src['document_id'],
                                "score": src['score'],
                                "page_numbers": src.get('page_numbers', [])
                            }
                            for src in rag_result['sources']
                        ]
                        rag_used = True
                    
                    # Send done signal with metadata
                    yield f"data: {json.dumps({
                        'done': True,
                        'conversation_id': conversation_id,
                        'message_id': message_id,
                        'sources': sources,  # 🆕 NEW: RAG sources
                        'rag_used': rag_used  # 🆕 NEW: Whether RAG was used
                    })}\n\n"
                    
                    logger.info(f"✅ Streaming complete (conversation: {conversation_id}, RAG used: {rag_used})")
        
        except ValueError as e:
            logger.error(f"❌ Chat error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            yield f"data: {json.dumps({'error': 'Internal server error'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
