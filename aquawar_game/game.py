"""Core game logic for Aquawar.

The :class:`Game` class coordinates rounds, assertions and actions.  It is
suitable both for usage by LLM agents (who receive textual prompts describing
only the current state) and for an interactive CLI demo (see ``demo.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import random
import json
import pickle
from pathlib import Path

from .fish import create_fish, Fish, MimicFish, FISH_FACTORIES

FISH_NAMES = list(FISH_FACTORIES.keys())


# ---------------------------------------------------------------------------
# Utility structures
# ---------------------------------------------------------------------------

@dataclass
class MoveRecord:
    player_idx: int
    turn: int
    move_type: str  # "assertion", "action"
    details: str    # human-readable description

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
    damage_dealt: int = 0  # Track total damage dealt throughout the round

    def reset_roster(self):
        self.roster = FISH_NAMES.copy()


@dataclass
class GameState:
    players: List[PlayerState]
    round_no: int = 1
    turn_player: int = 0
    move_history: List[MoveRecord] = field(default_factory=list)
    turn_count: int = 0
    phase: str = "assertion"  # "assertion" or "action"

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
    history: List[Dict[str, Any]]  # Track turn metadata
    
    def __init__(self, player_names: Tuple[str, str]):
        self.state = GameState(players=[PlayerState(player_names[0]), PlayerState(player_names[1])])
        self.history = []  # List[Dict] to track turn metadata
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
    def get_general_description(self) -> str:
        """General game overview and rules."""
        return """== AQUAWAR GAME OVERVIEW ==
Aquawar is a turn-based strategy game. Best-of-three rounds - first to win 2 rounds wins.

CORE MECHANICS:
- Each round: secretly select 4 fish from 12 available
- All fish start with 400 HP, 100 ATK
- Hidden identities: your fish are hidden from opponent until revealed by assertion
- Turn structure: optional assertion phase, then action phase

ASSERTION MECHANICS:
- Guess identity of hidden enemy fish
- Success: enemy fish revealed, all enemy fish lose 50 HP
- Failure: all your fish lose 50 HP
- Special: Mimic Fish must be guessed as "Mimic Fish", not the copied fish

ACTIONS:
- Normal Attack: deals 50% of ATK damage (50 damage at base ATK)
- Active Skill: unique ability per fish type

WIN CONDITIONS:
- Eliminate all enemy fish
- Turn limit (64 turns): decided by fish count, then total HP, then highest single HP
"""

    def get_fish_descriptions(self) -> str:
        """Detailed descriptions of all fish abilities."""
        return """== FISH ROSTER ==
All fish: 400 HP, 100 ATK base

1. Archerfish
   Passive: When teammate HP < 30% after attack, deal 30 damage to attacker
   Active: Attack all enemies for 35% ATK damage each

2. Pufferfish
   Passive: When teammate HP < 30% after attack, deal 30 damage to attacker  
   Active: Deal 50 damage to teammate, gain 70 ATK permanently

3. Electric Eel
   Passive: Take 70% damage, split 30% among teammates. Gain 20 ATK per 200 total damage taken
   Active: Attack all enemies for 35% ATK damage each

4. Sunfish
   Passive: Take 70% damage, split 30% among teammates. Gain 20 ATK per 200 total damage taken
   Active: Deal 50 damage to teammate, gain 70 ATK permanently

5. Sea Wolf
   Passive: 30% dodge chance
   Active: Deal 120 critical damage to single enemy

6. Manta Ray
   Passive: 30% dodge chance
   Active: Give teammate 70% damage reduction (next attack), gain 20 ATK

7. Sea Turtle
   Passive: Start with 3 shields (block damage), then 30% dodge when shields gone
   Active: Give teammate heal 20 HP (next damage), FIRST 3 USES ONLY also deal 120 critical damage

8. Octopus
   Passive: Heal 20 HP after taking damage
   Active: Give teammate 70% damage reduction (next attack), gain 20 ATK

9. Great White Shark
   Passive: Heal 20 HP after taking damage
   Active: Attack lowest HP enemy for 120% ATK (140% if target < 40% HP)

10. Hammerhead Shark
    Passive: Heal 20 HP after taking damage, gain 15 ATK when HP < 20%, explode for 40 damage when killed
    Active: Attack lowest HP enemy for 120% ATK (140% if target < 40% HP)

11. Clownfish
    Passive: Deal 30 damage to attacker when HP < 30% after attack
    Active: Give teammate damage sharing (take 70%, split 30%), FIRST 3 USES ONLY also attack all enemies for 35% ATK

12. Mimic Fish
    Passive/Active: Copies another fish's abilities (choose during selection)
"""

    def get_assertion_explanation(self) -> str:
        """Explanation of assertion mechanics."""
        return """== ASSERTION RULES ==
- Target: one hidden, living enemy fish
- Correct guess: fish revealed, all enemy fish lose 50 HP
- Wrong guess: all your fish lose 50 HP
- HP loss is NOT damage (won't trigger damage-related effects)
- Mimic Fish: must guess "Mimic Fish", not the copied fish identity
"""

    def get_past_moves(self, player_idx: int) -> str:
        """Brief summary of past moves this round."""
        if not self.state.move_history:
            return "== ROUND HISTORY ==\nNo moves yet this round."
        
        lines = ["== ROUND HISTORY =="]
        player_assertions = [m for m in self.state.move_history if m.player_idx == player_idx and m.move_type == "assertion"]
        opponent_actions = [m for m in self.state.move_history if m.player_idx != player_idx and m.move_type == "action"]
        
        if player_assertions:
            lines.append("Your assertions:")
            for move in player_assertions[-3:]:  # Last 3 assertions
                lines.append(f"  Turn {move.turn}: {move.details}")
        
        if opponent_actions:
            lines.append("Opponent actions:")
            for move in opponent_actions[-3:]:  # Last 3 actions
                lines.append(f"  Turn {move.turn}: {move.details}")
                
        return "\n".join(lines)

    def get_current_state(self, player_idx: int) -> str:
        """Current game state with revealed fish identities."""
        p = self.state.players[player_idx]
        enemy = self.state.players[1 - player_idx]
        lines = [f"== CURRENT STATE - Round {self.state.round_no}, Turn {self.state.turn_count} =="]
        lines.append("Your team:")
        if p.team is not None:
            for idx, f in enumerate(p.team.fish):
                status = "DEAD" if not f.is_alive() else f"HP {f.hp} ATK {f.atk}"
                lines.append(f"  {idx}: {f.name} - {status}")
        else:
            lines.append("  No team selected yet")
        lines.append("Enemy team:")
        if enemy.team is not None:
            for idx, f in enumerate(enemy.team.fish):
                name = f.name if f.revealed else "Hidden"
                status = "DEAD" if not f.is_alive() else f"HP {f.hp}"
                lines.append(f"  {idx}: {name} - {status}")
        else:
            lines.append("  No team selected yet")
        return "\n".join(lines)

    def prompt_for_selection(self, player_idx: int) -> str:
        """Prompt for fish selection phase."""
        p = self.state.players[player_idx]
        lines = [self.get_general_description()]
        lines.append("")
        lines.append(self.get_fish_descriptions())
        lines.append("")
        lines.append(f"== SELECTION PHASE - Round {self.state.round_no} ==")
        lines.append(f"{p.name}: Select 4 fish from the available roster:")
        
        for idx, fish_name in enumerate(p.roster):
            lines.append(f"  {idx}: {fish_name}")
        
        lines.append("\nReturn your selection as a list of 4 numbers (e.g., [0, 3, 7, 11])")
        lines.append("If you select Mimic Fish, you must also specify which fish to copy.")
        return "\n".join(lines)

    def prompt_for_assertion(self, player_idx: int) -> str:
        """Prompt for assertion phase."""
        lines = [self.get_general_description()]
        lines.append("")
        lines.append(self.get_fish_descriptions()) 
        lines.append("")
        lines.append(self.get_past_moves(player_idx))
        lines.append("")
        lines.append(self.get_current_state(player_idx))
        lines.append("")
        lines.append(self.get_assertion_explanation())
        lines.append("")
        lines.append("== ASSERTION PHASE ==")
        lines.append("You may assert the identity of one hidden enemy fish.")
        lines.append("Command: ASSERT <enemy_index> <Fish Name> or SKIP")
        return "\n".join(lines)

    def prompt_for_action(self, player_idx: int) -> str:
        """Prompt for action phase."""
        lines = [self.get_general_description()]
        lines.append("")
        lines.append(self.get_fish_descriptions())
        lines.append("")
        lines.append(self.get_current_state(player_idx))
        lines.append("")
        lines.append("== ACTION PHASE ==")
        lines.append("Choose an action for one of your living fish:")
        lines.append("  ACT <your_fish_index> NORMAL <enemy_index>  - Normal attack")
        lines.append("  ACT <your_fish_index> ACTIVE [<target_index>]  - Use active skill")
        return "\n".join(lines)

    def prompt_for_player(self, player_idx: int) -> str:
        """Legacy prompt - use the new phase-specific prompts instead."""
        return self.prompt_for_assertion(player_idx)

    # ------------------------------------------------------------------
    # Core gameplay turns
    # ------------------------------------------------------------------
    def perform_assertion(self, player_idx: int, enemy_index: int, guess: str) -> str:
        self.state.turn_count += 1
        enemy_team = self.state.players[1 - player_idx].team
        if enemy_team is None:
            return "Enemy has no team selected yet."
        
        if enemy_index >= len(enemy_team.fish):
            return "Invalid enemy index."
            
        fish = enemy_team.fish[enemy_index]
        if not fish.is_alive() or fish.revealed:
            return "Invalid assertion target."
        
        if fish.name == guess:
            fish.revealed = True
            for f in enemy_team.fish:
                if f.is_alive():
                    f.take_damage(50, None, direct=False, game=self.state)
            # Track damage dealt on successful assertion
            for f in enemy_team.fish:
                if f.is_alive() and f.hp <= (400-50):  # Fish took damage
                    self.state.players[player_idx].damage_dealt += 50
            result = f"Assertion success! Enemy {guess} revealed."
            self.state.move_history.append(MoveRecord(player_idx, self.state.turn_count, "assertion", f"Successfully asserted {guess}"))
        else:
            own_team = self.state.players[player_idx].team
            if own_team is not None:
                for f in own_team.fish:
                    if f.is_alive():
                        f.take_damage(50, None, direct=False, game=self.state)
                        # Track assertion damage
                        self.state.players[1-player_idx].damage_dealt += 50
            result = "Assertion failed! Your team loses 50 HP each."
            self.state.move_history.append(MoveRecord(player_idx, self.state.turn_count, "assertion", f"Failed assertion: guessed {guess}"))
        
        # Move to action phase
        self.state.phase = "action"
        return result

    def skip_assertion(self, player_idx: int) -> str:
        """Skip the assertion phase and move to action phase."""
        self.state.phase = "action"
        self.state.move_history.append(MoveRecord(player_idx, self.state.turn_count, "assertion", "Skipped assertion"))
        return "Assertion phase skipped"

    def perform_action(self, player_idx: int, fish_index: int, action: str,
                       target_index: Optional[int] = None) -> str:
        team = self.state.players[player_idx].team
        if team is None:
            return "No team selected yet."
        
        if fish_index >= len(team.fish):
            return "Invalid fish index."
            
        actor = team.fish[fish_index]
        if not actor.is_alive():
            return "Selected fish is dead.".strip()
        
        enemy_team = self.state.players[1 - player_idx].team
        if enemy_team is None:
            return "Enemy has no team selected yet."

        if action == "NORMAL":
            if target_index is None:
                return "Normal attack requires enemy target."
            if target_index >= len(enemy_team.fish):
                return "Invalid enemy target index."
            target = enemy_team.fish[target_index]
            actor.normal_attack(target, self.state)
            result = f"{actor.name} attacked enemy position {target_index}."
            self.state.move_history.append(MoveRecord(player_idx, self.state.turn_count, "action", f"{actor.name} normal attack on enemy {target_index}"))
        elif action == "ACTIVE":
            # Set up target selection functions for the active skill
            def choose_teammate_func(actor_idx: int, n: int) -> Optional[Fish]:
                if target_index is not None and 0 <= target_index < len(team.fish):
                    return team.fish[target_index]
                return None
            
            def choose_enemy_func(actor_idx: int, n: int) -> Optional[Fish]:
                if target_index is not None and 0 <= target_index < len(enemy_team.fish):
                    return enemy_team.fish[target_index]
                return None
            
            self.state.choose_teammate = choose_teammate_func
            self.state.choose_enemy = choose_enemy_func
            actor.active(self.state, fish_index)
            result = f"{actor.name} used active skill."
            target_desc = f" on {target_index}" if target_index is not None else ""
            self.state.move_history.append(MoveRecord(player_idx, self.state.turn_count, "action", f"{actor.name} active skill{target_desc}"))
        else:
            return "Unknown action."
        
        # Switch to next player and reset to assertion phase
        self.state.turn_player = 1 - self.state.turn_player
        self.state.phase = "assertion"
        return result

    # ------------------------------------------------------------------
    # Save/Load functionality
    # ------------------------------------------------------------------
    def save_game(self, filepath: str) -> None:
        """Save the current game state to a file."""
        save_data = {
            'state': self._serialize_state(),
            'history': getattr(self, 'history', []),  # Default empty if not present
            'version': '1.2.0'  # Version tracks save format changes for backward compatibility
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(save_data, f)
    
    @classmethod
    def load_game(cls, filepath: str) -> 'Game':
        """Load a game state from a file."""
        with open(filepath, 'rb') as f:
            save_data = pickle.load(f)
        
        game = cls.__new__(cls)  # Create instance without calling __init__
        game._deserialize_state(save_data['state'])
        
        # Handle history field (added in v1.1, default to empty for older saves)
        game.history = save_data.get('history', [])
        
        return game
    
    def _serialize_state(self) -> Dict[str, Any]:
        """Convert game state to serializable format."""
        return {
            'players': [
                {
                    'name': p.name,
                    'roster': p.roster.copy(),
                    'team': self._serialize_team(p.team) if p.team else None,
                    'score': p.score,
                    'damage_dealt': p.damage_dealt
                }
                for p in self.state.players
            ],
            'round_no': self.state.round_no,
            'turn_player': self.state.turn_player,
            'move_history': [
                {
                    'player_idx': m.player_idx,
                    'turn': m.turn,
                    'move_type': m.move_type,
                    'details': m.details
                }
                for m in self.state.move_history
            ],
            'turn_count': self.state.turn_count,
            'phase': self.state.phase
        }
    
    def _serialize_team(self, team: Team) -> Dict[str, Any]:
        """Convert team to serializable format."""
        return {
            'fish': [self._serialize_fish(f) for f in team.fish]
        }
    
    def _serialize_fish(self, fish: Fish) -> Dict[str, Any]:
        """Convert fish to serializable format."""
        return {
            'name': fish.name,
            'hp': fish.hp,
            'atk': fish.atk,
            'revealed': fish.revealed,
            'buffs': [{'kind': b.kind, 'value': b.value} for b in fish.buffs],
            'shields': fish.shields,
            'dodge_chance': fish.dodge_chance,
            'used_active_count': fish.used_active_count,
            'mimic_source': fish.mimic_source
        }
    
    def _deserialize_state(self, state_data: Dict[str, Any]) -> None:
        """Restore game state from serialized data."""
        from .fish import Buff
        
        # Recreate players
        players = []
        for p_data in state_data['players']:
            player = PlayerState(p_data['name'])
            player.roster = p_data['roster']
            player.score = p_data['score']
            player.damage_dealt = p_data.get('damage_dealt', 0)  # Default to 0 for backward compatibility
            
            if p_data['team'] is not None:
                team_fish = []
                for f_data in p_data['team']['fish']:
                    fish = create_fish(f_data['name'])
                    fish.hp = f_data['hp']
                    fish.atk = f_data['atk']
                    fish.revealed = f_data['revealed']
                    fish.buffs = [Buff(b['kind'], b['value']) for b in f_data['buffs']]
                    fish.shields = f_data['shields']
                    fish.dodge_chance = f_data['dodge_chance']
                    fish.used_active_count = f_data['used_active_count']
                    fish.mimic_source = f_data['mimic_source']
                    
                    # Handle mimic fish copying
                    if fish.mimic_source and isinstance(fish, MimicFish):
                        template = create_fish(fish.mimic_source)
                        fish.copy_from(template)
                    
                    team_fish.append(fish)
                player.team = Team(team_fish)
            else:
                player.team = None
                
            players.append(player)
        
        # Recreate move history
        move_history = []
        for m_data in state_data['move_history']:
            move_history.append(MoveRecord(
                m_data['player_idx'],
                m_data['turn'], 
                m_data['move_type'],
                m_data['details']
            ))
        
        # Create game state
        self.state = GameState(
            players=players,
            round_no=state_data['round_no'],
            turn_player=state_data['turn_player'],
            move_history=move_history,
            turn_count=state_data['turn_count'],
            phase=state_data.get('phase', 'assertion')  # Default to assertion for backward compatibility
        )

    # ------------------------------------------------------------------
    # History tracking
    # ------------------------------------------------------------------
    def add_history_entry(self, player: int, prompt: str, response: str, validity: str = "valid") -> None:
        """Add turn metadata to history."""
        self.history.append({
            "turn": self.state.turn_count,
            "player": player + 1,  # Convert to 1-based for readability
            "prompt": prompt,
            "response": response,
            "validity": validity
        })
    
    def track_damage_dealt(self, source_fish: Optional[Fish], damage: int) -> None:
        """Track damage dealt by a player's fish."""
        if source_fish is None or damage <= 0:
            return
            
        # Find which player owns the source fish
        for i, player in enumerate(self.state.players):
            if player.team and source_fish in player.team.fish:
                player.damage_dealt += damage
                break

    # ------------------------------------------------------------------
    # Round resolution and tiebreakers
    # ------------------------------------------------------------------
    def round_over(self) -> Optional[int]:
        team0 = self.state.players[0].team
        team1 = self.state.players[1].team
        
        if team0 is None or team1 is None:
            return None
            
        p0_alive = any(f.is_alive() for f in team0.fish)
        p1_alive = any(f.is_alive() for f in team1.fish)
        if p0_alive and not p1_alive:
            return 0
        if p1_alive and not p0_alive:
            return 1
        return None

