"""Prompt generation for LLM players - Town of Salem style."""
from typing import List, Optional, Dict, Any

from game.state import GameState, Player, Phase, Role
from game.events import EventLog, EventType


GAME_RULES = """
## Game Rules (Town of Salem Style)

Mafia is a social deduction game between two teams:
- **Town** (Villagers, Detective, Doctor): Win by eliminating all Mafia
- **Mafia**: Win when they equal or outnumber Town

### Roles
- **Villager**: No special ability. Use logic and discussion to find Mafia.
- **Detective**: Each night, investigate one player to learn if they are Mafia.
- **Doctor**: Each night, choose one player to protect from being killed.
- **Mafia**: Know each other. Each night, choose one Town player to kill.

### Game Flow (Each Day)
1. **Night**: Mafia kills, Doctor protects, Detective investigates
2. **Discussion**: Everyone speaks (2 rounds) - share suspicions and theories
3. **Nomination**: Everyone nominates one suspect - most nominated goes to trial
4. **Defense**: Accused player defends themselves, others respond
5. **Judgment**: Vote GUILTY or INNOCENT - majority decides fate

### Strategy
- Town: Find inconsistencies, share info carefully, vote out suspects
- Mafia: Blend in, deflect suspicion, eliminate threats at night
- Don't reveal power roles too early - Mafia will target you!
"""


def build_prompt_for_player(
    game_state: GameState,
    player_id: str,
    day_summary: Optional[str] = None,
) -> str:
    """Build a prompt for an LLM player."""
    player = game_state.players[player_id]
    
    prompt_parts = []
    
    # System context
    prompt_parts.append("# Mafia Game - You are playing as an AI agent")
    prompt_parts.append(GAME_RULES)
    
    # Current game state
    prompt_parts.append(f"\n## Current State")
    prompt_parts.append(f"- Phase: {game_state.current_phase.value}")
    prompt_parts.append(f"- Day: {game_state.day}")
    
    # Player's role and knowledge
    prompt_parts.append(f"\n## Your Identity")
    prompt_parts.append(f"- **Name**: {player.name}")
    prompt_parts.append(f"- **ID**: `{player.player_id}`")
    prompt_parts.append(f"- **Role**: {player.role.value}")
    prompt_parts.append(f"- **Team**: {player.team.value}")
    
    # Role-specific knowledge
    prompt_parts.append(build_role_knowledge(game_state, player))
    
    # Player list with IDs
    prompt_parts.append(build_player_list(game_state))
    
    # Day summary (if available)
    if day_summary:
        prompt_parts.append(f"\n## Summary of Previous Day")
        prompt_parts.append(day_summary)
    
    # Event log
    events_summary = build_events_summary(game_state, game_state.day)
    if events_summary:
        prompt_parts.append(f"\n## Recent Events")
        prompt_parts.append(events_summary)
    
    # Current phase context and action format
    phase = game_state.current_phase
    
    if phase == Phase.NIGHT:
        prompt_parts.append(build_night_prompt(game_state, player))
    elif phase == Phase.DAY_DISCUSSION:
        prompt_parts.append(build_discussion_prompt(game_state, player))
    elif phase == Phase.DAY_NOMINATION:
        prompt_parts.append(build_nomination_prompt(game_state, player))
    elif phase == Phase.DAY_DEFENSE:
        prompt_parts.append(build_defense_prompt(game_state, player))
    elif phase == Phase.DAY_JUDGMENT:
        prompt_parts.append(build_judgment_prompt(game_state, player))
    
    return "\n".join(prompt_parts)


def build_role_knowledge(game_state: GameState, player: Player) -> str:
    """Build role-specific knowledge section."""
    parts = []
    
    if player.role == Role.MAFIA:
        mafia_players = game_state.get_players_by_role(Role.MAFIA)
        mafia_info = [f"{p.name} (`{p.player_id}`)" for p in mafia_players]
        parts.append(f"\n**Mafia teammates**: {', '.join(mafia_info)}")
        parts.append("Your goal: Eliminate Town without getting caught.")
    
    elif player.role == Role.DETECTIVE:
        parts.append("\n**Your ability**: Investigate one player each night.")
        # Add investigation results
        night_events = game_state.event_log.get_events_by_type(EventType.NIGHT_ACTION)
        for event in night_events:
            if event.player_id == player.player_id and event.data.get("action_type") == "INVESTIGATE":
                target = game_state.players.get(event.target_id)
                result = event.data.get("result", "UNKNOWN")
                if target:
                    parts.append(f"- Night {event.day}: {target.name} is **{result}**")
    
    elif player.role == Role.DOCTOR:
        parts.append("\n**Your ability**: Protect one player each night (including yourself).")
    
    elif player.role == Role.VILLAGER:
        parts.append("\n**Your role**: Use observation and logic to find Mafia!")
    
    return "\n".join(parts)


def build_player_list(game_state: GameState) -> str:
    """Build player list with IDs."""
    parts = ["\n## Players"]
    
    alive = game_state.get_alive_players()
    dead = [p for p in game_state.players.values() if not p.is_alive]
    
    parts.append(f"\n**Alive ({len(alive)})**:")
    for p in alive:
        parts.append(f"- {p.name} (`{p.player_id}`)")
    
    if dead:
        parts.append(f"\n**Dead ({len(dead)})**:")
        for p in dead:
            parts.append(f"- {p.name} - was {p.role.value}")
    
    return "\n".join(parts)


def build_events_summary(game_state: GameState, current_day: int) -> str:
    """Build a summary of important events."""
    events = []
    
    # Deaths
    kills = game_state.event_log.get_events_by_type(EventType.KILL)
    for kill in kills:
        target = game_state.players.get(kill.target_id)
        if target:
            role = kill.data.get("role", "UNKNOWN")
            events.append(f"Night {kill.day}: {target.name} killed (was {role})")
    
    # Eliminations
    eliminations = game_state.event_log.get_events_by_type(EventType.ELIMINATE)
    for elim in eliminations:
        eliminated = game_state.players.get(elim.player_id)
        if eliminated:
            role = elim.data.get("role", "UNKNOWN")
            events.append(f"Day {elim.day}: {eliminated.name} executed (was {role})")
    
    return "\n".join(events) if events else ""


def build_night_prompt(game_state: GameState, player: Player) -> str:
    """Build prompt for night phase."""
    parts = ["\n## Night Phase - Use Your Ability"]
    
    alive_others = [p for p in game_state.get_alive_players() if p.player_id != player.player_id]
    
    if player.role == Role.MAFIA:
        parts.append("\n**Choose a Town player to kill:**")
        town = [p for p in alive_others if p.team.value == "TOWN_TEAM"]
        for p in town:
            parts.append(f"- {p.name} (`{p.player_id}`)")
        parts.append("\nRespond with JSON:")
        parts.append('```json')
        parts.append('{"action_type": "NIGHT_ACTION", "night_action_type": "KILL", "target_id": "p0"}')
        parts.append('```')
    
    elif player.role == Role.DOCTOR:
        parts.append("\n**Choose a player to protect:**")
        for p in game_state.get_alive_players():
            marker = " (you)" if p.player_id == player.player_id else ""
            parts.append(f"- {p.name} (`{p.player_id}`){marker}")
        parts.append("\nRespond with JSON:")
        parts.append('```json')
        parts.append('{"action_type": "NIGHT_ACTION", "night_action_type": "SAVE", "target_id": "p0"}')
        parts.append('```')
    
    elif player.role == Role.DETECTIVE:
        parts.append("\n**Choose a player to investigate:**")
        for p in alive_others:
            parts.append(f"- {p.name} (`{p.player_id}`)")
        parts.append("\nRespond with JSON:")
        parts.append('```json')
        parts.append('{"action_type": "NIGHT_ACTION", "night_action_type": "INVESTIGATE", "target_id": "p0"}')
        parts.append('```')
    
    else:
        parts.append("\nYou have no night action. Wait for morning.")
        parts.append('```json')
        parts.append('{"action_type": "PASS"}')
        parts.append('```')
    
    return "\n".join(parts)


def build_discussion_prompt(game_state: GameState, player: Player) -> str:
    """Build prompt for discussion phase."""
    parts = ["\n## Discussion Phase - Share Your Thoughts"]
    
    parts.append("\nThis is the discussion phase. Share your observations, suspicions, or defend yourself.")
    parts.append("Keep your message focused and strategic.")
    
    # Show recent speeches
    speeches = game_state.event_log.get_speeches()
    current_day_speeches = [s for s in speeches if s.day == game_state.day]
    if current_day_speeches:
        parts.append("\n**Recent discussion:**")
        for speech in current_day_speeches[-5:]:
            speaker = game_state.players.get(speech.player_id)
            if speaker:
                msg = speech.data.get('message', '')
                parts.append(f"- {speaker.name}: \"{msg}\"")
    
    parts.append("\n**Respond with JSON:**")
    parts.append('```json')
    parts.append('{"action_type": "SPEAK", "message": "Your thoughts here..."}')
    parts.append('```')
    
    return "\n".join(parts)


def build_nomination_prompt(game_state: GameState, player: Player) -> str:
    """Build prompt for nomination phase."""
    parts = ["\n## Nomination Phase - Choose a Suspect"]
    
    parts.append("\nYou MUST nominate one player you find suspicious.")
    parts.append("The player with the most nominations goes to trial.")
    
    alive_others = [p for p in game_state.get_alive_players() if p.player_id != player.player_id]
    parts.append("\n**Alive players to nominate:**")
    for p in alive_others:
        parts.append(f"- {p.name} (`{p.player_id}`)")
    
    # Show current nominations if any
    if game_state.nominations:
        parts.append("\n**Current nomination counts:**")
        for target_id, nominators in sorted(game_state.nominations.items(), key=lambda x: -len(x[1])):
            target = game_state.players.get(target_id)
            if target:
                parts.append(f"- {target.name}: {len(nominators)} nomination(s)")
    
    parts.append("\n**Respond with JSON:**")
    parts.append('```json')
    example_id = alive_others[0].player_id if alive_others else "p0"
    parts.append(f'{{"action_type": "NOMINATE", "target_id": "{example_id}"}}')
    parts.append('```')
    
    return "\n".join(parts)


def build_defense_prompt(game_state: GameState, player: Player) -> str:
    """Build prompt for defense/trial phase."""
    parts = ["\n## Trial Phase"]
    
    if not game_state.trial_state:
        parts.append("No trial in progress.")
        return "\n".join(parts)
    
    defendant = game_state.players.get(game_state.trial_state.defendant_id)
    if not defendant:
        return "\n".join(parts)
    
    is_defendant = player.player_id == defendant.player_id
    
    if is_defendant:
        parts.append(f"\n**YOU ARE ON TRIAL!** Defend yourself!")
        parts.append("Explain why you are not Mafia. Be convincing!")
    else:
        parts.append(f"\n**{defendant.name} is on trial.**")
        parts.append("Share your opinion - are they guilty or innocent?")
    
    parts.append("\n**Respond with JSON:**")
    parts.append('```json')
    parts.append('{"action_type": "SPEAK", "message": "Your statement..."}')
    parts.append('```')
    
    return "\n".join(parts)


def build_judgment_prompt(game_state: GameState, player: Player) -> str:
    """Build prompt for judgment/voting phase."""
    parts = ["\n## Judgment Phase - Cast Your Vote"]
    
    if not game_state.trial_state:
        parts.append("No trial in progress.")
        return "\n".join(parts)
    
    defendant = game_state.players.get(game_state.trial_state.defendant_id)
    if not defendant:
        return "\n".join(parts)
    
    if player.player_id == defendant.player_id:
        parts.append("\nYou are the defendant and cannot vote.")
        parts.append('```json')
        parts.append('{"action_type": "PASS"}')
        parts.append('```')
        return "\n".join(parts)
    
    parts.append(f"\n**Should {defendant.name} be executed?**")
    parts.append("- Vote GUILTY if you believe they are Mafia")
    parts.append("- Vote INNOCENT if you believe they are Town")
    
    # Show current vote tally if any
    if game_state.trial_state.votes:
        guilty = sum(1 for v in game_state.trial_state.votes.values() if v)
        innocent = sum(1 for v in game_state.trial_state.votes.values() if not v)
        parts.append(f"\n**Current votes:** {guilty} Guilty, {innocent} Innocent")
    
    parts.append("\n**Respond with JSON (include your reasoning in message):**")
    parts.append('```json')
    parts.append('{"action_type": "SPEAK", "message": "GUILTY - I believe they are Mafia because..."}')
    parts.append('```')
    parts.append("OR")
    parts.append('```json')
    parts.append('{"action_type": "SPEAK", "message": "INNOCENT - I believe they are Town because..."}')
    parts.append('```')
    
    return "\n".join(parts)


def build_summarization_prompt(game_state: GameState, day: int) -> str:
    """Build prompt for day summarization."""
    parts = []
    
    parts.append("# Summarize This Day")
    parts.append(f"\nProvide a 2-3 sentence summary of Day {day}.")
    parts.append("Focus on: key accusations, trial results, who was eliminated.")
    
    parts.append("\n## Events:")
    day_events = game_state.event_log.get_events_by_day(day)
    for event in day_events:
        if event.type == EventType.SPEAK:
            speaker = game_state.players.get(event.player_id)
            if speaker:
                msg = event.data.get('message', '')[:100]
                parts.append(f"- {speaker.name}: \"{msg}...\"")
        elif event.type == EventType.NOMINATE:
            nominator = game_state.players.get(event.player_id)
            target = game_state.players.get(event.target_id)
            if nominator and target:
                parts.append(f"- {nominator.name} nominated {target.name}")
        elif event.type == EventType.ELIMINATE:
            eliminated = game_state.players.get(event.player_id)
            if eliminated:
                parts.append(f"- {eliminated.name} ({eliminated.role.value}) was executed")
    
    return "\n".join(parts)
