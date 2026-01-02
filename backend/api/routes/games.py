"""Game API routes."""
import uuid
import random
import asyncio
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from game.state import GameState, Player, Role, Team
from game.orchestrator import get_orchestrator
from game.actions import action_from_dict
from api.models import (
    CreateGameRequest, GameStateResponse, PlayerResponse,
    ActionRequest, ActionResponse, EventResponse
)
from llm.agent import LLMAgent


router = APIRouter(prefix="/games", tags=["games"])


def assign_roles(player_count: int) -> Dict[int, Role]:
    """Assign roles to players based on player count."""
    roles = []
    
    # Default distribution for 8 players
    if player_count == 8:
        roles = [Role.MAFIA] * 2 + [Role.DETECTIVE] + [Role.DOCTOR] + [Role.VILLAGER] * 4
    elif player_count < 6:
        # Smaller game: 1 Mafia, 1 Detective, rest Villagers
        roles = [Role.MAFIA] + [Role.DETECTIVE] + [Role.VILLAGER] * (player_count - 2)
    else:
        # Larger game: scale up
        mafia_count = max(2, player_count // 4)
        roles = [Role.MAFIA] * mafia_count + [Role.DETECTIVE] + [Role.DOCTOR] + [Role.VILLAGER] * (player_count - mafia_count - 2)
    
    random.shuffle(roles)
    return roles


def get_team_for_role(role: Role) -> Team:
    """Get team for a role."""
    if role == Role.MAFIA:
        return Team.MAFIA_TEAM
    return Team.TOWN_TEAM


@router.post("", response_model=Dict)
async def create_game(request: CreateGameRequest):
    """Create a new game."""
    orchestrator = get_orchestrator()
    
    # Generate game ID
    game_id = str(uuid.uuid4())
    
    # Assign roles
    roles = assign_roles(request.player_count)
    
    # Create game state
    game_state = GameState(game_id=game_id)
    
    # Create LLM agents
    llm_agents: Dict[str, LLMAgent] = {}
    llm_model_index = 0
    
    players_response = []
    
    # Create players
    for i in range(request.player_count):
        player_id = str(uuid.uuid4())
        role = roles[i]
        team = get_team_for_role(role)
        
        is_human = False
        model_name = None
        name = f"Player {i+1}"
        
        if i == 0 and request.human_player_name:
            # First player is human
            is_human = True
            name = request.human_player_name
        elif llm_model_index < len(request.llm_models):
            # LLM player
            model_config = request.llm_models[llm_model_index % len(request.llm_models)]
            model_name = model_config.model_name
            name = f"{model_config.model_name.split('/')[-1]} {llm_model_index + 1}"
            
            llm_agent = LLMAgent(
                player_id=player_id,
                model_name=model_config.model_name,
                persona=model_config.persona
            )
            llm_agents[player_id] = llm_agent
            llm_model_index += 1
        else:
            # Default to first LLM model if not enough specified
            model_config = request.llm_models[0]
            model_name = model_config.model_name
            name = f"{model_config.model_name.split('/')[-1]} {llm_model_index + 1}"
            
            llm_agent = LLMAgent(
                player_id=player_id,
                model_name=model_config.model_name,
            )
            llm_agents[player_id] = llm_agent
            llm_model_index += 1
        
        player = Player(
            player_id=player_id,
            name=name,
            role=role,
            team=team,
            is_alive=True,
            is_human=is_human,
            model_name=model_name,
        )
        
        game_state.add_player(player)
        
        players_response.append({
            "player_id": player_id,
            "name": name,
            "role": role.value,
            "is_human": is_human,
        })
    
    # Register game with orchestrator
    orchestrator.register_game(game_state, llm_agents)
    
    return {
        "game_id": game_id,
        "players": players_response,
    }


@router.get("/{game_id}", response_model=GameStateResponse)
async def get_game_state(game_id: str, player_id: Optional[str] = None):
    """Get current game state."""
    orchestrator = get_orchestrator()
    game_state = orchestrator.get_game(game_id)
    
    if not game_state:
        raise HTTPException(status_code=404, detail="Game not found")
    
    state_dict = game_state.to_dict(player_id=player_id)
    return GameStateResponse(**state_dict)


@router.post("/{game_id}/start")
async def start_game(game_id: str, background_tasks: BackgroundTasks):
    """Start the game."""
    orchestrator = get_orchestrator()
    game_state = orchestrator.get_game(game_id)
    
    if not game_state:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if game_state.is_started:
        raise HTTPException(status_code=400, detail="Game already started")
    
    # Start game loop in background
    background_tasks.add_task(orchestrator.run_game_loop, game_id)
    
    return {"message": "Game started"}


@router.post("/{game_id}/actions", response_model=ActionResponse)
async def submit_action(game_id: str, request: ActionRequest):
    """Submit an action from a human player."""
    orchestrator = get_orchestrator()
    game_state = orchestrator.get_game(game_id)
    
    if not game_state:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Convert request to action
    action_dict = {
        "player_id": request.player_id,
        "action_type": request.action_type,
    }
    
    if request.message:
        action_dict["message"] = request.message
    if request.target_id:
        action_dict["target_id"] = request.target_id
    if request.nominee_id:
        action_dict["nominee_id"] = request.nominee_id
    if request.night_action_type:
        action_dict["night_action_type"] = request.night_action_type
    
    try:
        action = action_from_dict(action_dict)
    except Exception as e:
        return ActionResponse(success=False, message=str(e))
    
    # Submit action
    success, message = orchestrator.submit_action(game_id, request.player_id, action)
    
    return ActionResponse(success=success, message=message)


@router.get("/{game_id}/events", response_model=List[EventResponse])
async def get_events(game_id: str):
    """Get event log for a game."""
    orchestrator = get_orchestrator()
    game_state = orchestrator.get_game(game_id)
    
    if not game_state:
        raise HTTPException(status_code=404, detail="Game not found")
    
    events = game_state.event_log.to_list()
    return [EventResponse(**e) for e in events]


@router.post("/{game_id}/join")
async def join_game(game_id: str, player_name: str):
    """Join a game as a human player (if not full)."""
    orchestrator = get_orchestrator()
    game_state = orchestrator.get_game(game_id)
    
    if not game_state:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if game_state.is_started:
        raise HTTPException(status_code=400, detail="Game already started")
    
    # Find first available slot (non-human player)
    for player in game_state.players.values():
        if not player.is_human:
            # Replace with human
            player.is_human = True
            player.name = player_name
            player.model_name = None
            return {
                "player_id": player.player_id,
                "name": player_name,
                "role": player.role.value,
            }
    
    raise HTTPException(status_code=400, detail="Game is full")

