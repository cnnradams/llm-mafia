"""Prompt generation for LLM players - Town of Salem style."""
from typing import List, Optional, Dict, Any
from collections import Counter

from game.state import GameState, Player, Phase, Role
from game.events import EventLog, EventType, GameEvent


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
    
    # Initial game setup
    prompt_parts.append(build_game_setup(game_state))
    
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
    
    # Complete game history (completed days only)
    history = build_complete_history(game_state)
    if history:
        prompt_parts.append(history)
    
    # Current day events (what's happened today so far)
    today = build_today_events(game_state)
    if today:
        prompt_parts.append(today)
    
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


def build_game_setup(game_state: GameState) -> str:
    """Build initial game setup information."""
    # Count roles at game start (includes dead players)
    role_counts = Counter(p.role for p in game_state.players.values())
    
    parts = ["\n## Initial Game Setup"]
    parts.append(f"- Total Players: {len(game_state.players)}")
    
    if role_counts[Role.MAFIA] > 0:
        parts.append(f"- Mafia: {role_counts[Role.MAFIA]}")
    if role_counts[Role.VILLAGER] > 0:
        parts.append(f"- Villagers: {role_counts[Role.VILLAGER]}")
    if role_counts[Role.DETECTIVE] > 0:
        parts.append(f"- Detective: {role_counts[Role.DETECTIVE]}")
    if role_counts[Role.DOCTOR] > 0:
        parts.append(f"- Doctor: {role_counts[Role.DOCTOR]}")
    
    return "\n".join(parts)


def build_complete_history(game_state: GameState) -> str:
    """Build a complete history of COMPLETED days only (not current day in progress).
    
    The current day's events happen in real-time and agents see them as they occur.
    Past days should be in the agent's memory (updated at end of each day).
    """
    parts = ["\n## Complete Game History (Completed Days)"]
    
    if not game_state.event_log.events:
        parts.append("\n(No events yet - game just started)")
        return "\n".join(parts)
    
    current_day = game_state.day
    
    # Organize events by day
    events_by_day: Dict[int, List[GameEvent]] = {}
    for event in game_state.event_log.events:
        if event.day not in events_by_day:
            events_by_day[event.day] = []
        events_by_day[event.day].append(event)
    
    # Build history for COMPLETED days only (exclude current day in progress)
    completed_days = [day for day in sorted(events_by_day.keys()) if day < current_day]
    
    if not completed_days:
        parts.append("\n(No completed days yet - this is Day 1)")
        return "\n".join(parts)
    
    for day in completed_days:
        day_events = events_by_day[day]
        
        # Night events
        night_events = [e for e in day_events if e.phase == "NIGHT"]
        if night_events:
            parts.append(f"\n### Night {day}")
            
            # Kills
            kills = [e for e in night_events if e.type == EventType.KILL]
            for kill in kills:
                victim = game_state.players.get(kill.target_id)
                if victim:
                    role = kill.data.get("role", "UNKNOWN")
                    parts.append(f"- **{victim.name}** was killed (was {role})")
            
            if not kills:
                parts.append("- No one died this night")
        
        # Day events - show OUTCOMES only (no discussion/defense text)
        nomination_events = [e for e in day_events if e.phase == "DAY_NOMINATION"]
        judgment_events = [e for e in day_events if e.phase == "DAY_JUDGMENT"]
        
        nominations = [e for e in nomination_events if e.type == EventType.NOMINATE]
        eliminations = [e for e in judgment_events if e.type == EventType.ELIMINATE]
        
        # Show Day section if there were nominations
        if nominations:
            parts.append(f"\n### Day {day}")
            
            # Nominations - show who was nominated
            # Group by target
            nom_by_target: Dict[str, List[str]] = {}
            for nom in nominations:
                target_id = nom.target_id
                if target_id not in nom_by_target:
                    nom_by_target[target_id] = []
                nominator = game_state.players.get(nom.player_id)
                if nominator:
                    nom_by_target[target_id].append(nominator.name)
            
            parts.append("\n**Nominations:**")
            for target_id, nominators in sorted(nom_by_target.items(), key=lambda x: -len(x[1])):
                target = game_state.players.get(target_id)
                if target:
                    nom_str = ", ".join(nominators)
                    parts.append(f"- {target.name}: {len(nominators)} votes ({nom_str})")
            
            # Show who went to trial (most nominated)
            if nom_by_target:
                most_nominated = max(nom_by_target.items(), key=lambda x: len(x[1]))
                defendant = game_state.players.get(most_nominated[0])
                if defendant:
                    parts.append(f"\n**→ {defendant.name} went to trial**")
            
            # Trial/Judgment outcome (no speeches, just results)
            if eliminations:
                for elim in eliminations:
                    defendant = game_state.players.get(elim.player_id)
                    if defendant:
                        role = elim.data.get("role", "UNKNOWN")
                        parts.append(f"\n**Trial Result:** {defendant.name} was **EXECUTED** (was {role})")
                        
                        # Show votes if available in data
                        if "votes" in elim.data:
                            votes = elim.data["votes"]
                            guilty_voters = [game_state.players[pid].name for pid, vote in votes.items() if vote and pid in game_state.players]
                            innocent_voters = [game_state.players[pid].name for pid, vote in votes.items() if not vote and pid in game_state.players]
                            
                            if guilty_voters:
                                parts.append(f"  - Guilty ({len(guilty_voters)}): {', '.join(guilty_voters)}")
                            if innocent_voters:
                                parts.append(f"  - Innocent ({len(innocent_voters)}): {', '.join(innocent_voters)}")
            elif judgment_events:
                # Trial happened but no one was eliminated = acquittal
                parts.append(f"**Trial Result:** {defendant.name} was **ACQUITTED**")
    
    return "\n".join(parts)


def build_today_events(game_state: GameState) -> str:
    """Build a summary of events that have happened TODAY (current day in progress)."""
    parts = [f"\n## Today's Events (Day {game_state.day})"]
    
    current_day = game_state.day
    events = game_state.event_log.get_events_by_day(current_day)
    
    if not events:
        parts.append("\n(Day just started - no events yet)")
        return "\n".join(parts)
    
    # Night events
    night_events = [e for e in events if e.phase == "NIGHT"]
    if night_events:
        parts.append("\n**Night Results:**")
        kills = [e for e in night_events if e.type == EventType.KILL]
        for kill in kills:
            victim = game_state.players.get(kill.target_id)
            if victim:
                role = kill.data.get("role", "UNKNOWN")
                parts.append(f"- **{victim.name}** was killed by the Mafia (was {role})")
        if not kills:
            parts.append("- No one died this night")
    
    # Discussion events
    discussion_events = [e for e in events if e.phase == "DAY_DISCUSSION"]
    discussion_speeches = [e for e in discussion_events if e.type == EventType.SPEAK]
    if discussion_speeches:
        parts.append("\n**Discussion:**")
        for i, speech in enumerate(discussion_speeches, 1):
            speaker = game_state.players.get(speech.player_id)
            if speaker:
                msg = speech.data.get('message', '')
                parts.append(f"{i}. **{speaker.name}**: \"{msg}\"")
                parts.append("")  # Blank line
    
    # Nomination events (but don't show "went to trial" until nominations are complete)
    nomination_events = [e for e in events if e.phase == "DAY_NOMINATION"]
    nominations = [e for e in nomination_events if e.type == EventType.NOMINATE]
    if nominations:
        # Group by target
        nom_by_target: Dict[str, List[str]] = {}
        for nom in nominations:
            target_id = nom.target_id
            if target_id not in nom_by_target:
                nom_by_target[target_id] = []
            nominator = game_state.players.get(nom.player_id)
            if nominator:
                nom_by_target[target_id].append(nominator.name)
        
        parts.append("\n**Nominations so far:**")
        for target_id, nominators in sorted(nom_by_target.items(), key=lambda x: -len(x[1])):
            target = game_state.players.get(target_id)
            if target:
                nom_str = ", ".join(nominators)
                parts.append(f"- {target.name}: {len(nominators)} votes ({nom_str})")
    
    # Defense/Trial events
    defense_events = [e for e in events if e.phase == "DAY_DEFENSE"]
    defense_speeches = [e for e in defense_events if e.type == EventType.SPEAK]
    if defense_speeches:
        parts.append("\n**Trial Defense:**")
        for speech in defense_speeches:
            speaker = game_state.players.get(speech.player_id)
            if speaker:
                context = speech.data.get('context', '')
                msg = speech.data.get('message', '')
                
                if context == "opening_defense":
                    label = f"**{speaker.name}** (DEFENDANT - opening)"
                elif context == "closing_defense":
                    label = f"**{speaker.name}** (DEFENDANT - closing)"
                elif context == "town_response":
                    label = f"**{speaker.name}**"
                else:
                    label = f"**{speaker.name}**"
                
                parts.append(f"- {label}: \"{msg}\"")
    
    return "\n".join(parts)


def build_role_knowledge(game_state: GameState, player: Player) -> str:
    """Build role-specific knowledge section."""
    parts = []
    
    if player.role == Role.MAFIA:
        mafia_players = game_state.get_players_by_role(Role.MAFIA)
        mafia_info = [f"{p.name} (`{p.player_id}`)" for p in mafia_players]
        parts.append(f"\n**Mafia teammates**: {', '.join(mafia_info)}")
        parts.append("Your goal: Eliminate Town without getting caught.")
        
        # Show Mafia kill attempts and results
        night_actions = game_state.event_log.get_events_by_type(EventType.NIGHT_ACTION)
        kills = game_state.event_log.get_events_by_type(EventType.KILL)
        
        mafia_kills = {}
        for event in night_actions:
            if event.data.get("action_type") == "KILL":
                # This was a kill attempt
                mafia_kills[event.day] = event.target_id
        
        if mafia_kills:
            parts.append("\n**Your kill attempts:**")
            for day, target_id in sorted(mafia_kills.items()):
                target = game_state.players.get(target_id)
                if target:
                    # Check if kill was successful
                    kill_succeeded = any(k.day == day and k.target_id == target_id for k in kills)
                    if kill_succeeded:
                        parts.append(f"- Night {day}: Killed {target.name} ✓")
                    else:
                        parts.append(f"- Night {day}: Tried to kill {target.name} - **BLOCKED** (Doctor saved them)")
    
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
    parts.append("\n*Note: See 'Today's Events' above for night results and discussion so far.*")
    
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
    parts.append("\n*Note: See 'Today's Events' above for discussion and nominations so far.*")
    
    alive_others = [p for p in game_state.get_alive_players() if p.player_id != player.player_id]
    parts.append("\n**Alive players to nominate:**")
    for p in alive_others:
        parts.append(f"- {p.name} (`{p.player_id}`)")
    
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
    
    parts.append(f"\n*Note: See 'Today's Events' above for discussion and trial statements so far.*")
    
    if is_defendant:
        parts.append(f"\n**⚠️ YOU ({player.name}) ARE ON TRIAL! THE TOWN WANTS TO EXECUTE YOU!**")
        parts.append("\n**This is YOUR DEFENSE - defend YOURSELF!**")
        parts.append("Speak in FIRST PERSON ('I am innocent...', 'I didn't...', 'My role is...').")
        parts.append("DO NOT talk about yourself in third person. YOU are defending YOUR life!")
        parts.append("\nDefense strategies:")
        parts.append("- Claim your role (if safe to do so)")
        parts.append("- Explain why you're innocent")
        parts.append("- Point out why the accusations against you are wrong")
        parts.append("- Redirect suspicion to actual suspicious players")
        parts.append("- Appeal to your voting/speaking record")
    else:
        parts.append(f"\n**{defendant.name} is on trial.**")
        parts.append("Share your opinion - do you think they are Mafia or Town?")
        parts.append("Consider their behavior, claims, and who nominated them.")
    
    parts.append("\n**Respond with JSON (defend yourself in first person):**")
    parts.append('```json')
    if is_defendant:
        parts.append('{"action_type": "SPEAK", "message": "I am innocent! I am a [role] and here is why you should not execute me: [your defense]"}')
    else:
        parts.append('{"action_type": "SPEAK", "message": "I think [defendant] is suspicious because... OR I think [defendant] is innocent because..."}')
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
    
    parts.append(f"\n*Note: See 'Today's Events' above for all discussion, nominations, and trial defense statements.*")
    
    parts.append(f"\n**Should {defendant.name} be executed?**")
    parts.append("- Vote GUILTY if you believe they are Mafia")
    parts.append("- Vote INNOCENT if you believe they are Town")
    
    # Show current vote tally if any
    if game_state.trial_state.votes:
        guilty_voters = [game_state.players[pid].name for pid, vote in game_state.trial_state.votes.items() if vote and pid in game_state.players]
        innocent_voters = [game_state.players[pid].name for pid, vote in game_state.trial_state.votes.items() if not vote and pid in game_state.players]
        
        parts.append(f"\n**Current votes:**")
        if guilty_voters:
            parts.append(f"- Guilty ({len(guilty_voters)}): {', '.join(guilty_voters)}")
        if innocent_voters:
            parts.append(f"- Innocent ({len(innocent_voters)}): {', '.join(innocent_voters)}")
    
    parts.append("\n**Respond with JSON:**")
    parts.append('```json')
    parts.append('{"action_type": "JUDGMENT_VOTE", "vote": "GUILTY", "reason": "I believe they are Mafia because..."}')
    parts.append('```')
    parts.append("OR")
    parts.append('```json')
    parts.append('{"action_type": "JUDGMENT_VOTE", "vote": "INNOCENT", "reason": "I believe they are Town because..."}')
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
