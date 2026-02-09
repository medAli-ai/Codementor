from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import logging
import json
import asyncio

from app.schemas.conversation import ChatRequest, ChatResponse
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
    Chat endpoint (non-streaming) - saves messages to database
    
    Requires authentication.
    """
    try:
        conversation_id, message_id, response = chat_service.process_chat_message(
            user_message=request.message,
            conversation_id=request.conversation_id,
            user_id=current_user.id,
            temperature=request.temperature,
            db=db
        )
        
        return ChatResponse(
            conversation_id=conversation_id,
            message_id=message_id,
            response=response,
            model=settings.OLLAMA_MODEL
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
    Streaming chat endpoint - saves messages to database
    
    Requires authentication.
    """
    async def generate():
        try:
            logger.info(f"🌊 User {current_user.email} streaming: {request.message[:50]}...")
            
            conversation_id = None
            message_id = None
            
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
                    
                    # Send done signal with metadata
                    yield f"data: {json.dumps({
                        'done': True,
                        'conversation_id': conversation_id,
                        'message_id': message_id
                    })}\n\n"
            
            logger.info(f"✅ Streaming complete (conversation: {conversation_id})")
            
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