"""Pydantic models for API requests and responses."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from game.state import Role, Team


class LLMModelConfig(BaseModel):
    """Configuration for an LLM player."""
    model_name: str
    persona: Optional[str] = None


class CreateGameRequest(BaseModel):
    """Request to create a new game."""
    player_count: Optional[int] = 8
    llm_models: List[LLMModelConfig]
    human_player_name: Optional[str] = None


class PlayerResponse(BaseModel):
    """Player information in API response."""
    player_id: str
    name: str
    role: Optional[str] = None
    team: Optional[str] = None
    is_alive: bool
    is_human: bool
    model_name: Optional[str] = None


class GameStateResponse(BaseModel):
    """Game state in API response."""
    game_id: str
    phase: str
    day: int
    players: List[PlayerResponse]
    current_speaker_id: Optional[str] = None
    nominations: Dict[str, List[str]]
    voting_state: Optional[Dict[str, Any]] = None
    winner: Optional[str] = None
    is_complete: bool
    day_summary: Optional[str] = None


class ActionRequest(BaseModel):
    """Request to submit an action."""
    player_id: str
    action_type: str
    message: Optional[str] = None
    target_id: Optional[str] = None
    nominee_id: Optional[str] = None
    night_action_type: Optional[str] = None


class ActionResponse(BaseModel):
    """Response after submitting an action."""
    success: bool
    message: Optional[str] = None


class EventResponse(BaseModel):
    """Event information."""
    type: str
    phase: str
    day: int
    player_id: Optional[str] = None
    target_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: str

