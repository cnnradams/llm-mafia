"""Game state management."""
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import uuid

from .events import EventLog


class Role(Enum):
    """Player roles."""
    MAFIA = "MAFIA"
    VILLAGER = "VILLAGER"
    DETECTIVE = "DETECTIVE"
    DOCTOR = "DOCTOR"


class Team(Enum):
    """Player teams."""
    MAFIA_TEAM = "MAFIA_TEAM"
    TOWN_TEAM = "TOWN_TEAM"


class Phase(Enum):
    """Game phases - Town of Salem style."""
    NIGHT = "NIGHT"
    DAY_DISCUSSION = "DAY_DISCUSSION"  # Everyone discusses (2 rounds)
    DAY_NOMINATION = "DAY_NOMINATION"  # Everyone nominates someone
    DAY_DEFENSE = "DAY_DEFENSE"        # Defendant defends, others respond
    DAY_JUDGMENT = "DAY_JUDGMENT"      # Vote GUILTY/INNOCENT
    GAME_END = "GAME_END"
    
    # Legacy alias
    DAY_VOTING = "DAY_JUDGMENT"  # For backwards compatibility


@dataclass
class Player:
    """Represents a player in the game."""
    player_id: str
    name: str
    role: Role
    team: Team
    is_alive: bool = True
    is_human: bool = False
    model_name: Optional[str] = None  # For LLM players (OpenRouter model ID)
    model_label: Optional[str] = None  # Short label for CLI display (hidden from game)
    model_provider: Optional[str] = None  # Provider name for CLI display
    
    def to_dict(self, hide_role: bool = False) -> Dict:
        """Convert player to dictionary.
        
        Note: model_label and model_provider are intentionally NOT included
        in the dict output to keep them hidden from the game/prompts.
        """
        data = {
            "player_id": self.player_id,
            "name": self.name,
            "is_alive": self.is_alive,
            "is_human": self.is_human,
        }
        if not hide_role or self.is_human:
            data["role"] = self.role.value
            data["team"] = self.team.value
        # model_name is also excluded to prevent LLMs from knowing their identity
        return data


@dataclass
class TrialState:
    """State for Town of Salem style trial."""
    defendant_id: str
    defense_phase: str = "opening"  # "opening", "discussion", "closing", "done"
    current_speaker_idx: int = 0
    votes: Dict[str, bool] = field(default_factory=dict)  # player_id -> True=GUILTY, False=INNOCENT
    
    def is_voting_complete(self, alive_count: int) -> bool:
        """Check if all alive players (except defendant) have voted."""
        return len(self.votes) >= alive_count - 1  # Defendant doesn't vote
    
    def get_result(self) -> Optional[bool]:
        """Get verdict. True=GUILTY (execute), False=INNOCENT, None=tie."""
        if not self.votes:
            return None
        
        guilty = sum(1 for v in self.votes.values() if v)
        innocent = sum(1 for v in self.votes.values() if not v)
        
        if guilty > innocent:
            return True  # GUILTY - execute
        elif innocent > guilty:
            return False  # INNOCENT - acquit
        return None  # Tie - typically means innocent


@dataclass
class VotingState:
    """State for voting phase (legacy, kept for compatibility)."""
    nominee1_id: Optional[str] = None
    nominee2_id: Optional[str] = None
    votes: Dict[str, str] = field(default_factory=dict)  # player_id -> nominee_id
    
    def is_complete(self, alive_count: int) -> bool:
        """Check if all alive players have voted."""
        return len(self.votes) >= alive_count
    
    def get_result(self) -> Optional[str]:
        """Get the nominee with majority votes. Returns None if tie."""
        if not self.votes:
            return None
        
        votes1 = sum(1 for v in self.votes.values() if v == self.nominee1_id)
        votes2 = sum(1 for v in self.votes.values() if v == self.nominee2_id)
        
        if votes1 > votes2:
            return self.nominee1_id
        elif votes2 > votes1:
            return self.nominee2_id
        return None  # Tie


class GameState:
    """Manages the game state."""
    
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.players: Dict[str, Player] = {}
        self.current_phase: Phase = Phase.DAY_DISCUSSION
        self.day: int = 1
        self.current_speaker_idx: int = 0
        self.discussion_round: int = 0  # Track discussion rounds
        self.nominations: Dict[str, List[str]] = {}  # target_id -> [nominator_ids]
        self.who_nominated: Dict[str, str] = {}  # nominator_id -> target_id (each player nominates once)
        self.trial_state: Optional[TrialState] = None  # Town of Salem trial
        self.voting_state: Optional[VotingState] = None  # Legacy
        self.event_log: EventLog = EventLog()
        self.day_summaries: Dict[int, str] = {}  # day -> summary
        self.winner: Optional[Team] = None
        self.is_started: bool = False
        self.is_complete: bool = False
    
    def add_player(self, player: Player) -> None:
        """Add a player to the game."""
        self.players[player.player_id] = player
    
    def get_alive_players(self) -> List[Player]:
        """Get all alive players."""
        return [p for p in self.players.values() if p.is_alive]
    
    def get_alive_player_ids(self) -> List[str]:
        """Get IDs of all alive players."""
        return [p.player_id for p in self.get_alive_players()]
    
    def get_players_by_role(self, role: Role) -> List[Player]:
        """Get all players with a specific role."""
        return [p for p in self.players.values() if p.role == role and p.is_alive]
    
    def get_players_by_team(self, team: Team) -> List[Player]:
        """Get all players on a specific team."""
        return [p for p in self.players.values() if p.team == team and p.is_alive]
    
    def get_current_speaker(self) -> Optional[Player]:
        """Get the current speaker in round-robin."""
        alive_players = self.get_alive_players()
        if not alive_players:
            return None
        idx = self.current_speaker_idx % len(alive_players)
        return alive_players[idx]
    
    def advance_speaker(self) -> None:
        """Move to next speaker in round-robin."""
        self.current_speaker_idx += 1
    
    def reset_speaker_order(self) -> None:
        """Reset speaker order (for new day)."""
        self.current_speaker_idx = 0
    
    def add_nomination(self, nominator_id: str, target_id: str) -> None:
        """Add a nomination."""
        if target_id not in self.nominations:
            self.nominations[target_id] = []
        if nominator_id not in self.nominations[target_id]:
            self.nominations[target_id].append(nominator_id)
    
    def get_successful_nominations(self) -> List[str]:
        """Get list of player IDs who have been successfully nominated."""
        return [
            target_id for target_id, nominators in self.nominations.items()
            if len(nominators) >= 1 and target_id in self.get_alive_player_ids()
        ]
    
    def check_win_conditions(self) -> Optional[Team]:
        """Check if game has ended and return winner."""
        mafia_count = len(self.get_players_by_role(Role.MAFIA))
        town_count = len([p for p in self.get_alive_players() if p.team == Team.TOWN_TEAM])
        
        if mafia_count == 0:
            return Team.TOWN_TEAM
        elif mafia_count >= town_count:
            return Team.MAFIA_TEAM
        
        return None
    
    def to_dict(self, player_id: Optional[str] = None) -> Dict:
        """Convert game state to dictionary for API response."""
        # Determine if we should hide role info
        hide_role = False
        if player_id:
            player = self.players.get(player_id)
            hide_role = not player or not player.is_human
        
        return {
            "game_id": self.game_id,
            "phase": self.current_phase.value,
            "day": self.day,
            "players": [p.to_dict(hide_role=hide_role) for p in self.players.values()],
            "current_speaker_id": self.get_current_speaker().player_id if self.get_current_speaker() else None,
            "nominations": {
                target_id: nominators
                for target_id, nominators in self.nominations.items()
                if target_id in self.get_alive_player_ids()
            },
            "voting_state": {
                "nominee1_id": self.voting_state.nominee1_id,
                "nominee2_id": self.voting_state.nominee2_id,
                "votes": self.voting_state.votes,
            } if self.voting_state else None,
            "winner": self.winner.value if self.winner else None,
            "is_complete": self.is_complete,
            "day_summary": self.day_summaries.get(self.day - 1),  # Previous day's summary
        }

