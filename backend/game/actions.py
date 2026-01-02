"""Action system for player actions."""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field

from .state import GameState, Player, Phase


class ActionType(Enum):
    """Types of actions."""
    SPEAK = "SPEAK"
    NOMINATE = "NOMINATE"
    VOTE = "VOTE"
    PASS = "PASS"
    NIGHT_ACTION = "NIGHT_ACTION"


class NightActionType(Enum):
    """Types of night actions."""
    KILL = "KILL"
    SAVE = "SAVE"
    INVESTIGATE = "INVESTIGATE"


@dataclass
class Action(ABC):
    """Base class for all actions."""
    player_id: str
    action_type: ActionType = field(init=False)
    
    @abstractmethod
    def validate(self, game_state: GameState) -> tuple[bool, Optional[str]]:
        """Validate the action. Returns (is_valid, error_message)."""
        pass
    
    def to_dict(self) -> dict:
        """Convert action to dictionary."""
        result = {
            "player_id": self.player_id,
            "action_type": self.action_type.value,
        }
        if hasattr(self, 'message'):
            result['message'] = self.message
        if hasattr(self, 'target_id'):
            result['target_id'] = self.target_id
        if hasattr(self, 'night_action_type'):
            result['night_action_type'] = self.night_action_type.value if hasattr(self.night_action_type, 'value') else str(self.night_action_type)
        return result


@dataclass
class SpeakAction(Action):
    """Player speaks during discussion."""
    message: str
    
    def __post_init__(self):
        self.action_type = ActionType.SPEAK
    
    def validate(self, game_state: GameState) -> tuple[bool, Optional[str]]:
        """Validate speak action."""
        if game_state.current_phase != Phase.DAY_DISCUSSION:
            return False, "Can only speak during discussion phase"
        
        player = game_state.players.get(self.player_id)
        if not player:
            return False, "Player not found"
        
        if not player.is_alive:
            return False, "Dead players cannot speak"
        
        current_speaker = game_state.get_current_speaker()
        if not current_speaker or current_speaker.player_id != self.player_id:
            return False, "Not your turn to speak"
        
        if not self.message or not self.message.strip():
            return False, "Message cannot be empty"
        
        return True, None


@dataclass
class NominateAction(Action):
    """Player nominates another player."""
    target_id: str
    
    def __post_init__(self):
        self.action_type = ActionType.NOMINATE
    
    def validate(self, game_state: GameState) -> tuple[bool, Optional[str]]:
        """Validate nominate action."""
        if game_state.current_phase != Phase.DAY_DISCUSSION:
            return False, "Can only nominate during discussion phase"
        
        player = game_state.players.get(self.player_id)
        if not player:
            return False, "Player not found"
        
        if not player.is_alive:
            return False, "Dead players cannot nominate"
        
        current_speaker = game_state.get_current_speaker()
        if not current_speaker or current_speaker.player_id != self.player_id:
            return False, "Not your turn to nominate"
        
        target = game_state.players.get(self.target_id)
        if not target:
            return False, "Target player not found"
        
        if not target.is_alive:
            return False, "Cannot nominate dead players"
        
        if self.player_id == self.target_id:
            return False, "Cannot nominate yourself"
        
        # Check if already nominated (can re-nominate)
        # No restriction on re-nomination
        
        return True, None


@dataclass
class VoteAction(Action):
    """Player votes for a nominee."""
    nominee_id: str
    
    def __post_init__(self):
        self.action_type = ActionType.VOTE
    
    def validate(self, game_state: GameState) -> tuple[bool, Optional[str]]:
        """Validate vote action."""
        if game_state.current_phase != Phase.DAY_VOTING:
            return False, "Can only vote during voting phase"
        
        player = game_state.players.get(self.player_id)
        if not player:
            return False, "Player not found"
        
        if not player.is_alive:
            return False, "Dead players cannot vote"
        
        if not game_state.voting_state:
            return False, "No voting in progress"
        
        if self.nominee_id not in [game_state.voting_state.nominee1_id, game_state.voting_state.nominee2_id]:
            return False, "Can only vote for one of the two nominees"
        
        if self.player_id in game_state.voting_state.votes:
            return False, "Already voted"
        
        return True, None


@dataclass
class PassAction(Action):
    """Player passes their turn."""
    
    def __post_init__(self):
        self.action_type = ActionType.PASS
    
    def validate(self, game_state: GameState) -> tuple[bool, Optional[str]]:
        """Validate pass action."""
        if game_state.current_phase != Phase.DAY_DISCUSSION:
            return False, "Can only pass during discussion phase"
        
        player = game_state.players.get(self.player_id)
        if not player:
            return False, "Player not found"
        
        if not player.is_alive:
            return False, "Dead players cannot pass"
        
        current_speaker = game_state.get_current_speaker()
        if not current_speaker or current_speaker.player_id != self.player_id:
            return False, "Not your turn to pass"
        
        return True, None


@dataclass
class NightAction(Action):
    """Night phase action (kill, save, investigate)."""
    night_action_type: NightActionType
    target_id: str
    
    def __post_init__(self):
        self.action_type = ActionType.NIGHT_ACTION
    
    def validate(self, game_state: GameState) -> tuple[bool, Optional[str]]:
        """Validate night action."""
        if game_state.current_phase != Phase.NIGHT:
            return False, "Can only perform night actions during night phase"
        
        player = game_state.players.get(self.player_id)
        if not player:
            return False, "Player not found"
        
        if not player.is_alive:
            return False, "Dead players cannot perform actions"
        
        target = game_state.players.get(self.target_id)
        if not target:
            return False, "Target player not found"
        
        if not target.is_alive:
            return False, "Cannot target dead players"
        
        if self.player_id == self.target_id:
            # Some roles might be able to target themselves (e.g., Doctor saving self)
            # But generally not allowed for most actions
            if self.night_action_type != NightActionType.SAVE:
                return False, "Cannot target yourself"
        
        # Role-specific validation
        if self.night_action_type == NightActionType.KILL:
            if player.role.value != "MAFIA":
                return False, "Only Mafia can kill"
        elif self.night_action_type == NightActionType.SAVE:
            if player.role.value != "DOCTOR":
                return False, "Only Doctor can save"
        elif self.night_action_type == NightActionType.INVESTIGATE:
            if player.role.value != "DETECTIVE":
                return False, "Only Detective can investigate"
        
        return True, None


def action_from_dict(data: dict) -> Action:
    """Create an action from a dictionary."""
    action_type = ActionType(data["action_type"])
    player_id = data["player_id"]
    
    if action_type == ActionType.SPEAK:
        return SpeakAction(player_id=player_id, message=data["message"])
    elif action_type == ActionType.NOMINATE:
        return NominateAction(player_id=player_id, target_id=data["target_id"])
    elif action_type == ActionType.VOTE:
        return VoteAction(player_id=player_id, nominee_id=data["nominee_id"])
    elif action_type == ActionType.PASS:
        return PassAction(player_id=player_id)
    elif action_type == ActionType.NIGHT_ACTION:
        return NightAction(
            player_id=player_id,
            night_action_type=NightActionType(data["night_action_type"]),
            target_id=data["target_id"]
        )
    else:
        raise ValueError(f"Unknown action type: {action_type}")

