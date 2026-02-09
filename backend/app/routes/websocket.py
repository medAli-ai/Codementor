from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import json
import logging
import asyncio

from app.services.connection_manager import connection_manager
from app.services import chat_service
from app.db.session import get_db
from app.models import User
from app.core.security import decode_access_token

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time chat with database persistence.
    
    Requires JWT token in query parameter: ws://localhost:8000/api/ws/ws?token=<jwt_token>
    
    Client sends: {"conversation_id": 1, "message": "Hello", "temperature": 0.7}
    Server sends: {"type": "start"} → {"type": "chunk", "content": "..."} → {"type": "done", "conversation_id": 1, "message_id": 5}
    """
    
    # Verify token and get user
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    email = payload.get("sub")
    if not email:
        await websocket.close(code=1008, reason="Invalid token payload")
        return
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get user from database
        user = db.query(User).filter(User.email == email).first()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
        
        # Connect WebSocket
        await connection_manager.connect(websocket)
        logger.info(f"🔌 User {user.email} connected via WebSocket")
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                user_message = message_data.get("message", "")
                conversation_id = message_data.get("conversation_id")
                temperature = message_data.get("temperature", 0.7)
                
                logger.info(f"📨 User {user.email}: {user_message[:50]}...")
                
                # Send start signal
                await connection_manager.send_message(
                    {"type": "start"},
                    websocket
                )
                
                # Stream response and save to database
                stream_generator = chat_service.process_chat_message_stream(
                    user_message=user_message,
                    conversation_id=conversation_id,
                    user_id=user.id,
                    temperature=temperature,
                    db=db
                )
                
                final_conversation_id = None
                final_message_id = None
                
                async for item in stream_generator:
                    if item["type"] == "chunk":
                        # Send content chunk
                        await connection_manager.send_message(
                            {"type": "chunk", "content": item["content"]},
                            websocket
                        )
                        await asyncio.sleep(0.08)  # Visible streaming
                    
                    elif item["type"] == "done":
                        # Got final metadata
                        final_conversation_id = item["conversation_id"]
                        final_message_id = item["message_id"]
                
                # Send done signal with metadata
                await connection_manager.send_message(
                    {
                        "type": "done",
                        "conversation_id": final_conversation_id,
                        "message_id": final_message_id
                    },
                    websocket
                )
                
                logger.info(f"✅ WebSocket message complete (conversation: {final_conversation_id})")
                
        except WebSocketDisconnect:
            connection_manager.disconnect(websocket)
            logger.info(f"🔌 User {user.email} disconnected")
        
        except json.JSONDecodeError:
            await connection_manager.send_message(
                {"type": "error", "message": "Invalid JSON"},
                websocket
            )
        
        except Exception as e:
            logger.error(f"❌ WebSocket error: {e}")
            await connection_manager.send_message(
                {"type": "error", "message": "Internal server error"},
                websocket
            )
    
    finally:
        db.close()