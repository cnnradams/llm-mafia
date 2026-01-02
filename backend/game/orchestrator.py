"""Game orchestrator for managing game execution."""
import asyncio
from typing import Dict, Optional, List

from game.state import GameState, Phase, Player
from game.actions import Action, NightAction
from game.phases import process_action, transition_to_night, transition_to_day, process_night_results
from llm.agent import LLMAgent
from llm.summarizer import summarize_day
from config import DEFAULT_MODEL


class GameOrchestrator:
    """Manages game execution and coordination."""
    
    def __init__(self):
        self.games: Dict[str, GameState] = {}
        self.llm_agents: Dict[str, Dict[str, LLMAgent]] = {}  # game_id -> {player_id: LLMAgent}
        self.pending_actions: Dict[str, Dict[str, Optional[Action]]] = {}  # game_id -> {player_id: action}
    
    def register_game(self, game_state: GameState, llm_agents: Optional[Dict[str, LLMAgent]] = None) -> None:
        """Register a game with the orchestrator."""
        self.games[game_state.game_id] = game_state
        self.llm_agents[game_state.game_id] = llm_agents or {}
        self.pending_actions[game_state.game_id] = {}
    
    def get_game(self, game_id: str) -> Optional[GameState]:
        """Get game state by ID."""
        return self.games.get(game_id)
    
    async def run_game_loop(self, game_id: str) -> None:
        """Run the game loop for a game."""
        game_state = self.games.get(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")
        
        if not game_state.is_started:
            game_state.is_started = True
        
        while not game_state.is_complete:
            if game_state.current_phase == Phase.DAY_DISCUSSION:
                await self.handle_discussion_phase(game_state)
            elif game_state.current_phase == Phase.DAY_VOTING:
                await self.handle_voting_phase(game_state)
            elif game_state.current_phase == Phase.NIGHT:
                await self.handle_night_phase(game_state)
            elif game_state.current_phase == Phase.GAME_END:
                break
            
            # Small delay to prevent tight loops
            await asyncio.sleep(0.1)
    
    async def handle_discussion_phase(self, game_state: GameState) -> None:
        """Handle discussion phase with round-robin."""
        alive_players = game_state.get_alive_players()
        if not alive_players:
            return
        
        current_speaker = game_state.get_current_speaker()
        if not current_speaker:
            return
        
        # Check if we already have an action for this player
        if current_speaker.player_id in self.pending_actions[game_state.game_id]:
            action = self.pending_actions[game_state.game_id][current_speaker.player_id]
            if action:
                success, message = process_action(game_state, action)
                if success:
                    # Clear the pending action
                    self.pending_actions[game_state.game_id][current_speaker.player_id] = None
                else:
                    # Invalid action, wait for new one
                    return
        
        # If human player, wait for action via API
        if current_speaker.is_human:
            # Don't advance, wait for human action
            return
        
        # LLM player - get action
        llm_agent = self.llm_agents[game_state.game_id].get(current_speaker.player_id)
        if llm_agent:
            day_summary = game_state.day_summaries.get(game_state.day - 1)
            action = await llm_agent.get_action(game_state, day_summary)
            success, message = process_action(game_state, action)
            if not success:
                # Fallback action
                action = await llm_agent.get_random_action(game_state)
                process_action(game_state, action)
        
        # Check if phase changed (e.g., to voting)
        if game_state.current_phase == Phase.DAY_VOTING:
            return
        
        # Check if we've completed a full round (all players have had a turn)
        # For now, continue until voting phase is triggered
        # Could add logic to limit discussion rounds
    
    async def handle_voting_phase(self, game_state: GameState) -> None:
        """Handle voting phase."""
        if not game_state.voting_state:
            return
        
        alive_players = game_state.get_alive_players()
        
        for player in alive_players:
            # Check if player has voted
            if player.player_id in game_state.voting_state.votes:
                continue
            
            # If human, wait for vote via API
            if player.is_human:
                continue
            
            # LLM player - get vote
            llm_agent = self.llm_agents[game_state.game_id].get(player.player_id)
            if llm_agent:
                day_summary = game_state.day_summaries.get(game_state.day - 1)
                action = await llm_agent.get_action(game_state, day_summary)
                success, message = process_action(game_state, action)
                if not success:
                    # Fallback: random vote
                    from game.actions import VoteAction
                    nominees = [game_state.voting_state.nominee1_id, game_state.voting_state.nominee2_id]
                    import random
                    vote_action = VoteAction(
                        player_id=player.player_id,
                        nominee_id=random.choice(nominees)
                    )
                    process_action(game_state, vote_action)
        
        # Check if voting is complete
        if game_state.voting_state and game_state.voting_state.is_complete(len(alive_players)):
            from game.voting import complete_voting
            eliminated_id = complete_voting(game_state)
            
            if eliminated_id:
                # Check win conditions
                winner = game_state.check_win_conditions()
                if winner:
                    game_state.winner = winner
                    game_state.current_phase = Phase.GAME_END
                    game_state.is_complete = True
                    return
                
                # Summarize the day
                await self.summarize_day(game_state)
                
                # Move to night
                transition_to_night(game_state)
    
    async def handle_night_phase(self, game_state: GameState) -> None:
        """Handle night phase."""
        from game.state import Role
        
        night_actions: Dict[str, NightAction] = {}
        
        # Collect actions from all players with night abilities
        for role_type in [Role.MAFIA, Role.DOCTOR, Role.DETECTIVE]:
            role_players = [p for p in game_state.get_alive_players() if p.role == role_type]
            
            for player in role_players:
                if player.is_human:
                    # Wait for human action
                    if player.player_id in self.pending_actions[game_state.game_id]:
                        action = self.pending_actions[game_state.game_id][player.player_id]
                        if isinstance(action, NightAction):
                            night_actions[player.player_id] = action
                            self.pending_actions[game_state.game_id][player.player_id] = None
                    continue
                
                # LLM player
                llm_agent = self.llm_agents[game_state.game_id].get(player.player_id)
                if llm_agent:
                    day_summary = game_state.day_summaries.get(game_state.day - 1)
                    action = await llm_agent.get_action(game_state, day_summary)
                    if isinstance(action, NightAction):
                        night_actions[player.player_id] = action
        
        # If we have all necessary actions, process night
        # For simplicity, process once we have at least the Mafia action
        mafia_alive = [p for p in game_state.get_alive_players() if p.role == Role.MAFIA]
        if mafia_alive:
            mafia_action_exists = any(p.player_id in night_actions for p in mafia_alive)
            
            if mafia_action_exists:
                # Process night results
                process_night_results(game_state, night_actions)
                
                # Check win conditions
                winner = game_state.check_win_conditions()
                if winner:
                    game_state.winner = winner
                    game_state.current_phase = Phase.GAME_END
                    game_state.is_complete = True
                    return
                
                # Move to next day
                transition_to_day(game_state)
    
    async def summarize_day(self, game_state: GameState) -> None:
        """Summarize the completed day."""
        summary = await summarize_day(game_state, game_state.day)
        game_state.day_summaries[game_state.day] = summary
    
    def submit_action(self, game_id: str, player_id: str, action: Action) -> tuple[bool, Optional[str]]:
        """Submit an action from a human player."""
        game_state = self.games.get(game_id)
        if not game_state:
            return False, "Game not found"
        
        # Validate action
        is_valid, error = action.validate(game_state)
        if not is_valid:
            return False, error
        
        # Store as pending
        if game_id not in self.pending_actions:
            self.pending_actions[game_id] = {}
        self.pending_actions[game_id][player_id] = action
        
        return True, None


# Global orchestrator instance
_orchestrator: Optional[GameOrchestrator] = None


def get_orchestrator() -> GameOrchestrator:
    """Get or create the global game orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = GameOrchestrator()
    return _orchestrator

