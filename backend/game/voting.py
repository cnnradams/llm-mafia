"""Two-nomination voting system."""
from typing import List, Optional

from .state import GameState, VotingState, Phase
from .events import EventType, EventLog


def check_should_transition_to_voting(game_state: GameState) -> bool:
    """Check if we should transition to voting phase (when 2 successful nominations exist)."""
    successful_nominations = game_state.get_successful_nominations()
    return len(successful_nominations) >= 2


def initialize_voting(game_state: GameState) -> VotingState:
    """Initialize voting phase with two nominees."""
    successful_nominations = game_state.get_successful_nominations()
    
    if len(successful_nominations) < 2:
        raise ValueError("Need at least 2 successful nominations to start voting")
    
    # Take first two successful nominations
    nominee1_id = successful_nominations[0]
    nominee2_id = successful_nominations[1]
    
    voting_state = VotingState(
        nominee1_id=nominee1_id,
        nominee2_id=nominee2_id,
    )
    
    game_state.voting_state = voting_state
    game_state.current_phase = Phase.DAY_VOTING
    
    # Log voting phase start
    game_state.event_log.add_event(
        EventType.PHASE_CHANGE,
        game_state.current_phase.value,
        game_state.day,
        data={
            "nominee1_id": nominee1_id,
            "nominee2_id": nominee2_id,
        }
    )
    
    return voting_state


def process_vote(game_state: GameState, voter_id: str, nominee_id: str) -> None:
    """Process a vote."""
    if not game_state.voting_state:
        raise ValueError("No voting in progress")
    
    if voter_id in game_state.voting_state.votes:
        raise ValueError("Player has already voted")
    
    if nominee_id not in [game_state.voting_state.nominee1_id, game_state.voting_state.nominee2_id]:
        raise ValueError("Invalid nominee")
    
    game_state.voting_state.votes[voter_id] = nominee_id
    
    # Log vote
    game_state.event_log.add_event(
        EventType.VOTE,
        game_state.current_phase.value,
        game_state.day,
        player_id=voter_id,
        target_id=nominee_id,
    )


def complete_voting(game_state: GameState) -> Optional[str]:
    """Complete voting and return eliminated player ID, or None if tie."""
    if not game_state.voting_state:
        raise ValueError("No voting in progress")
    
    alive_count = len(game_state.get_alive_players())
    
    if not game_state.voting_state.is_complete(alive_count):
        # Not all players have voted yet
        return None
    
    eliminated_id = game_state.voting_state.get_result()
    
    if eliminated_id:
        # Eliminate the player
        eliminated = game_state.players[eliminated_id]
        eliminated.is_alive = False
        
        # Log elimination
        game_state.event_log.add_event(
            EventType.ELIMINATE,
            game_state.current_phase.value,
            game_state.day,
            player_id=eliminated_id,
            data={
                "role": eliminated.role.value,
                "team": eliminated.team.value,
            }
        )
        
        # Clear voting state
        game_state.voting_state = None
        game_state.nominations = {}
        game_state.reset_speaker_order()
        
        return eliminated_id
    else:
        # Tie - handle tie (for now, no elimination, move to next phase)
        # Could implement tie-breaker logic here
        game_state.voting_state = None
        game_state.nominations = {}
        game_state.reset_speaker_order()
        return None

