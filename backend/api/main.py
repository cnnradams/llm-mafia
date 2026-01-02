"""FastAPI application entry point."""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from api.routes import games
from api.websocket import websocket_endpoint, manager
from game.orchestrator import get_orchestrator
from game.state import Phase


app = FastAPI(title="Mafia LLM Game API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(games.router)


@app.websocket("/games/{game_id}/ws")
async def websocket_route(websocket: WebSocket, game_id: str):
    """WebSocket route for game updates."""
    await websocket_endpoint(websocket, game_id)


# Background task to broadcast game state updates
async def broadcast_updates():
    """Periodically broadcast game state updates to connected clients."""
    import asyncio
    orchestrator = get_orchestrator()
    
    while True:
        await asyncio.sleep(0.5)  # Update every 500ms
        
        for game_id, game_state in list(orchestrator.games.items()):
            if game_id in manager.active_connections:
                await manager.send_game_update(game_id, {
                    "type": "game_state",
                    "data": game_state.to_dict()
                })


@app.on_event("startup")
async def startup_event():
    """Startup event - start background tasks."""
    import asyncio
    asyncio.create_task(broadcast_updates())


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Mafia LLM Game API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

