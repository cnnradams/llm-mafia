"""Phase management for game flow."""
from typing import Optional

from .state import GameState, Phase, Player, Role
from .actions import Action, NightAction, NightActionType
from .events import EventType
from .voting import check_should_transition_to_voting, initialize_voting, complete_voting


def process_action(game_state: GameState, action: Action) -> tuple[bool, Optional[str]]:
    """Process an action and update game state."""
    is_valid, error = action.validate(game_state)
    if not is_valid:
        return False, error
    
    if game_state.current_phase == Phase.DAY_DISCUSSION:
        return process_discussion_action(game_state, action)
    elif game_state.current_phase == Phase.DAY_VOTING:
        return process_voting_action(game_state, action)
    elif game_state.current_phase == Phase.NIGHT:
        return process_night_action(game_state, action)
    
    return False, "Invalid phase for action"


def process_discussion_action(game_state: GameState, action: Action) -> tuple[bool, Optional[str]]:
    """Process action during discussion phase."""
    from .actions import SpeakAction, NominateAction, PassAction
    
    if isinstance(action, SpeakAction):
        # Log speech
        game_state.event_log.add_event(
            EventType.SPEAK,
            game_state.current_phase.value,
            game_state.day,
            player_id=action.player_id,
            data={"message": action.message}
        )
        game_state.advance_speaker()
        return True, None
    
    elif isinstance(action, NominateAction):
        # Add nomination
        game_state.add_nomination(action.player_id, action.target_id)
        
        # Log nomination
        game_state.event_log.add_event(
            EventType.NOMINATE,
            game_state.current_phase.value,
            game_state.day,
            player_id=action.player_id,
            target_id=action.target_id,
        )
        
        # Check if we should transition to voting
        if check_should_transition_to_voting(game_state):
            initialize_voting(game_state)
            return True, "Voting phase initiated"
        
        game_state.advance_speaker()
        return True, None
    
    elif isinstance(action, PassAction):
        game_state.advance_speaker()
        return True, None
    
    return False, "Invalid action for discussion phase"


def process_voting_action(game_state: GameState, action: Action) -> tuple[bool, Optional[str]]:
    """Process action during voting phase."""
    from .actions import VoteAction
    from .voting import process_vote, complete_voting
    
    if isinstance(action, VoteAction):
        try:
            process_vote(game_state, action.player_id, action.nominee_id)
            
            # Check if voting is complete
            eliminated_id = complete_voting(game_state)
            
            if eliminated_id is not None:
                # Voting complete, check win conditions
                winner = game_state.check_win_conditions()
                if winner:
                    game_state.winner = winner
                    game_state.current_phase = Phase.GAME_END
                    game_state.is_complete = True
                    return True, f"Game over! {winner.value} wins!"
                
                # Move to night phase
                transition_to_night(game_state)
                return True, f"Player {eliminated_id} eliminated. Moving to night phase."
            
            return True, None
            
        except ValueError as e:
            return False, str(e)
    
    return False, "Invalid action for voting phase"


def process_night_action(game_state: GameState, action: Action) -> tuple[bool, Optional[str]]:
    """Process night phase action."""
    if not isinstance(action, NightAction):
        return False, "Invalid action for night phase"
    
    # Store night actions and process them all at once at end of night
    # For now, process immediately
    
    if action.night_action_type == NightActionType.KILL:
        # Mafia kill - will be processed at end of night
        game_state.event_log.add_event(
            EventType.NIGHT_ACTION,
            game_state.current_phase.value,
            game_state.day,
            player_id=action.player_id,
            target_id=action.target_id,
            data={"action_type": "KILL"}
        )
        return True, None
    
    elif action.night_action_type == NightActionType.SAVE:
        # Doctor save
        game_state.event_log.add_event(
            EventType.NIGHT_ACTION,
            game_state.current_phase.value,
            game_state.day,
            player_id=action.player_id,
            target_id=action.target_id,
            data={"action_type": "SAVE"}
        )
        return True, None
    
    elif action.night_action_type == NightActionType.INVESTIGATE:
        # Detective investigate (will return role info to detective)
        target = game_state.players[action.target_id]
        game_state.event_log.add_event(
            EventType.NIGHT_ACTION,
            game_state.current_phase.value,
            game_state.day,
            player_id=action.player_id,
            target_id=action.target_id,
            data={
                "action_type": "INVESTIGATE",
                "result": target.role.value
            }
        )
        return True, None
    
    return False, "Unknown night action type"


def transition_to_night(game_state: GameState) -> None:
    """Transition from day to night phase."""
    game_state.current_phase = Phase.NIGHT
    
    game_state.event_log.add_event(
        EventType.PHASE_CHANGE,
        game_state.current_phase.value,
        game_state.day,
    )


def transition_to_day(game_state: GameState) -> None:
    """Transition from night to day phase."""
    game_state.day += 1
    game_state.current_phase = Phase.DAY_DISCUSSION
    game_state.reset_speaker_order()
    game_state.nominations = {}
    
    game_state.event_log.add_event(
        EventType.PHASE_CHANGE,
        game_state.current_phase.value,
        game_state.day,
    )


def process_night_results(game_state: GameState, night_actions: dict) -> None:
    """Process all night actions and determine results."""
    # night_actions: {player_id: NightAction}
    
    kill_target_id = None
    save_target_id = None
    
    # Collect night actions
    for player_id, action in night_actions.items():
        if action.night_action_type == NightActionType.KILL:
            kill_target_id = action.target_id
        elif action.night_action_type == NightActionType.SAVE:
            save_target_id = action.target_id
    
    # Process kill (unless saved)
    if kill_target_id and kill_target_id != save_target_id:
        killed_player = game_state.players[kill_target_id]
        killed_player.is_alive = False
        
        game_state.event_log.add_event(
            EventType.KILL,
            game_state.current_phase.value,
            game_state.day,
            target_id=kill_target_id,
            data={
                "role": killed_player.role.value,
                "team": killed_player.team.value,
            }
        )
    
    # Check win conditions
    winner = game_state.check_win_conditions()
    if winner:
        game_state.winner = winner
        game_state.current_phase = Phase.GAME_END
        game_state.is_complete = True
        return
    
    # Move to next day
    transition_to_day(game_state)

