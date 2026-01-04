"""LLM agent player."""
import random
from typing import Optional, Dict, Any, List

from game.state import GameState
from game.actions import (
    Action, SpeakAction, NominateAction, VoteAction, PassAction, NightAction,
    NightActionType, JudgmentVoteAction, action_from_dict
)
from llm.openrouter_client import get_client
from llm.prompts import build_prompt_for_player
from llm.memory import PlayerMemory, MEMORY_UPDATE_PROMPT
from config import DEFAULT_MODEL


class LLMAgent:
    """Represents an LLM player."""
    
    def __init__(self, player_id: str, model_name: str, persona: Optional[str] = None):
        self.player_id = player_id
        self.model_name = model_name
        self.persona = persona
        self.memory = PlayerMemory(player_id=player_id)
    
    async def get_action(
        self,
        game_state: GameState,
        day_summary: Optional[str] = None,
    ) -> Action:
        """Get an action from the LLM agent."""
        client = get_client()
        
        # Build prompt
        prompt = build_prompt_for_player(game_state, self.player_id, day_summary)
        
        # Add persona if provided
        if self.persona:
            prompt = f"## Your Persona\n{self.persona}\n\n{prompt}"
        
        # Add memory section at the end
        memory_section = self.memory.to_prompt_section()
        if memory_section:
            prompt = f"{prompt}\n\n{memory_section}"
        
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            # Get JSON response
            response_data = await client.get_json_response(
                self.model_name,
                messages,
                temperature=0.8,
            )
            
            # Convert to action
            response_data["player_id"] = self.player_id
            action = action_from_dict(response_data)
            
            # Validate action
            is_valid, error = action.validate(game_state)
            if is_valid:
                return action
            else:
                # If invalid, fallback to pass
                print(f"Invalid action from LLM: {error}, falling back to pass")
                return PassAction(player_id=self.player_id)
        
        except Exception as e:
            print(f"Error getting action from LLM: {e}, falling back to pass")
            return PassAction(player_id=self.player_id)
    
    async def update_memory(
        self,
        game_state: GameState,
        phase_events: str,
    ) -> None:
        """Update the agent's memory after a phase completes."""
        client = get_client()
        
        player = game_state.players[self.player_id]
        current_memory = self.memory.memory_text or "No previous memory."
        
        # Include player identity context in memory update
        identity_context = f"You are {player.name} ({self.player_id}), Role: {player.role.value}, Team: {player.team.value}"
        
        prompt = MEMORY_UPDATE_PROMPT.format(
            identity=identity_context,
            phase_events=phase_events,
            current_memory=current_memory,
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response_data = await client.get_json_response(
                self.model_name,
                messages,
                temperature=0.5,  # Lower temperature for memory updates
            )
            
            # Update memory from response
            if "memory" in response_data:
                self.memory.update_memory(response_data["memory"])
        
        except Exception as e:
            print(f"Error updating memory for {self.player_id}: {e}")
    
    async def get_random_action(self, game_state: GameState) -> Action:
        """Get a random valid action (fallback)."""
        from game.state import Phase
        
        alive_players = game_state.get_alive_players()
        alive_ids = [p.player_id for p in alive_players if p.player_id != self.player_id]
        
        if game_state.current_phase == Phase.DAY_DISCUSSION:
            actions = [PassAction(player_id=self.player_id)]
            if alive_ids:
                actions.append(NominateAction(
                    player_id=self.player_id,
                    target_id=random.choice(alive_ids)
                ))
            actions.append(SpeakAction(
                player_id=self.player_id,
                message="I'm thinking..."
            ))
            return random.choice(actions)
        elif game_state.current_phase == Phase.DAY_VOTING:
            if game_state.voting_state and alive_ids:
                nominees = [game_state.voting_state.nominee1_id, game_state.voting_state.nominee2_id]
                return VoteAction(
                    player_id=self.player_id,
                    nominee_id=random.choice(nominees)
                )
        elif game_state.current_phase == Phase.NIGHT:
            if alive_ids:
                return NightAction(
                    player_id=self.player_id,
                    night_action_type=NightActionType.KILL,
                    target_id=random.choice(alive_ids)
                )
        
        return PassAction(player_id=self.player_id)

