import logging
from typing import List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and store WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.remove(websocket)
        logger.info(f"❌ Client disconnected. Total: {len(self.active_connections)}")

    async def send_message(self, message: dict, websocket: WebSocket):
        """Send JSON message to specific client"""
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        for connection in self.active_connections:
            await connection.send_json(message)


# Singleton instance
connection_manager = ConnectionManager()
