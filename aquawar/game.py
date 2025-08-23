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
    game_turn: int = 0  # Increments on every LLM invocation attempt
    player_turn: int = 1  # Increments when both players complete assertion+action phases
    phase: str = "assertion"  # "assertion" or "action"
    current_player: int = 1  # Who needs to make a move right now (1 or 2)
    # max_tries: int = 3  # Maximum retry attempts for invalid moves

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
    current_turn_damage: Dict[str, int]  # Track damage for current turn
    evaluation: Dict[str, Any]  # Cumulative evaluation metrics for analysis
    debug: bool = False  # Debug flag for detailed logging
    
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if self.debug:
            print(f"[GAME DEBUG] {message}")
    
    # def __init__(self, player_names: Tuple[str, str], debug: bool = False, max_tries: int = 3):
    def __init__(self, player_names: Tuple[str, str], debug: bool = False):
        # self.state = GameState(players=[PlayerState(player_names[0]), PlayerState(player_names[1])], max_tries=max_tries)
        self.state = GameState(players=[PlayerState(player_names[0]), PlayerState(player_names[1])])
        self.state.current_player = 1  # Player 1 starts first
        self.history = []  # List[Dict] to track turn metadata
        self.current_turn_damage = {"dealt": 0, "taken": 0}  # Track damage for current turn
        self.evaluation = self._initialize_evaluation()  # Initialize evaluation metrics
        self.debug = debug  # Set debug flag
        print(f"=== Game initialized: {player_names[0]} vs {player_names[1]} (Debug mode: {self.debug}) ===")
        for p in self.state.players:
            p.reset_roster()

    def _initialize_evaluation(self) -> Dict[str, Any]:
        """Initialize the evaluation tracking structure."""
        return {
            "players": {
                "1": {
                    "current_hp": 1600,  # 4 fish * 400 HP each
                    "damage_dealt": 0,
                    "damage_taken": 0,
                    "assertions": {
                        "true": 0,
                        "false": 0,
                        "skipped": 0
                    },
                    "invalid_moves": {
                        "total": 0,
                        "by_type": {
                            "invalid_response": 0,   # Tool not called properly, malformed JSON
                            "invalid_parameter": 0,  # Missing/invalid parameters
                            "invalid_action": 0      # Game logic errors, exceptions
                        }
                    }
                },
                "2": {
                    "current_hp": 1600,  # 4 fish * 400 HP each
                    "damage_dealt": 0,
                    "damage_taken": 0,
                    "assertions": {
                        "true": 0,
                        "false": 0,
                        "skipped": 0
                    },
                    "invalid_moves": {
                        "total": 0,
                        "by_type": {
                            "invalid_response": 0,   # Tool not called properly, malformed JSON
                            "invalid_parameter": 0,  # Missing/invalid parameters
                            "invalid_action": 0      # Game logic errors, exceptions
                        }
                    }
                }
            },
            "game_status": "ongoing"  # "completed", "ongoing", "timeout", "error"
        }
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
        
        # Switch to next player after successful team selection
        if self.state.current_player == 1:
            self.state.current_player = 2
        elif self.state.current_player == 2:
            # Both players have selected teams, start gameplay with player 1
            self.state.current_player = 1

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
        lines = [f"== CURRENT STATE - Round {self.state.round_no}, Turn {self.state.game_turn} =="]
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



    # ------------------------------------------------------------------
    # Core gameplay turns
    # ------------------------------------------------------------------
    def perform_assertion(self, player_idx: int, enemy_index: int, guess: str) -> str:
        """Perform an assertion on an enemy fish."""
        # Reset damage tracking for new phase
        self.reset_turn_damage()
        
        enemy_team = self.state.players[1 - player_idx].team
        if enemy_team is None:
            return "Enemy team not initialized."
        
        if enemy_index < 0 or enemy_index >= len(enemy_team.fish):
            return f"Invalid enemy index: {enemy_index}"
        
        fish = enemy_team.fish[enemy_index]
        
        if fish.name == guess:
            fish.revealed = True
            # Track damage dealt to all enemy fish (this counts as damage dealt by current player)
            for f in enemy_team.fish:
                if f.is_alive():
                    damage_applied = f.take_damage(50, None, direct=False, game=self.state)
                    self.track_damage_dealt(damage_applied)
            result = f"Correct! {fish.name} revealed and all enemy fish take 50 HP damage."
            self.state.move_history.append(MoveRecord(player_idx, self.state.game_turn, "assertion", f"Successful assertion: {guess}"))
            
            # Update evaluation: successful assertion
            self._update_evaluation_assertion(player_idx, "true")
        else:
            self._debug_log(f"Assertion failed - applying 50 HP damage to player {player_idx}'s fish")
            player_team = self.state.players[player_idx].team
            if player_team:
                # Track damage taken by player's own fish (this counts as damage taken by current player)
                for i, f in enumerate(player_team.fish):
                    if f.is_alive():
                        self._debug_log(f"Applying damage to fish {i}: {f.name} (HP: {f.hp})")
                        damage_applied = f.take_damage(50, None, direct=False, game=self.state)
                        self._debug_log(f"Damage applied: {damage_applied}, new HP: {f.hp}")
                        self.track_damage_taken(damage_applied)
            result = f"Wrong! {guess} was incorrect, all your fish take 50 HP damage."
            self.state.move_history.append(MoveRecord(player_idx, self.state.game_turn, "assertion", f"Failed assertion: guessed {guess}"))
            self._debug_log(f"Assertion failure processing complete")
            
            # Update evaluation: failed assertion
            self._update_evaluation_assertion(player_idx, "false")
        
        # Update evaluation: cumulative damage and current HP
        self._debug_log("Updating evaluation metrics")
        self._update_evaluation_damage(player_idx, self.current_turn_damage["dealt"], self.current_turn_damage["taken"])
        self._update_evaluation_hp()
        
        # Move to action phase (turn counter will be incremented after action phase)
        self._debug_log("Moving to action phase")
        self.state.phase = "action"
        self._debug_log(f"Phase transition complete: assertion -> action")
        return result

    def skip_assertion(self, player_idx: int) -> str:
        """Skip the assertion phase and move to action phase."""
        # Reset damage tracking for new phase
        self.reset_turn_damage()
        
        self.state.phase = "action"
        self.state.move_history.append(MoveRecord(player_idx, self.state.game_turn, "assertion", "Skipped assertion"))
        
        # Update evaluation: skipped assertion
        self._update_evaluation_assertion(player_idx, "skipped")
        
        return "Assertion phase skipped"

    def perform_action(self, player_idx: int, fish_index: int, action: str,
                       target_index: Optional[int] = None) -> str:
        self._debug_log(f"perform_action called: player_idx={player_idx}, fish_index={fish_index}, action={action}, target_index={target_index}")
        
        # Start tracking damage for this action if not already started
        if not hasattr(self, 'current_turn_damage'):
            self.reset_turn_damage()
        
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

        self._debug_log(f"perform_action: actor={actor.name}, enemy_team size={len(enemy_team.fish)}")

        # Record HP before action to track damage
        enemy_hp_before = {i: f.hp for i, f in enumerate(enemy_team.fish)}
        team_hp_before = {i: f.hp for i, f in enumerate(team.fish)}

        if action == "NORMAL":
            self._debug_log(f"perform_action: processing NORMAL attack")
            if target_index is None:
                return "Normal attack requires enemy target."
            if target_index >= len(enemy_team.fish):
                return "Invalid enemy target index."
            target = enemy_team.fish[target_index]
            self._debug_log(f"perform_action: about to call {actor.name}.normal_attack({target.name})")
            try:
                actor.normal_attack(target, self.state)
                self._debug_log(f"perform_action: normal_attack completed")
            except Exception as e:
                self._debug_log(f"ERROR in normal_attack: {e} (type: {type(e).__name__})")
                raise
            result = f"{actor.name} attacked enemy position {target_index}."
            self.state.move_history.append(MoveRecord(player_idx, self.state.game_turn, "action", f"{actor.name} normal attack on enemy {target_index}"))
        elif action == "ACTIVE":
            self._debug_log(f"perform_action: processing ACTIVE skill")
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
            self._debug_log(f"perform_action: about to call {actor.name}.active()")
            try:
                actor.active(self.state, fish_index)
                self._debug_log(f"perform_action: active skill completed")
            except Exception as e:
                self._debug_log(f"ERROR in active skill: {e} (type: {type(e).__name__})")
                raise
            result = f"{actor.name} used active skill."
            target_desc = f" on {target_index}" if target_index is not None else ""
            self.state.move_history.append(MoveRecord(player_idx, self.state.game_turn, "action", f"{actor.name} active skill{target_desc}"))
        else:
            return "Unknown action."
        
        # Calculate damage dealt and taken
        for i, f in enumerate(enemy_team.fish):
            damage_dealt = enemy_hp_before[i] - f.hp
            if damage_dealt > 0:
                self.track_damage_dealt(damage_dealt)
        
        for i, f in enumerate(team.fish):
            damage_taken = team_hp_before[i] - f.hp
            if damage_taken > 0:
                self.track_damage_taken(damage_taken)
        
        # Update evaluation: cumulative damage and current HP
        self._update_evaluation_damage(player_idx, self.current_turn_damage["dealt"], self.current_turn_damage["taken"])
        self._update_evaluation_hp()
        
        # Complete the turn: switch to next player and reset to assertion phase ONLY on successful action
        self.state.turn_player = 1 - self.state.turn_player
        self.state.phase = "assertion"
        
        # Switch current_player only after successful action
        self.state.current_player = 1 if self.state.current_player == 2 else 2
        
        # Increment player turn when both players have completed assertion+action
        if self.state.turn_player == 0:  # Back to player 1, so both players completed their turns
            self.state.player_turn += 1
        
        return result

    # ------------------------------------------------------------------
    # Save/Load functionality
    # ------------------------------------------------------------------
    def save_game(self, filepath: str, players_info: Optional[Dict[str, Any]] = None) -> None:
        """Save the current game state to a file.
        
        Args:
            filepath: Path to save the game
            players_info: Optional dictionary with player information in format:
                         {"1": [{"name": str, "model": str, "temperature": float, "top_p": float}],
                          "2": [{"name": str, "model": str, "temperature": float, "top_p": float}]}
        """
        save_data = {
            'state': self._serialize_state(),
            'history': getattr(self, 'history', []),  # Default empty if not present
            'evaluation': getattr(self, 'evaluation', self._initialize_evaluation())  # Include evaluation data
        }
        
        # Add players info if provided
        if players_info is not None:
            save_data['players'] = players_info
        
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
        
        # Handle history field (default to empty for older saves)
        game.history = save_data.get('history', [])
        
        # Handle current_turn_damage field (backward compatibility with old saves)
        game.current_turn_damage = save_data.get('current_turn_damage', {"dealt": 0, "taken": 0})
        
        # Handle evaluation field (backward compatibility with old saves)
        if hasattr(game, '_initialize_evaluation'):
            game.evaluation = save_data.get('evaluation', game._initialize_evaluation())
        else:
            # Fallback for when method isn't available during deserialization
            game.evaluation = save_data.get('evaluation', {
                "players": {
                    "1": {"current_hp": 1600, "damage_dealt": 0, "damage_taken": 0, 
                          "assertions": {"true": 0, "false": 0, "skipped": 0}, 
                          "invalid_moves": {"total": 0, "by_type": {"invalid_response": 0, "invalid_parameter": 0, "invalid_action": 0}}},
                    "2": {"current_hp": 1600, "damage_dealt": 0, "damage_taken": 0, 
                          "assertions": {"true": 0, "false": 0, "skipped": 0}, 
                          "invalid_moves": {"total": 0, "by_type": {"invalid_response": 0, "invalid_parameter": 0, "invalid_action": 0}}}
                },
                "game_status": "ongoing"
            })
        
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
            'game_turn': self.state.game_turn,
            'player_turn': self.state.player_turn,
            'phase': self.state.phase,
            'current_player': self.state.current_player,
            # 'max_tries': self.state.max_tries
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
            game_turn=state_data['game_turn'],
            player_turn=state_data.get('player_turn', 1),
            phase=state_data.get('phase', 'assertion'),  # Default to assertion for backward compatibility
            current_player=state_data.get('current_player', 1),  # Default to player 1 for backward compatibility
            # max_tries=state_data.get('max_tries', 3)  # Default to 3 for backward compatibility
        )

    # ------------------------------------------------------------------
    # Evaluation tracking
    # ------------------------------------------------------------------
    def _update_evaluation_hp(self) -> None:
        """Update current HP for both players in evaluation."""
        for player_idx, player_state in enumerate(self.state.players):
            player_key = str(player_idx + 1)
            if player_state.team:
                current_hp = sum(f.hp for f in player_state.team.fish if f.is_alive())
                self.evaluation["players"][player_key]["current_hp"] = current_hp
    
    def _update_evaluation_damage(self, player_idx: int, damage_dealt: int, damage_taken: int) -> None:
        """Update cumulative damage for a player in evaluation."""
        player_key = str(player_idx + 1)
        self.evaluation["players"][player_key]["damage_dealt"] += damage_dealt
        self.evaluation["players"][player_key]["damage_taken"] += damage_taken
    
    def _update_evaluation_assertion(self, player_idx: int, assertion_type: str) -> None:
        """Update assertion count for a player in evaluation.
        
        Args:
            player_idx: Player index (0 or 1)
            assertion_type: "true", "false", or "skipped"
        """
        player_key = str(player_idx + 1)
        if assertion_type in ["true", "false", "skipped"]:
            self.evaluation["players"][player_key]["assertions"][assertion_type] += 1
    
    def _update_evaluation_invalid_move(self, player_idx: int, invalid_type: str) -> None:
        """Update invalid move count for a player in evaluation.
        
        Args:
            player_idx: Player index (0 or 1) 
            invalid_type: "invalid_response", "invalid_parameter", or "invalid_action"
        """
        player_key = str(player_idx + 1)
        if invalid_type in ["invalid_response", "invalid_parameter", "invalid_action"]:
            self.evaluation["players"][player_key]["invalid_moves"]["total"] += 1
            self.evaluation["players"][player_key]["invalid_moves"]["by_type"][invalid_type] += 1
    
    def _update_evaluation_game_status(self, status: str) -> None:
        """Update game status in evaluation.
        
        Args:
            status: "completed", "ongoing", "timeout", or "error"
        """
        if status in ["completed", "ongoing", "timeout", "error"]:
            self.evaluation["game_status"] = status

    # ------------------------------------------------------------------
    # History tracking
    # ------------------------------------------------------------------
    def reset_turn_damage(self) -> None:
        """Reset damage tracking for a new turn."""
        self.current_turn_damage = {"dealt": 0, "taken": 0}
    
    def track_damage_dealt(self, amount: int) -> None:
        """Track damage dealt by the current player this turn."""
        self.current_turn_damage["dealt"] += amount
    
    def track_damage_taken(self, amount: int) -> None:
        """Track damage taken by the current player this turn."""
        self.current_turn_damage["taken"] += amount
    
    
    def add_history_entry_unified(self, player_index: int, input_messages: List[Any], response: Dict[str, Any], 
                                 valid: bool, move: str, damage_dealt: int = 0, damage_taken: int = 0, 
                                 attempt: int = 1, max_attempts: int = 1, error_details: Optional[Dict] = None) -> None:
        """Unified history entry function that fixes double increment and message mutation bugs."""
        
        self._debug_log(f"add_history_entry_unified called: player_index={player_index}, valid={valid}, move={move[:25]}..., attempt={attempt}/{max_attempts}")
        # Fix double increment: use player_index directly (0-based), convert to 1-based for history
        player_num = player_index + 1  # Convert 0-based to 1-based for history
        
        # Track invalid moves in evaluation if move was invalid
        if not valid:
            self._track_invalid_move_from_move_description(player_index, move)
        
        # Create copy of input messages to prevent mutation across entries
        messages_copy = [msg.copy() if isinstance(msg, dict) else msg for msg in input_messages]
        
        # Build history entry with consistent structure
        history_entry = {
            "player": player_num,  # 1 or 2 (fixed - no double increment)
            "game_turn": self.state.game_turn,
            "player_turn": self.state.player_turn,
            "input_messages": messages_copy,  # Prevent shared object mutation
            "response": response,  # Raw LLM response object
            "valid": valid,
            "move": move,
            "damage_dealt": damage_dealt,
            "damage_taken": damage_taken,
            "attempt": attempt,
            "max_attempts": max_attempts
        }
        
        # Add error details if provided (for failed attempts)
        if error_details:
            history_entry["error_details"] = error_details
        self._debug_log(f"Adding history entry: ({len(self.history)} -> {len(self.history) + 1})")
        
        self.history.append(history_entry)
        

    def _track_invalid_move_from_move_description(self, player_idx: int, move_description: str) -> None:
        """Classify and track invalid move based on move description."""
        # Classify the invalid move type based on common error patterns
        if any(keyword in move_description.lower() for keyword in ["no tool call", "malformed", "wrong tool", "invalid response"]):
            invalid_type = "invalid_response"
        elif any(keyword in move_description.lower() for keyword in ["missing", "invalid enemy index", "invalid fish name", "invalid argument", "invalid parameter"]):
            invalid_type = "invalid_parameter"
        else:
            # Default to invalid_action for server errors, exceptions, game logic errors
            invalid_type = "invalid_action"
        
        self._update_evaluation_invalid_move(player_idx, invalid_type)
    
    def increment_game_turn(self) -> None:
        """Increment game turn counter for any action/assertion attempt."""
        self._debug_log(f"Incrementing game turn: {self.state.game_turn} -> {self.state.game_turn + 1}")
        self.state.game_turn += 1

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

