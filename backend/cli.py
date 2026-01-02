#!/usr/bin/env python3
"""
Interactive CLI tool for testing the Mafia game engine and LLM interactions.

Run with: python cli.py
"""

import asyncio
import random
import uuid
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.markdown import Markdown

from game.state import GameState, Player, Role, Team, Phase, TrialState
from game.actions import (
    SpeakAction, NominateAction, VoteAction, PassAction, NightAction, NightActionType,
)
from game.phases import process_action, process_night_results
from game.events import EventType
from llm.agent import LLMAgent
from llm.prompts import build_prompt_for_player
from llm.openrouter_client import get_client
from config import DEFAULT_MODEL

console = Console()

NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry",
    "Ivy", "Jack", "Kate", "Leo", "Maya", "Nick", "Olivia", "Pete"
]


class MafiaCLI:
    """Interactive CLI for testing the Mafia game engine."""
    
    def __init__(self):
        self.game: Optional[GameState] = None
        self.agents: dict[str, LLMAgent] = {}
        self.model: str = DEFAULT_MODEL
        # Limit discussion rounds per player (None = unlimited)
        self.max_rounds_per_player: int = 2  # Each player speaks max 2 times before forcing nominations
    
    def create_game(
        self,
        num_players: int = 8,
        num_mafia: int = 2,
        include_detective: bool = True,
        include_doctor: bool = True,
    ) -> None:
        """Create a new game with the specified configuration."""
        game_id = str(uuid.uuid4())[:8]
        self.game = GameState(game_id=game_id)
        self.agents = {}
        
        # Prepare roles
        roles = []
        roles.extend([Role.MAFIA] * num_mafia)
        if include_detective:
            roles.append(Role.DETECTIVE)
        if include_doctor:
            roles.append(Role.DOCTOR)
        villager_count = num_players - len(roles)
        roles.extend([Role.VILLAGER] * villager_count)
        
        random.shuffle(roles)
        
        # Create players
        player_names = random.sample(NAMES, num_players)
        for i, (name, role) in enumerate(zip(player_names, roles)):
            player_id = f"p{i}"
            team = Team.MAFIA_TEAM if role == Role.MAFIA else Team.TOWN_TEAM
            
            player = Player(
                player_id=player_id,
                name=name,
                role=role,
                team=team,
                is_human=False,
                model_name=self.model,
            )
            self.game.add_player(player)
            
            # Create LLM agent for each player
            self.agents[player_id] = LLMAgent(
                player_id=player_id,
                model_name=self.model,
            )
        
        self.game.is_started = True
        
        # Standard Mafia: Start at Night so Mafia kills first, giving Day 1 information
        self.game.current_phase = Phase.NIGHT
        self.game.day = 0  # Night before Day 1
    
    def display_state(self, show_roles: bool = True) -> None:
        """Display the current game state."""
        if not self.game:
            console.print("[red]No game in progress. Use 'new' to create a game.[/red]")
            return
        
        console.print()
        
        # Game info panel
        info_lines = [
            f"[bold]Game ID:[/bold] {self.game.game_id}",
            f"[bold]Phase:[/bold] {self.game.current_phase.value}",
            f"[bold]Day:[/bold] {self.game.day}",
            f"[bold]Model:[/bold] {self.model}",
        ]
        if self.game.winner:
            info_lines.append(f"[bold green]Winner:[/bold green] {self.game.winner.value}")
        
        console.print(Panel("\n".join(info_lines), title="Game State", border_style="blue"))
        
        # Players table
        table = Table(title="Players", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=4)
        table.add_column("Name", width=10)
        table.add_column("Role" if show_roles else "Role", width=12)
        table.add_column("Team" if show_roles else "Team", width=12)
        table.add_column("Status", width=10)
        table.add_column("Speaker", width=8)
        
        current_speaker = self.game.get_current_speaker()
        for player in self.game.players.values():
            status = "🟢 Alive" if player.is_alive else "💀 Dead"
            is_speaker = "👉" if current_speaker and current_speaker.player_id == player.player_id else ""
            
            role_display = player.role.value if show_roles else "???"
            team_display = player.team.value if show_roles else "???"
            
            # Color by role
            if show_roles:
                if player.role == Role.MAFIA:
                    role_display = f"[red]{role_display}[/red]"
                    team_display = f"[red]{team_display}[/red]"
                elif player.role == Role.DETECTIVE:
                    role_display = f"[blue]{role_display}[/blue]"
                elif player.role == Role.DOCTOR:
                    role_display = f"[green]{role_display}[/green]"
            
            table.add_row(
                player.player_id,
                player.name,
                role_display,
                team_display,
                status,
                is_speaker
            )
        
        console.print(table)
        
        # Nominations
        if self.game.nominations:
            nom_table = Table(title="Nominations", show_header=True)
            nom_table.add_column("Target")
            nom_table.add_column("Nominated By")
            for target_id, nominators in self.game.nominations.items():
                target = self.game.players.get(target_id)
                nom_names = [self.game.players[n].name for n in nominators if n in self.game.players]
                if target and target.is_alive:
                    nom_table.add_row(target.name, ", ".join(nom_names))
            console.print(nom_table)
        
        # Trial state (Town of Salem)
        if self.game.trial_state:
            defendant = self.game.players[self.game.trial_state.defendant_id]
            guilty = sum(1 for v in self.game.trial_state.votes.values() if v)
            innocent = sum(1 for v in self.game.trial_state.votes.values() if not v)
            console.print(Panel(
                f"[bold]Defendant:[/bold] {defendant.name} ({defendant.player_id})\n"
                f"[bold]Phase:[/bold] {self.game.trial_state.defense_phase}\n"
                f"[bold]Votes:[/bold] {guilty} Guilty, {innocent} Innocent",
                title="⚖️ Trial",
                border_style="red"
            ))
        
        # Legacy voting state
        if self.game.voting_state:
            nom1 = self.game.players[self.game.voting_state.nominee1_id]
            nom2 = self.game.players[self.game.voting_state.nominee2_id]
            console.print(Panel(
                f"[bold]Nominee 1:[/bold] {nom1.name} ({nom1.player_id})\n"
                f"[bold]Nominee 2:[/bold] {nom2.name} ({nom2.player_id})\n"
                f"[bold]Votes:[/bold] {len(self.game.voting_state.votes)}/{len(self.game.get_alive_players())}",
                title="Voting",
                border_style="yellow"
            ))
    
    def display_events(self, last_n: int = 10) -> None:
        """Display recent events."""
        if not self.game:
            console.print("[red]No game in progress.[/red]")
            return
        
        events = self.game.event_log.events[-last_n:]
        
        if not events:
            console.print("[dim]No events yet[/dim]")
            return
        
        table = Table(title=f"Recent Events (last {last_n})", show_header=True)
        table.add_column("Day", width=4)
        table.add_column("Type", width=14)
        table.add_column("Player", width=10)
        table.add_column("Target", width=10)
        table.add_column("Details")
        
        for event in events:
            player_name = self.game.players[event.player_id].name if event.player_id and event.player_id in self.game.players else "-"
            target_name = self.game.players[event.target_id].name if event.target_id and event.target_id in self.game.players else "-"
            
            details = ""
            if event.data:
                if "message" in event.data:
                    msg = event.data["message"]
                    details = msg
                elif "action_type" in event.data:
                    details = event.data["action_type"]
            
            table.add_row(str(event.day), event.type.value, player_name, target_name, details)
        
        console.print(table)
    
    def show_prompt(self, player_id: str) -> None:
        """Show the LLM prompt for a player."""
        if not self.game:
            console.print("[red]No game in progress.[/red]")
            return
        
        if player_id not in self.game.players:
            console.print(f"[red]Player {player_id} not found[/red]")
            return
        
        player = self.game.players[player_id]
        day_summary = self.game.day_summaries.get(self.game.day - 1)
        prompt_text = build_prompt_for_player(self.game, player_id, day_summary)
        
        console.print(Panel(
            Markdown(prompt_text),
            title=f"Prompt for {player.name} ({player_id})",
            border_style="cyan"
        ))
    
    async def ask_player(self, player_id: str, apply: bool = False) -> None:
        """Get an action from an LLM agent."""
        if not self.game:
            console.print("[red]No game in progress.[/red]")
            return
        
        if player_id not in self.agents:
            console.print(f"[red]No agent for {player_id}[/red]")
            return
        
        agent = self.agents[player_id]
        player = self.game.players[player_id]
        
        console.print(f"[dim]Asking {player.name} ({agent.model_name})...[/dim]")
        
        day_summary = self.game.day_summaries.get(self.game.day - 1)
        action = await agent.get_action(self.game, day_summary)
        
        console.print(Panel(
            Syntax(str(action.to_dict()), "python", theme="monokai"),
            title=f"Action from {player.name}",
            border_style="green"
        ))
        
        if apply or Confirm.ask("Apply this action?"):
            success, message = process_action(self.game, action)
            if success:
                console.print(f"[green]✓ Action applied[/green]" + (f": {message}" if message else ""))
            else:
                console.print(f"[red]✗ Action failed: {message}[/red]")
    
    async def run_step(self, count: int = 1) -> None:
        """Run one or more game steps - for Town of Salem, runs full phases."""
        if not self.game:
            console.print("[red]No game in progress.[/red]")
            return
        
        # In Town of Salem style, each "step" runs a full phase
        for i in range(count):
            if self.game.is_complete:
                console.print(f"[yellow]Game complete! {self.game.winner.value} wins![/yellow]")
                return
            
            console.print(f"\n[dim]Step {i + 1}/{count}[/dim]")
            await self.run_phase()
    
    async def run_phase(self) -> None:
        """Run the current phase to completion - Town of Salem style."""
        if not self.game:
            console.print("[red]No game in progress.[/red]")
            return
        
        phase = self.game.current_phase
        
        if phase == Phase.NIGHT:
            await self._run_night()
        elif phase == Phase.DAY_DISCUSSION:
            await self._run_discussion()
        elif phase == Phase.DAY_NOMINATION:
            await self._run_nominations()
        elif phase == Phase.DAY_DEFENSE:
            await self._run_defense()
        elif phase == Phase.DAY_JUDGMENT:
            await self._run_judgment()
        else:
            console.print(f"[yellow]Unknown phase: {phase.value}[/yellow]")
        
        if self.game.is_complete:
            console.print(f"\n[bold green]🎉 Game Over! {self.game.winner.value} wins![/bold green]")
    
    async def _run_discussion(self) -> None:
        """Run discussion phase - everyone speaks for N rounds."""
        console.print(f"[bold cyan]📢 Discussion Phase (Day {self.game.day})[/bold cyan]")
        console.print(f"[dim]Each player speaks {self.max_rounds_per_player} time(s)[/dim]\n")
        
        alive_players = self.game.get_alive_players()
        
        for round_num in range(self.max_rounds_per_player):
            console.print(f"[bold]--- Round {round_num + 1} ---[/bold]")
            
            for player in alive_players:
                agent = self.agents.get(player.player_id)
                if not agent:
                    continue
                
                # Get speech from LLM
                day_summary = self.game.day_summaries.get(self.game.day - 1)
                action = await agent.get_action(self.game, day_summary)
                
                # Force speak action (no nominations during discussion)
                if isinstance(action, SpeakAction):
                    self.game.event_log.add_event(
                        EventType.SPEAK,
                        self.game.current_phase.value,
                        self.game.day,
                        player_id=player.player_id,
                        data={"message": action.message}
                    )
                    console.print(f"[bold]{player.name}:[/bold] \"{action.message}\"")
                else:
                    # Fallback: generate a simple message
                    console.print(f"[bold]{player.name}:[/bold] [dim](passes)[/dim]")
                
                self.game.advance_speaker()
            
            console.print()
        
        # Move to nomination phase
        console.print("[yellow]Discussion complete. Moving to nominations...[/yellow]")
        self.game.current_phase = Phase.DAY_NOMINATION
        self.game.reset_speaker_order()
        self.game.nominations = {}
        self.game.who_nominated = {}
    
    async def _run_nominations(self) -> None:
        """Run nomination phase - everyone nominates someone."""
        console.print(f"[bold cyan]🎯 Nomination Phase[/bold cyan]")
        console.print(f"[dim]Each player nominates one suspect[/dim]\n")
        
        alive_players = self.game.get_alive_players()
        
        for player in alive_players:
            if player.player_id in self.game.who_nominated:
                continue  # Already nominated
            
            agent = self.agents.get(player.player_id)
            if not agent:
                continue
            
            # Get nomination from LLM
            day_summary = self.game.day_summaries.get(self.game.day - 1)
            action = await agent.get_action(self.game, day_summary)
            
            # Extract target
            target_id = None
            if isinstance(action, NominateAction):
                target_id = action.target_id
            elif hasattr(action, 'target_id'):
                target_id = action.target_id
            
            # Validate target
            valid_targets = [p.player_id for p in alive_players if p.player_id != player.player_id]
            if target_id not in valid_targets:
                # Random fallback
                target_id = random.choice(valid_targets)
            
            # Record nomination
            self.game.who_nominated[player.player_id] = target_id
            if target_id not in self.game.nominations:
                self.game.nominations[target_id] = []
            self.game.nominations[target_id].append(player.player_id)
            
            target = self.game.players[target_id]
            console.print(f"{player.name} nominates {target.name}")
        
        # Find most nominated player
        if not self.game.nominations:
            console.print("[yellow]No nominations. Moving to night...[/yellow]")
            self._transition_to_night()
            return
        
        # Sort by nomination count
        sorted_noms = sorted(
            self.game.nominations.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        top_count = len(sorted_noms[0][1])
        tied = [pid for pid, noms in sorted_noms if len(noms) == top_count]
        
        # Pick defendant (random if tied)
        defendant_id = random.choice(tied) if len(tied) > 1 else sorted_noms[0][0]
        defendant = self.game.players[defendant_id]
        
        console.print(f"\n[bold red]⚖️ {defendant.name} goes to trial with {top_count} nomination(s)![/bold red]")
        
        # Set up trial
        self.game.trial_state = TrialState(defendant_id=defendant_id, defense_phase="opening")
        self.game.current_phase = Phase.DAY_DEFENSE
    
    async def _run_defense(self) -> None:
        """Run defense phase - defendant defends, others respond, defendant closes."""
        if not self.game.trial_state:
            console.print("[red]No trial in progress[/red]")
            return
        
        defendant = self.game.players[self.game.trial_state.defendant_id]
        console.print(f"[bold cyan]⚖️ Trial of {defendant.name}[/bold cyan]\n")
        
        # 1. Defendant opening statement
        console.print("[bold]--- Opening Defense ---[/bold]")
        agent = self.agents.get(defendant.player_id)
        if agent:
            day_summary = self.game.day_summaries.get(self.game.day - 1)
            action = await agent.get_action(self.game, day_summary)
            if isinstance(action, SpeakAction):
                console.print(f"[bold]{defendant.name} (defendant):[/bold] \"{action.message}\"")
            else:
                console.print(f"[bold]{defendant.name} (defendant):[/bold] [dim](remains silent)[/dim]")
        
        # 2. Others respond
        console.print("\n[bold]--- Town Responds ---[/bold]")
        for player in self.game.get_alive_players():
            if player.player_id == defendant.player_id:
                continue
            
            agent = self.agents.get(player.player_id)
            if not agent:
                continue
            
            day_summary = self.game.day_summaries.get(self.game.day - 1)
            action = await agent.get_action(self.game, day_summary)
            
            if isinstance(action, SpeakAction):
                console.print(f"[bold]{player.name}:[/bold] \"{action.message}\"")
            else:
                console.print(f"[bold]{player.name}:[/bold] [dim](no comment)[/dim]")
        
        # 3. Defendant closing statement
        console.print("\n[bold]--- Closing Defense ---[/bold]")
        if agent:
            action = await agent.get_action(self.game, day_summary)
            if isinstance(action, SpeakAction):
                console.print(f"[bold]{defendant.name} (defendant):[/bold] \"{action.message}\"")
            else:
                console.print(f"[bold]{defendant.name} (defendant):[/bold] [dim](remains silent)[/dim]")
        
        # Move to judgment
        console.print("\n[yellow]Defense complete. Moving to judgment...[/yellow]")
        self.game.trial_state.defense_phase = "done"
        self.game.current_phase = Phase.DAY_JUDGMENT
    
    async def _run_judgment(self) -> None:
        """Run judgment phase - vote GUILTY or INNOCENT."""
        if not self.game.trial_state:
            console.print("[red]No trial in progress[/red]")
            return
        
        defendant = self.game.players[self.game.trial_state.defendant_id]
        console.print(f"[bold cyan]🗳️ Judgment: Is {defendant.name} GUILTY or INNOCENT?[/bold cyan]\n")
        
        guilty_votes = 0
        innocent_votes = 0
        
        for player in self.game.get_alive_players():
            if player.player_id == defendant.player_id:
                continue  # Defendant can't vote
            
            if player.player_id in self.game.trial_state.votes:
                continue  # Already voted
            
            agent = self.agents.get(player.player_id)
            if not agent:
                continue
            
            # Get vote from LLM - we'll interpret any action as a vote
            day_summary = self.game.day_summaries.get(self.game.day - 1)
            action = await agent.get_action(self.game, day_summary)
            
            # Determine vote (simple heuristic: Mafia votes innocent for each other)
            vote_guilty = True  # Default
            
            # Check if action has vote info
            if hasattr(action, 'message'):
                msg = action.message.lower() if action.message else ""
                if 'innocent' in msg or 'not guilty' in msg:
                    vote_guilty = False
                elif 'guilty' in msg:
                    vote_guilty = True
                else:
                    # Random for now - TODO: better LLM integration
                    vote_guilty = random.choice([True, False])
            else:
                vote_guilty = random.choice([True, False])
            
            self.game.trial_state.votes[player.player_id] = vote_guilty
            
            if vote_guilty:
                guilty_votes += 1
                console.print(f"{player.name}: [red]GUILTY[/red]")
            else:
                innocent_votes += 1
                console.print(f"{player.name}: [green]INNOCENT[/green]")
        
        # Determine verdict
        console.print(f"\n[bold]Votes: {guilty_votes} Guilty, {innocent_votes} Innocent[/bold]")
        
        if guilty_votes > innocent_votes:
            # GUILTY - execute
            console.print(f"\n[bold red]☠️ {defendant.name} has been executed![/bold red]")
            console.print(f"[dim]They were {defendant.role.value}[/dim]")
            defendant.is_alive = False
            
            self.game.event_log.add_event(
                EventType.ELIMINATE,
                self.game.current_phase.value,
                self.game.day,
                player_id=defendant.player_id,
                data={"role": defendant.role.value, "team": defendant.team.value}
            )
            
            # Check win condition
            winner = self.game.check_win_conditions()
            if winner:
                self.game.winner = winner
                self.game.is_complete = True
                return
        else:
            # INNOCENT or TIE - acquit
            console.print(f"\n[bold green]✓ {defendant.name} has been acquitted![/bold green]")
        
        # Move to night
        self._transition_to_night()
    
    def _transition_to_night(self) -> None:
        """Transition to night phase."""
        self.game.current_phase = Phase.NIGHT
        self.game.trial_state = None
        self.game.nominations = {}
        self.game.who_nominated = {}
        self.game.reset_speaker_order()
        console.print("\n[bold]🌙 Night falls...[/bold]")
    
    async def _run_night(self) -> None:
        """Handle night phase - Mafia kills, Doctor saves, Detective investigates."""
        console.print(f"[bold cyan]🌙 Night {self.game.day}[/bold cyan]\n")
        
        night_actions = {}
        investigation_results = {}
        
        # Collect actions from special roles
        for player in self.game.get_alive_players():
            if player.role not in [Role.MAFIA, Role.DOCTOR, Role.DETECTIVE]:
                continue
            
            agent = self.agents.get(player.player_id)
            if not agent:
                continue
            
            day_summary = self.game.day_summaries.get(self.game.day - 1)
            action = await agent.get_action(self.game, day_summary)
            
            # Get target from action
            target_id = None
            if isinstance(action, NightAction):
                target_id = action.target_id
                night_actions[player.player_id] = action
            elif hasattr(action, 'target_id'):
                target_id = action.target_id
            
            # Validate and set fallback
            valid_targets = [p.player_id for p in self.game.get_alive_players()]
            if player.role != Role.DOCTOR:
                valid_targets = [t for t in valid_targets if t != player.player_id]
            
            if target_id not in valid_targets and valid_targets:
                target_id = random.choice(valid_targets)
            
            if target_id:
                target = self.game.players[target_id]
                
                if player.role == Role.MAFIA:
                    night_actions[player.player_id] = NightAction(
                        player_id=player.player_id,
                        night_action_type=NightActionType.KILL,
                        target_id=target_id
                    )
                    console.print(f"[red]{player.name} (MAFIA)[/red] targets {target.name}")
                
                elif player.role == Role.DOCTOR:
                    night_actions[player.player_id] = NightAction(
                        player_id=player.player_id,
                        night_action_type=NightActionType.SAVE,
                        target_id=target_id
                    )
                    console.print(f"[green]{player.name} (DOCTOR)[/green] protects {target.name}")
                
                elif player.role == Role.DETECTIVE:
                    night_actions[player.player_id] = NightAction(
                        player_id=player.player_id,
                        night_action_type=NightActionType.INVESTIGATE,
                        target_id=target_id
                    )
                    is_mafia = target.role == Role.MAFIA
                    result = "MAFIA" if is_mafia else "NOT MAFIA"
                    investigation_results[player.player_id] = (target_id, is_mafia)
                    console.print(f"[blue]{player.name} (DETECTIVE)[/blue] investigates {target.name} → [bold]{result}[/bold]")
        
        # Process night results
        if night_actions:
            alive_before = set(p.player_id for p in self.game.get_alive_players())
            
            process_night_results(self.game, night_actions)
            
            alive_after = set(p.player_id for p in self.game.get_alive_players())
            died = alive_before - alive_after
            
            # Dawn
            self.game.day += 1
            self.game.current_phase = Phase.DAY_DISCUSSION
            self.game.reset_speaker_order()
            self.game.nominations = {}
            self.game.who_nominated = {}
            self.game.trial_state = None
            
            console.print(f"\n[bold]☀️ Day {self.game.day} dawns[/bold]")
            if died:
                for pid in died:
                    dead_player = self.game.players[pid]
                    console.print(f"[red]💀 {dead_player.name} was found dead! (was {dead_player.role.value})[/red]")
            else:
                console.print(f"[green]Everyone survived the night![/green]")
            
            # Check win condition
            winner = self.game.check_win_conditions()
            if winner:
                self.game.winner = winner
                self.game.is_complete = True
    
    async def test_llm(self, message: str) -> None:
        """Send a test message to the LLM."""
        try:
            client = get_client()
            messages = [{"role": "user", "content": message}]
            
            console.print(f"[dim]Sending to {self.model}...[/dim]")
            response = await client.chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            
            content = response["choices"][0]["message"]["content"]
            console.print(Panel(content, title="Response", border_style="green"))
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    def process_command(self, cmd: str) -> bool:
        """Process a command. Returns False if should exit."""
        parts = cmd.strip().split(maxsplit=1)
        if not parts:
            return True
        
        command = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""
        args = args_str.split() if args_str else []
        
        try:
            if command in ["quit", "exit", "q"]:
                console.print("[dim]Goodbye![/dim]")
                return False
            
            elif command == "help" or command == "?":
                self.show_help()
            
            elif command == "new":
                players = int(args[0]) if args else 8
                mafia = int(args[1]) if len(args) > 1 else 2
                self.create_game(num_players=players, num_mafia=mafia)
                console.print(f"[green]✓ Created game with {players} players ({mafia} mafia)[/green]")
                self.display_state()
            
            elif command in ["state", "s", "status"]:
                show_roles = "--hide" not in args_str
                self.display_state(show_roles=show_roles)
            
            elif command in ["events", "e", "log"]:
                n = int(args[0]) if args else 10
                self.display_events(n)
            
            elif command in ["prompt", "p"]:
                if not args:
                    console.print("[red]Usage: prompt <player_id>[/red]")
                else:
                    self.show_prompt(args[0])
            
            elif command == "ask":
                if not args:
                    console.print("[red]Usage: ask <player_id>[/red]")
                else:
                    asyncio.run(self.ask_player(args[0]))
            
            elif command in ["step", "n", "next"]:
                count = int(args[0]) if args else 1
                asyncio.run(self.run_step(count))
            
            elif command in ["phase", "run"]:
                asyncio.run(self.run_phase())
            
            elif command == "speak":
                if len(args) < 1:
                    console.print("[red]Usage: speak <player_id> <message>[/red]")
                else:
                    player_id = args[0]
                    message = args_str.split(maxsplit=1)[1] if len(args_str.split(maxsplit=1)) > 1 else ""
                    if not message:
                        console.print("[red]Message required[/red]")
                    elif self.game:
                        action = SpeakAction(player_id=player_id, message=message)
                        success, error = process_action(self.game, action)
                        if success:
                            console.print(f"[green]✓ {self.game.players[player_id].name} spoke[/green]")
                        else:
                            console.print(f"[red]✗ {error}[/red]")
            
            elif command in ["nominate", "nom"]:
                if len(args) < 2:
                    console.print("[red]Usage: nominate <player_id> <target_id>[/red]")
                elif self.game:
                    action = NominateAction(player_id=args[0], target_id=args[1])
                    success, msg = process_action(self.game, action)
                    if success:
                        p1 = self.game.players[args[0]].name
                        p2 = self.game.players[args[1]].name
                        console.print(f"[green]✓ {p1} nominated {p2}[/green]")
                        if msg:
                            console.print(f"[yellow]{msg}[/yellow]")
                    else:
                        console.print(f"[red]✗ {msg}[/red]")
            
            elif command == "vote":
                if len(args) < 2:
                    console.print("[red]Usage: vote <player_id> <nominee_id>[/red]")
                elif self.game:
                    action = VoteAction(player_id=args[0], nominee_id=args[1])
                    success, msg = process_action(self.game, action)
                    if success:
                        console.print(f"[green]✓ Vote recorded[/green]")
                        if msg:
                            console.print(f"[yellow]{msg}[/yellow]")
                    else:
                        console.print(f"[red]✗ {msg}[/red]")
            
            elif command == "pass":
                if not args:
                    console.print("[red]Usage: pass <player_id>[/red]")
                elif self.game:
                    action = PassAction(player_id=args[0])
                    success, error = process_action(self.game, action)
                    if success:
                        console.print(f"[green]✓ Passed[/green]")
                    else:
                        console.print(f"[red]✗ {error}[/red]")
            
            elif command == "night":
                if len(args) < 3:
                    console.print("[red]Usage: night <player_id> <KILL|SAVE|INVESTIGATE> <target_id>[/red]")
                elif self.game:
                    try:
                        night_type = NightActionType(args[1].upper())
                        action = NightAction(player_id=args[0], night_action_type=night_type, target_id=args[2])
                        success, msg = process_action(self.game, action)
                        if success:
                            console.print(f"[green]✓ Night action recorded[/green]")
                        else:
                            console.print(f"[red]✗ {msg}[/red]")
                    except ValueError:
                        console.print("[red]Invalid type. Use KILL, SAVE, or INVESTIGATE[/red]")
            
            elif command == "kill":
                if not args:
                    console.print("[red]Usage: kill <player_id>[/red]")
                elif self.game and args[0] in self.game.players:
                    player = self.game.players[args[0]]
                    player.is_alive = False
                    console.print(f"[red]💀 {player.name} killed ({player.role.value})[/red]")
                    winner = self.game.check_win_conditions()
                    if winner:
                        self.game.winner = winner
                        self.game.is_complete = True
                        console.print(f"[bold green]🎉 {winner.value} wins![/bold green]")
                else:
                    console.print(f"[red]Player not found[/red]")
            
            elif command == "setphase":
                if not args:
                    console.print("[red]Usage: setphase <DAY_DISCUSSION|DAY_VOTING|NIGHT>[/red]")
                elif self.game:
                    try:
                        self.game.current_phase = Phase(args[0].upper())
                        console.print(f"[green]✓ Phase set to {self.game.current_phase.value}[/green]")
                    except ValueError:
                        console.print("[red]Invalid phase[/red]")
            
            elif command == "model":
                if args:
                    self.model = args[0]
                    # Update all agents
                    for agent in self.agents.values():
                        agent.model_name = self.model
                    console.print(f"[green]✓ Model set to {self.model}[/green]")
                else:
                    console.print(f"Current model: {self.model}")
            
            elif command == "chat":
                if not args_str:
                    console.print("[red]Usage: chat <message>[/red]")
                else:
                    asyncio.run(self.test_llm(args_str))
            
            elif command == "auto":
                # Run the full game automatically
                asyncio.run(self.run_auto())
            
            elif command == "rounds":
                if args:
                    self.max_rounds_per_player = int(args[0])
                    console.print(f"[green]✓ Max discussion rounds set to {self.max_rounds_per_player}[/green]")
                else:
                    console.print(f"Max discussion rounds per player: {self.max_rounds_per_player}")
            
            elif command == "quickstart":
                # Create game and run first night automatically, then show Day 1
                players = int(args[0]) if args else 6
                mafia = int(args[1]) if len(args) > 1 else 1
                self.create_game(num_players=players, num_mafia=mafia)
                console.print(f"[green]✓ Created game with {players} players ({mafia} mafia)[/green]")
                console.print(f"[dim]Starting at Night 0 (Mafia's first kill)...[/dim]")
                
                # Run night phase automatically
                asyncio.run(self._run_night())
                
                console.print(f"[bold]Day {self.game.day} begins - now there's information to discuss![/bold]")
                self.display_state()
            
            else:
                console.print(f"[red]Unknown command: {command}. Type 'help' for commands.[/red]")
        
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        
        return True
    
    async def run_auto(self) -> None:
        """Run the game automatically until completion."""
        if not self.game:
            console.print("[red]No game in progress. Use 'new' first.[/red]")
            return
        
        console.print("[bold]Running game automatically...[/bold]\n")
        
        while not self.game.is_complete:
            console.print(f"\n[bold cyan]═══ {self.game.current_phase.value} (Day {self.game.day}) ═══[/bold cyan]")
            await self.run_phase()
            
            if not self.game.is_complete:
                self.display_state()
        
        console.print(f"\n[bold green]🎉 Game Complete! {self.game.winner.value} wins![/bold green]")
        self.display_state()
    
    def show_help(self) -> None:
        """Show help information."""
        console.print(Panel(
            "[bold yellow]Town of Salem Style Flow:[/bold yellow]\n"
            "  Night → Discussion → Nomination → Defense → Judgment → Night...\n"
            "\n[bold cyan]Game Management[/bold cyan]\n"
            "  [cyan]new[/cyan] [players] [mafia]  - Create new game (starts at Night 0)\n"
            "  [cyan]quickstart[/cyan] [p] [m]     - Create game & run first night\n"
            "  [cyan]state[/cyan] / [cyan]s[/cyan]              - Show game state\n"
            "  [cyan]events[/cyan] / [cyan]e[/cyan] [n]         - Show last n events\n"
            "  [cyan]model[/cyan] [name]           - Get/set LLM model\n"
            "  [cyan]rounds[/cyan] [n]             - Discussion rounds per player (default: 2)\n"
            "\n[bold cyan]Running the Game[/bold cyan]\n"
            "  [cyan]phase[/cyan] / [cyan]run[/cyan]            - Run current phase to completion\n"
            "  [cyan]step[/cyan] / [cyan]n[/cyan] [count]       - Run n full phases\n"
            "  [cyan]auto[/cyan]                   - Run entire game automatically\n"
            "\n[bold cyan]LLM Testing[/bold cyan]\n"
            "  [cyan]prompt[/cyan] / [cyan]p[/cyan] <id>        - Show LLM prompt for player\n"
            "  [cyan]ask[/cyan] <id>               - Get action from LLM agent\n"
            "  [cyan]chat[/cyan] <message>         - Send raw message to LLM\n"
            "\n[bold cyan]Debug[/bold cyan]\n"
            "  [cyan]kill[/cyan] <id>              - Kill a player\n"
            "  [cyan]setphase[/cyan] <phase>       - Set phase (NIGHT/DAY_DISCUSSION/etc)\n"
            "\n[bold cyan]Other[/bold cyan]\n"
            "  [cyan]help[/cyan] / [cyan]?[/cyan]               - Show this help\n"
            "  [cyan]quit[/cyan] / [cyan]q[/cyan]               - Exit",
            title="Mafia CLI - Town of Salem Style",
            border_style="blue"
        ))
    
    def run(self) -> None:
        """Run the interactive CLI."""
        console.print(Panel(
            "[bold]Mafia Game Engine CLI[/bold]\n\n"
            "Test the game engine and LLM interactions.\n"
            "Type [cyan]help[/cyan] for commands or [cyan]new[/cyan] to start a game.",
            title="Welcome",
            border_style="blue"
        ))
        
        while True:
            try:
                # Show current state in prompt
                prompt_parts = ["[bold blue]mafia"]
                if self.game:
                    prompt_parts.append(f"[dim]({self.game.current_phase.value[:3]})[/dim]")
                prompt_parts.append(">[/bold blue]")
                
                cmd = Prompt.ask("".join(prompt_parts))
                
                if not self.process_command(cmd):
                    break
            
            except KeyboardInterrupt:
                console.print("\n[dim]Use 'quit' to exit[/dim]")
            except EOFError:
                break


def main():
    """Entry point."""
    cli = MafiaCLI()
    cli.run()


if __name__ == "__main__":
    main()
