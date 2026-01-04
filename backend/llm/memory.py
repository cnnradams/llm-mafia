"""Player memory system for LLM agents.

Each player maintains a simple working memory blob that gets updated after each phase.
This allows LLMs to track whatever they want in their own format.
"""
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class PlayerMemory:
    """Working memory for a single player - just a freeform text blob."""
    player_id: str
    
    # Single freeform memory text - LLM controls the format/content
    memory_text: str = ""
    
    def update_memory(self, new_memory: str):
        """Update the memory text."""
        self.memory_text = new_memory
    
    def to_prompt_section(self) -> str:
        """Generate prompt section from memory."""
        if not self.memory_text:
            return ""
        
        return f"## Your Working Memory\n\n{self.memory_text}"


class MemoryManager:
    """Manages memory for all players in a game."""
    
    def __init__(self):
        self.player_memories: Dict[str, PlayerMemory] = {}
    
    def get_memory(self, player_id: str) -> PlayerMemory:
        """Get or create memory for a player."""
        if player_id not in self.player_memories:
            self.player_memories[player_id] = PlayerMemory(player_id=player_id)
        return self.player_memories[player_id]
    
    def update_player_memory(self, player_id: str, new_memory: str):
        """Update a player's memory with new text."""
        memory = self.get_memory(player_id)
        memory.update_memory(new_memory)
    
    def clear(self):
        """Clear all memories (for new game)."""
        self.player_memories.clear()


# Prompt for LLM to update their memory
MEMORY_UPDATE_PROMPT = """
## Update Your Working Memory

**Your Identity:**
{identity}

Based on what just happened this phase, update your working memory.
Write whatever you want to remember - suspicions, facts, strategies, patterns, etc.
This is YOUR memory - organize it however you think is best.

Remember: Write from YOUR perspective based on YOUR role and what YOU know.

**Phase Events:**
{phase_events}

**Your Current Memory:**
{current_memory}

Respond with JSON containing your updated memory text:
```json
{{
    "memory": "Your updated memory text here - write whatever you want to remember"
}}
```

Keep it concise but include whatever information you think is important for winning the game.
"""

