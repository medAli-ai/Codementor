from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import logging

from app.services.llm import llm_service
from app.services.connection_manager import connection_manager  # ← Import service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat.
    
    Now the route is THIN - just handles protocol!
    Business logic is in the service.
    """
    await connection_manager.connect(websocket)  # ← Use service
    
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            message = payload.get("message", "")
            temperature = payload.get("temperature", 0.7)
            
            if not message:
                await connection_manager.send_message({
                    "type": "error",
                    "content": "No message provided"
                }, websocket)
                continue
            
            logger.info(f"📩 Received: {message[:50]}...")
            
            # Send start signal
            await connection_manager.send_message({"type": "start"}, websocket)
            
            # Stream LLM response
            messages = [{"role": "user", "content": message}]
            
            async for chunk in llm_service.chat_stream(
                messages=messages,
                temperature=temperature
            ):
                await connection_manager.send_message({
                    "type": "chunk",
                    "content": chunk
                }, websocket)
            
            # Send done signal
            await connection_manager.send_message({"type": "done"}, websocket)

            await asyncio.sleep(0.50)
            
            logger.info("✅ Response sent")
            
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)
