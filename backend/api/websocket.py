"""WebSocket handler for real-time game updates."""
from typing import Dict, Set
import json
from fastapi import WebSocket, WebSocketDisconnect

from game.orchestrator import get_orchestrator


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # game_id -> {websockets}
    
    async def connect(self, websocket: WebSocket, game_id: str):
        """Connect a WebSocket to a game."""
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = set()
        self.active_connections[game_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, game_id: str):
        """Disconnect a WebSocket from a game."""
        if game_id in self.active_connections:
            self.active_connections[game_id].discard(websocket)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]
    
    async def send_game_update(self, game_id: str, data: dict):
        """Send game update to all connected clients for a game."""
        if game_id not in self.active_connections:
            return
        
        message = json.dumps(data)
        disconnected = set()
        
        for connection in self.active_connections[game_id]:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection, game_id)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket endpoint for game updates."""
    await manager.connect(websocket, game_id)
    
    orchestrator = get_orchestrator()
    
    try:
        # Send initial game state
        game_state = orchestrator.get_game(game_id)
        if game_state:
            await websocket.send_json({
                "type": "game_state",
                "data": game_state.to_dict()
            })
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            # Could handle client messages here if needed
            # For now, just keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)

