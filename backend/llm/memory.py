"""Player memory system for LLM agents.

Each player maintains a working memory blob that gets updated at the end of each day.
This allows LLMs to summarize the full day's events into persistent memory.
"""
from typing import Dict, Optional, List
from dataclasses import dataclass

from game.state import GameState, Player, Role, Phase
from game.events import EventLog, EventType, GameEvent


@dataclass
class PlayerMemory:
    """Working memory for a single player - a freeform text blob."""
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


# Game rules context (same as in prompts.py for consistency)
GAME_RULES_BRIEF = """
Mafia is a social deduction game between two teams:
- **Town** (Villagers, Detective, Doctor): Win by eliminating all Mafia
- **Mafia**: Win when they equal or outnumber Town

**Roles:**
- Villager: No special ability. Use logic and discussion to find Mafia.
- Detective: Each night, investigate one player to learn if they are Mafia.
- Doctor: Each night, choose one player to protect from being killed.
- Mafia: Know each other. Each night, choose one Town player to kill.

**Game Flow:** Night (kills/protects/investigates) → Discussion → Nomination → Trial → Judgment → Night...
"""


def build_memory_update_prompt(
    game_state: GameState,
    player: Player,
    day_events: str,
    current_memory: str,
) -> str:
    """Build a comprehensive memory update prompt with full context."""
    
    parts = []
    
    # ===== SYSTEM CONTEXT =====
    parts.append("# Mafia Game - Memory Update")
    parts.append(GAME_RULES_BRIEF)
    
    # ===== PLAYER IDENTITY =====
    parts.append("\n## Your Identity")
    parts.append(f"- **Name**: {player.name}")
    parts.append(f"- **ID**: `{player.player_id}`")
    parts.append(f"- **Role**: {player.role.value}")
    parts.append(f"- **Team**: {player.team.value}")
    
    # Role-specific knowledge
    if player.role == Role.MAFIA:
        mafia_players = game_state.get_players_by_role(Role.MAFIA)
        mafia_names = [f"{p.name} (`{p.player_id}`)" for p in mafia_players]
        parts.append(f"\n**Mafia teammates**: {', '.join(mafia_names)}")
    elif player.role == Role.DETECTIVE:
        # Include investigation results
        night_events = game_state.event_log.get_events_by_type(EventType.NIGHT_ACTION)
        investigations = []
        for event in night_events:
            if event.player_id == player.player_id and event.data.get("action_type") == "INVESTIGATE":
                target = game_state.players.get(event.target_id)
                result = event.data.get("result", "UNKNOWN")
                if target:
                    investigations.append(f"Night {event.day}: {target.name} is **{result}**")
        if investigations:
            parts.append("\n**Your investigation results:**")
            for inv in investigations:
                parts.append(f"- {inv}")
    
    # ===== GAME STATE SUMMARY =====
    parts.append("\n## Current Game State")
    parts.append(f"- **Day**: {game_state.day}")
    
    alive = game_state.get_alive_players()
    dead = [p for p in game_state.players.values() if not p.is_alive]
    
    parts.append(f"- **Alive** ({len(alive)}): {', '.join(p.name for p in alive)}")
    if dead:
        dead_info = [f"{p.name} (was {p.role.value})" for p in dead]
        parts.append(f"- **Dead** ({len(dead)}): {', '.join(dead_info)}")
    
    # ===== FULL DAY EVENTS =====
    parts.append("\n## Complete Day Events (Night through Judgment)")
    parts.append("*This is the full transcript of everything that happened today. Summarize the key information into your memory.*\n")
    parts.append(day_events)
    
    # ===== CURRENT MEMORY =====
    parts.append("\n## Your Previous Memory")
    if current_memory and current_memory != "No previous memory.":
        parts.append(current_memory)
    else:
        parts.append("*(No previous memory - this is your first memory update)*")
    
    # ===== TASK INSTRUCTIONS =====
    parts.append("\n## Your Task: Update Your Working Memory")
    parts.append("""
Based on today's events, write your updated working memory. 

**This memory will be your ONLY persistent context across days** - you will NOT see previous days' discussions again. 
Include everything important: facts, suspicions, voting patterns, contradictions, your situation, and strategy.

Write from YOUR perspective as {role}. Organize it however you think is best for your future reference.

Respond with JSON:
```json
{{
    "memory": "Your complete updated memory here..."
}}
```
""".format(role=player.role.value))
    
    return "\n".join(parts)


def build_day_events_transcript(
    game_state: GameState,
    day: int,
) -> str:
    """Build a complete transcript of events for a day (night through judgment).
    
    Night N and Day N share the same day number, so all events for a full
    day cycle (Night → Discussion → Nomination → Trial → Judgment) are 
    logged with the same day value.
    
    Includes full messages with proper attribution showing speaker status/claims.
    """
    parts = []
    events = game_state.event_log.get_events_by_day(day)
    
    # Night and Day now share the same day number
    # Night N events and Day N events are both logged with day=N
    night_events = [e for e in events if e.phase == "NIGHT"]
    
    # ===== NIGHT RESULTS =====
    if night_events:
        parts.append("### Night Results")
        
        kills = [e for e in night_events if e.type == EventType.KILL]
        for kill in kills:
            victim = game_state.players.get(kill.target_id)
            if victim:
                role = kill.data.get("role", "UNKNOWN")
                parts.append(f"☠️ **{victim.name}** was killed by the Mafia (was {role})")
        
        if not kills:
            parts.append("Everyone survived the night.")
        parts.append("")
    
    # ===== DISCUSSION =====
    discussion_events = [e for e in events if e.phase == "DAY_DISCUSSION"]
    discussion_speeches = [e for e in discussion_events if e.type == EventType.SPEAK]
    
    if discussion_speeches:
        parts.append("### Discussion Phase")
        for i, speech in enumerate(discussion_speeches, 1):
            speaker = game_state.players.get(speech.player_id)
            if speaker:
                # Build attribution with context
                status = "alive" if speaker.is_alive else "dead"
                attribution = f"**{speaker.name}**"
                
                msg = speech.data.get('message', '')
                parts.append(f"{i}. {attribution}: \"{msg}\"")
                parts.append("")  # Blank line between speeches
    
    # ===== NOMINATIONS =====
    nomination_events = [e for e in events if e.phase == "DAY_NOMINATION"]
    nominations = [e for e in nomination_events if e.type == EventType.NOMINATE]
    
    if nominations:
        parts.append("### Nomination Phase")
        # Group by target
        nom_by_target: Dict[str, List[str]] = {}
        for nom in nominations:
            target_id = nom.target_id
            if target_id not in nom_by_target:
                nom_by_target[target_id] = []
            nominator = game_state.players.get(nom.player_id)
            if nominator:
                nom_by_target[target_id].append(nominator.name)
        
        parts.append("**Nominations:**")
        for target_id, nominators in sorted(nom_by_target.items(), key=lambda x: -len(x[1])):
            target = game_state.players.get(target_id)
            if target:
                parts.append(f"- {target.name}: {len(nominators)} votes ({', '.join(nominators)})")
        
        # Who went to trial
        if nom_by_target:
            most_nominated = max(nom_by_target.items(), key=lambda x: len(x[1]))
            defendant = game_state.players.get(most_nominated[0])
            if defendant:
                parts.append(f"\n**→ {defendant.name} went to trial**")
        parts.append("")
    
    # ===== DEFENSE/TRIAL =====
    defense_events = [e for e in events if e.phase == "DAY_DEFENSE"]
    defense_speeches = [e for e in defense_events if e.type == EventType.SPEAK]
    
    if defense_speeches:
        parts.append("### Trial Phase")
        for speech in defense_speeches:
            speaker = game_state.players.get(speech.player_id)
            if speaker:
                context = speech.data.get('context', '')
                msg = speech.data.get('message', '')
                
                # Add context label
                if context == "opening_defense":
                    label = f"**{speaker.name}** (DEFENDANT - opening)"
                elif context == "closing_defense":
                    label = f"**{speaker.name}** (DEFENDANT - closing)"
                elif context == "town_response":
                    label = f"**{speaker.name}**"
                else:
                    label = f"**{speaker.name}**"
                
                parts.append(f"{label}: \"{msg}\"")
                parts.append("")
    
    # ===== JUDGMENT =====
    judgment_events = [e for e in events if e.phase == "DAY_JUDGMENT"]
    eliminations = [e for e in judgment_events if e.type == EventType.ELIMINATE]
    
    if eliminations:
        parts.append("### Judgment Result")
        for elim in eliminations:
            defendant = game_state.players.get(elim.player_id)
            if defendant:
                role = elim.data.get("role", "UNKNOWN")
                parts.append(f"⚖️ **{defendant.name}** was **EXECUTED** (was {role})")
                
                # Show votes if available
                if "votes" in elim.data:
                    votes = elim.data["votes"]
                    guilty_voters = [game_state.players[pid].name for pid, vote in votes.items() if vote and pid in game_state.players]
                    innocent_voters = [game_state.players[pid].name for pid, vote in votes.items() if not vote and pid in game_state.players]
                    
                    if guilty_voters:
                        parts.append(f"  - **Guilty** ({len(guilty_voters)}): {', '.join(guilty_voters)}")
                    if innocent_voters:
                        parts.append(f"  - **Innocent** ({len(innocent_voters)}): {', '.join(innocent_voters)}")
    elif defense_speeches:  # Trial happened but no elimination = acquittal
        parts.append("### Judgment Result")
        parts.append("The defendant was **ACQUITTED** (not enough guilty votes)")
    
    if not parts:
        parts.append("*(No events recorded for this day)*")
    
    return "\n".join(parts)


# Keep old constant for backwards compatibility but it's no longer used
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
