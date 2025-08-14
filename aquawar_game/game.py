"""Core game logic for Aquawar.

The :class:`Game` class coordinates rounds, assertions and actions.  It is
suitable both for usage by LLM agents (who receive textual prompts describing
only the current state) and for an interactive CLI demo (see ``demo.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import random

from .fish import create_fish, Fish, MimicFish, FISH_FACTORIES

FISH_NAMES = list(FISH_FACTORIES.keys())


# ---------------------------------------------------------------------------
# Utility structures
# ---------------------------------------------------------------------------

@dataclass
class Team:
    fish: List[Fish]

    def living_fish(self) -> List[Fish]:
        return [f for f in self.fish if f.is_alive()]


@dataclass
class PlayerState:
    name: str
    roster: List[str] = field(default_factory=list)  # available fish names
    team: Optional[Team] = None
    score: int = 0

    def reset_roster(self):
        self.roster = FISH_NAMES.copy()


@dataclass
class GameState:
    players: List[PlayerState]
    round_no: int = 1
    turn_player: int = 0

    def team_of(self, fish: Fish) -> Team:
        for p in self.players:
            if p.team and fish in p.team.fish:
                return p.team
        raise ValueError("fish not found")

    def other_team_of(self, fish: Fish) -> Team:
        for p in self.players:
            if p.team and fish in p.team.fish:
                other = self.players[1] if p is self.players[0] else self.players[0]
                if other.team is None:
                    raise ValueError("other team missing")
                return other.team
        raise ValueError("fish not found")

    # Placeholder chooser functions; overridden by demo / LLM drivers
    def choose_teammate(self, actor_idx: int, n: int) -> Optional[Fish]:
        return None

    def choose_enemy(self, actor_idx: int, n: int) -> Optional[Fish]:
        return None


# ---------------------------------------------------------------------------
# Game setup
# ---------------------------------------------------------------------------

class Game:
    def __init__(self, player_names: Tuple[str, str]):
        self.state = GameState(players=[PlayerState(player_names[0]), PlayerState(player_names[1])])
        for p in self.state.players:
            p.reset_roster()

    # ------------------------------------------------------------------
    # Selection phase
    # ------------------------------------------------------------------
    def select_team(self, player_idx: int, fish_selection: List[str], mimic_choice: Optional[str] = None) -> None:
        p = self.state.players[player_idx]
        p.team = Team([create_fish(name) for name in fish_selection])
        # handle mimic fish copying
        for f in p.team.fish:
            f.reset()
        if mimic_choice:
            for f in p.team.fish:
                if isinstance(f, MimicFish):
                    template = create_fish(mimic_choice)
                    f.copy_from(template)
                    break
        # remove used fish from roster
        for name in fish_selection:
            if name in p.roster:
                p.roster.remove(name)

    # ------------------------------------------------------------------
    # Prompt generation for LLM decisions
    # ------------------------------------------------------------------
    def prompt_for_player(self, player_idx: int) -> str:
        p = self.state.players[player_idx]
        enemy = self.state.players[1 - player_idx]
        lines = [f"Round {self.state.round_no} - Your turn, {p.name}"]
        lines.append("Your team:")
        for idx, f in enumerate(p.team.fish):
            status = "DEAD" if not f.is_alive() else f"HP {f.hp} ATK {f.atk}"
            lines.append(f"  {idx}: {f.name if f.revealed else 'Hidden'} - {status}")
        lines.append("Enemy team:")
        for idx, f in enumerate(enemy.team.fish):
            name = f.name if f.revealed else "Hidden"
            status = "DEAD" if not f.is_alive() else f"HP {f.hp}"
            lines.append(f"  {idx}: {name} - {status}")
        lines.append("\nYou may optionally assert the identity of one hidden enemy fish using:")
        lines.append("ASSERT <enemy_index> <Fish Name> or type SKIP to skip assertion.")
        lines.append("After assertion (or skipping) choose an action:"
                     " ACT <your_fish_index> NORMAL <enemy_index>"
                     " or ACT <your_fish_index> ACTIVE [<target_index>]")
        lines.append("Fish names: " + ", ".join(FISH_NAMES))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Core gameplay turns
    # ------------------------------------------------------------------
    def perform_assertion(self, player_idx: int, enemy_index: int, guess: str) -> str:
        enemy_team = self.state.players[1 - player_idx].team
        fish = enemy_team.fish[enemy_index]
        if not fish.is_alive() or fish.revealed:
            return "Invalid assertion target."
        if fish.name == guess:
            fish.revealed = True
            for f in enemy_team.fish:
                if f.is_alive():
                    f.take_damage(50, None, direct=False, game=self.state)
            return f"Assertion success! Enemy {guess} revealed."
        else:
            own_team = self.state.players[player_idx].team
            for f in own_team.fish:
                if f.is_alive():
                    f.take_damage(50, None, direct=False, game=self.state)
            return "Assertion failed! Your team loses 50 HP each."

    def perform_action(self, player_idx: int, fish_index: int, action: str,
                       target_index: Optional[int] = None) -> str:
        team = self.state.players[player_idx].team
        actor = team.fish[fish_index]
        if not actor.is_alive():
            return "Selected fish is dead.".strip()
        enemy_team = self.state.players[1 - player_idx].team

        if action == "NORMAL":
            if target_index is None:
                return "Normal attack requires enemy target."
            target = enemy_team.fish[target_index]
            actor.normal_attack(target, self.state)
            return f"{actor.name} attacked enemy position {target_index}."
        elif action == "ACTIVE":
            self.state.choose_teammate = lambda idx, n: team.fish[target_index] if target_index is not None and 0 <= target_index < n else None
            self.state.choose_enemy = lambda idx, n: enemy_team.fish[target_index] if target_index is not None and 0 <= target_index < n else None
            actor.active(self.state, fish_index)
            return f"{actor.name} used active skill."
        else:
            return "Unknown action."

    # ------------------------------------------------------------------
    # Round resolution and tiebreakers
    # ------------------------------------------------------------------
    def round_over(self) -> Optional[int]:
        p0_alive = any(f.is_alive() for f in self.state.players[0].team.fish)
        p1_alive = any(f.is_alive() for f in self.state.players[1].team.fish)
        if p0_alive and not p1_alive:
            return 0
        if p1_alive and not p0_alive:
            return 1
        return None

