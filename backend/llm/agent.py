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
from llm.memory import PlayerMemory, build_memory_update_prompt, build_day_events_transcript
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
    
    async def update_memory_end_of_day(
        self,
        game_state: GameState,
        day: int,
    ) -> None:
        """Update the agent's memory at end of day with full day transcript.
        
        This is called once at the end of each day (after judgment, before night)
        with the complete transcript of events from night through judgment.
        """
        client = get_client()
        
        player = game_state.players.get(self.player_id)
        if not player or not player.is_alive:
            return  # Don't update memory for dead players
        
        current_memory = self.memory.memory_text or ""
        
        # Build complete day events transcript
        day_events = build_day_events_transcript(game_state, day)
        
        # Build comprehensive memory update prompt with full context
        prompt = build_memory_update_prompt(
            game_state=game_state,
            player=player,
            day_events=day_events,
            current_memory=current_memory,
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            # Get plain text response (not JSON)
            response = await client.chat_completion(
                self.model_name,
                messages,
                temperature=0.5,  # Lower temperature for memory updates
            )
            
            # Extract the text content
            new_memory = response["choices"][0]["message"]["content"]
            
            # Sanitize: remove control characters
            new_memory = ''.join(char for char in new_memory if ord(char) >= 32 or char in '\n\t')
            
            # Update memory
            self.memory.update_memory(new_memory.strip())
        
        except Exception as e:
            print(f"Error updating memory for {self.player_id}: {e}")
            # On error, keep the previous memory (don't clear it)
    
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

