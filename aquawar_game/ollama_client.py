"""Ollama client integration for Aquawar using Langchain.

This module provides Ollama AI integration for autonomous gameplay using Langchain's
tool calling capabilities.
"""

from __future__ import annotations

import json
from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from pydantic import BaseModel, Field

from .game import Game, FISH_NAMES
from .persistent_game import PersistentGameManager


@dataclass
class GameAction:
    """Represents a game action with validation info."""
    action_type: str
    success: bool
    message: str
    validity: str = "valid"


class SelectTeamInput(BaseModel):
    """Input for team selection tool."""
    fish_indices: List[int] = Field(description="List of 4 fish indices to select (0-11)")
    mimic_choice: Optional[str] = Field(description="Fish name for Mimic Fish to copy (if selected)", default=None)


class AssertInput(BaseModel):
    """Input for assertion tool."""
    enemy_index: int = Field(description="Index of enemy fish to assert (0-3)")
    fish_name: str = Field(description="Name of fish species to assert")


class AttackInput(BaseModel):
    """Input for normal attack action."""
    fish_index: int = Field(description="Index of your fish to act with (0-3)")
    target_index: int = Field(description="Index of enemy fish to attack (0-3)")


class ActiveSkillInput(BaseModel):
    """Input for active skill action."""
    fish_index: int = Field(description="Index of your fish to act with (0-3)")
    target_index: Optional[int] = Field(description="Target index if skill requires target", default=None)


@tool
def select_team_tool(fish_indices: List[int], mimic_choice: Optional[str] = None) -> str:
    """Select your team of 4 fish from the available roster.
    
    Args:
        fish_indices: List of 4 fish indices to select (0-11 from roster)
        mimic_choice: Fish name for Mimic Fish to copy (required if Mimic Fish selected)
    
    Returns:
        String describing the result of team selection
    """
    # This will be called by the OllamaPlayer with proper game context
    return f"Tool called: select_team with indices {fish_indices}, mimic: {mimic_choice}"


@tool
def assert_fish_tool(enemy_index: int, fish_name: str) -> str:
    """Assert the identity of a hidden enemy fish.
    
    Args:
        enemy_index: Index of the enemy fish to assert (0-3)
        fish_name: Name of the fish species you believe it is
    
    Returns:
        String describing the result of the assertion
    """
    return f"Tool called: assert_fish - enemy {enemy_index} is {fish_name}"


@tool
def skip_assertion_tool() -> str:
    """Skip the assertion phase and move directly to action phase.
    
    Returns:
        String confirming assertion was skipped
    """
    return "Tool called: skip_assertion"


@tool
def normal_attack_tool(fish_index: int, target_index: int) -> str:
    """Perform a normal attack with one of your fish.
    
    Args:
        fish_index: Index of your fish to attack with (0-3)
        target_index: Index of enemy fish to attack (0-3)
    
    Returns:
        String describing the attack result
    """
    return f"Tool called: normal_attack - fish {fish_index} attacks enemy {target_index}"


@tool
def active_skill_tool(fish_index: int, target_index: Optional[int] = None) -> str:
    """Use the active skill of one of your fish.
    
    Args:
        fish_index: Index of your fish to use skill with (0-3)
        target_index: Target index if skill requires a target (optional)
    
    Returns:
        String describing the skill usage result
    """
    return f"Tool called: active_skill - fish {fish_index} uses skill on target {target_index}"


class OllamaPlayer:
    """AI player using Ollama LLM with Langchain tool calling."""
    
    def __init__(self, name: str, model: str = "llama3.2:3b", temperature: float = 0.7):
        """Initialize Ollama player.
        
        Args:
            name: Player name
            model: Ollama model to use 
            temperature: Temperature for LLM responses
        """
        self.name = name
        self.model = model
        self.temperature = temperature
        
        # Initialize Ollama chat model with tools
        self.llm = ChatOllama(
            model=model,
            temperature=temperature,
        ).bind_tools([
            select_team_tool,
            assert_fish_tool,
            skip_assertion_tool,
            normal_attack_tool,
            active_skill_tool
        ])
        
        # Game context
        self.game: Optional[Game] = None
        self.player_index: Optional[int] = None
        
    def set_game_context(self, game: Game, player_index: int):
        """Set the game context for this player.
        
        Args:
            game: Game instance
            player_index: This player's index (0 or 1)
        """
        self.game = game
        self.player_index = player_index
    
    def get_system_message(self) -> str:
        """Get system message for the LLM."""
        return f"""You are {self.name}, an expert Aquawar player competing in a tournament.

Aquawar is a turn-based strategy game where you select 4 fish and battle against an opponent.

GAME PHASES:
1. TEAM SELECTION: Select 4 fish from 12 available (indices 0-11)
2. ASSERTION PHASE: Optionally guess hidden enemy fish identity  
3. ACTION PHASE: Attack or use active skills

KEY RULES:
- All fish start with 400 HP, 100 ATK
- Hidden identities: fish are hidden until revealed by successful assertion
- Successful assertion: enemy fish revealed, all enemy fish lose 50 HP
- Failed assertion: all your fish lose 50 HP
- Normal attack: 50% ATK damage (50 base damage)
- Active skills: unique abilities per fish type

WIN CONDITIONS:
- Eliminate all enemy fish
- If time limit reached: decided by fish count, total HP, highest single HP

You must use the provided tools to make your moves. Always think strategically about:
- Team composition and synergies
- When to assert vs skip
- Target prioritization
- Resource management

IMPORTANT: If you select Mimic Fish (index varies by roster), you MUST also specify mimic_choice parameter with the fish name you want it to copy. Available fish names are: Archerfish, Pufferfish, Electric Eel, Sunfish, Sea Wolf, Manta Ray, Sea Turtle, Octopus, Great White Shark, Hammerhead Shark, Clownfish, Mimic Fish.

Play to win!"""

    def _extract_tool_call(self, response: BaseMessage) -> Optional[Dict[str, Any]]:
        """Extract tool call from response if available."""
        try:
            # Try to access tool_calls attribute if it exists
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls and len(tool_calls) > 0:
                return tool_calls[0]
        except (AttributeError, IndexError):
            pass
        return None

    def make_team_selection(self, available_fish: List[str]) -> GameAction:
        """Make team selection using LLM tool calling.
        
        Args:
            available_fish: List of available fish names
            
        Returns:
            GameAction with selection result
        """
        if not self.game or self.player_index is None:
            return GameAction("select_team", False, "No game context set", "invalid action")
        
        prompt = self.game.prompt_for_selection(self.player_index)
        
        messages = [
            SystemMessage(content=self.get_system_message()),
            HumanMessage(content=f"{prompt}\n\nSelect your team of 4 fish using the select_team_tool. Use fish indices from the roster.\n\nRECOMMENDED STRATEGY: For this game, avoid selecting Mimic Fish (if present) to keep selection simple. Choose 4 different fish with good synergies.")
        ]
        
        response_content = ""
        try:
            response = self.llm.invoke(messages)
            response_content = str(response.content) if hasattr(response, 'content') else "No response content"
            
            tool_call = self._extract_tool_call(response)
            if not tool_call:
                return GameAction("select_team", False, "No tool call made", "invalid response")
            
            if tool_call['name'] != 'select_team_tool':
                return GameAction("select_team", False, f"Wrong tool called: {tool_call['name']}", "invalid response")
            
            args = tool_call['args']
            fish_indices = args.get('fish_indices', [])
            mimic_choice = args.get('mimic_choice')
            
            # Validate indices
            if len(fish_indices) != 4:
                return GameAction("select_team", False, "Must select exactly 4 fish", "invalid argument")
            
            for idx in fish_indices:
                if not isinstance(idx, int) or idx < 0 or idx >= len(available_fish):
                    return GameAction("select_team", False, f"Invalid fish index: {idx}", "invalid argument")
            
            # Convert indices to fish names
            fish_names = [available_fish[i] for i in fish_indices]
            
            # Check for Mimic Fish
            if "Mimic Fish" in fish_names and not mimic_choice:
                return GameAction("select_team", False, "Mimic Fish selected but no mimic choice provided", "invalid argument")
            
            # Make the selection
            self.game.select_team(self.player_index, fish_names, mimic_choice)
            
            # Track in history
            response_text = f"Selected fish indices: {fish_indices}"
            if mimic_choice:
                response_text += f", Mimic choice: {mimic_choice}"
            
            self.game.add_history_entry(self.player_index, prompt, response_text, "valid")
            
            return GameAction("select_team", True, f"Selected team: {fish_names}", "valid")
            
        except Exception as e:
            error_msg = f"Error in team selection: {e}"
            self.game.add_history_entry(self.player_index, prompt, response_content, "invalid action")
            return GameAction("select_team", False, error_msg, "invalid action")
    
    def make_assertion(self) -> GameAction:
        """Make assertion decision using LLM tool calling.
        
        Returns:
            GameAction with assertion result
        """
        if not self.game or self.player_index is None:
            return GameAction("assertion", False, "No game context set", "invalid action")
        
        prompt = self.game.prompt_for_assertion(self.player_index)
        
        messages = [
            SystemMessage(content=self.get_system_message()),
            HumanMessage(content=f"{prompt}\n\nMake your assertion decision using either assert_fish_tool or skip_assertion_tool.")
        ]
        
        response_content = ""
        try:
            response = self.llm.invoke(messages)
            response_content = str(response.content) if hasattr(response, 'content') else "No response content"
            
            tool_call = self._extract_tool_call(response)
            if not tool_call:
                return GameAction("assertion", False, "No tool call made", "invalid response")
            
            tool_name = tool_call['name']
            args = tool_call['args']
            
            if tool_name == 'skip_assertion_tool':
                result = self.game.skip_assertion(self.player_index)
                self.game.add_history_entry(self.player_index, prompt, "SKIP", "valid")
                return GameAction("assertion", True, result, "valid")
                
            elif tool_name == 'assert_fish_tool':
                enemy_index = args.get('enemy_index')
                fish_name = args.get('fish_name')
                
                if enemy_index is None or fish_name is None:
                    return GameAction("assertion", False, "Missing assertion parameters", "invalid argument")
                
                result = self.game.perform_assertion(self.player_index, enemy_index, fish_name)
                response_text = f"ASSERT {enemy_index} {fish_name}"
                self.game.add_history_entry(self.player_index, prompt, response_text, "valid")
                return GameAction("assertion", True, result, "valid")
                
            else:
                return GameAction("assertion", False, f"Wrong tool called: {tool_name}", "invalid response")
            
        except Exception as e:
            error_msg = f"Error in assertion: {e}"
            self.game.add_history_entry(self.player_index, prompt, response_content, "invalid action")
            return GameAction("assertion", False, error_msg, "invalid action")
    
    def make_action(self) -> GameAction:
        """Make action decision using LLM tool calling.
        
        Returns:
            GameAction with action result
        """
        if not self.game or self.player_index is None:
            return GameAction("action", False, "No game context set", "invalid action")
        
        prompt = self.game.prompt_for_action(self.player_index)
        
        messages = [
            SystemMessage(content=self.get_system_message()),
            HumanMessage(content=f"{prompt}\n\nMake your action using either normal_attack_tool or active_skill_tool.")
        ]
        
        response_content = ""
        try:
            response = self.llm.invoke(messages)
            response_content = str(response.content) if hasattr(response, 'content') else "No response content"
            
            tool_call = self._extract_tool_call(response)
            if not tool_call:
                return GameAction("action", False, "No tool call made", "invalid response")
            
            tool_name = tool_call['name']
            args = tool_call['args']
            
            if tool_name == 'normal_attack_tool':
                fish_index = args.get('fish_index')
                target_index = args.get('target_index')
                
                if fish_index is None or target_index is None:
                    return GameAction("action", False, "Missing attack parameters", "invalid argument")
                
                result = self.game.perform_action(self.player_index, fish_index, "NORMAL", target_index)
                response_text = f"ACT {fish_index} NORMAL {target_index}"
                self.game.add_history_entry(self.player_index, prompt, response_text, "valid")
                return GameAction("action", True, result, "valid")
                
            elif tool_name == 'active_skill_tool':
                fish_index = args.get('fish_index')
                target_index = args.get('target_index')
                
                if fish_index is None:
                    return GameAction("action", False, "Missing fish index for active skill", "invalid argument")
                
                result = self.game.perform_action(self.player_index, fish_index, "ACTIVE", target_index)
                response_text = f"ACT {fish_index} ACTIVE"
                if target_index is not None:
                    response_text += f" {target_index}"
                self.game.add_history_entry(self.player_index, prompt, response_text, "valid")
                return GameAction("action", True, result, "valid")
                
            else:
                return GameAction("action", False, f"Wrong tool called: {tool_name}", "invalid response")
            
        except Exception as e:
            error_msg = f"Error in action: {e}"
            self.game.add_history_entry(self.player_index, prompt, response_content, "invalid action")
            return GameAction("action", False, error_msg, "invalid action")


class OllamaGameManager:
    """Manages AI vs AI games using Ollama players."""
    
    def __init__(self, save_dir: str = "saves", model: str = "llama3.2:3b"):
        """Initialize the game manager.
        
        Args:
            save_dir: Directory for saving games
            model: Ollama model to use for both players
        """
        self.persistent_manager = PersistentGameManager(save_dir)
        self.model = model
        
    def create_ai_vs_ai_game(self, game_id: str, player1_name: str = "AI Player 1", 
                           player2_name: str = "AI Player 2") -> tuple[Game, OllamaPlayer, OllamaPlayer]:
        """Create a new AI vs AI game.
        
        Args:
            game_id: Unique game identifier
            player1_name: Name for player 1
            player2_name: Name for player 2
            
        Returns:
            Tuple of (game, player1, player2)
        """
        # Initialize game
        game = self.persistent_manager.initialize_new_game(game_id, (player1_name, player2_name))
        
        # Create AI players
        player1 = OllamaPlayer(player1_name, self.model)
        player2 = OllamaPlayer(player2_name, self.model)
        
        # Set game context
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        
        return game, player1, player2
    
    def run_ai_vs_ai_game(self, game_id: str, max_turns: int = 100) -> Dict[str, Any]:
        """Run a complete AI vs AI game until completion.
        
        Args:
            game_id: Game identifier
            max_turns: Maximum number of turns before forcing end
            
        Returns:
            Dictionary with game results
        """
        try:
            # Create game and players
            game, player1, player2 = self.create_ai_vs_ai_game(game_id)
            players = [player1, player2]
            
            print(f"Starting AI vs AI game: {player1.name} vs {player2.name}")
            print(f"Using model: {self.model}")
            
            # Team selection phase
            for i, player in enumerate(players):
                print(f"\n{player.name} selecting team...")
                available_fish = game.state.players[i].roster.copy()
                action = player.make_team_selection(available_fish)
                
                if not action.success:
                    return {
                        "success": False,
                        "error": f"Team selection failed for {player.name}: {action.message}",
                        "turn": 0,
                        "phase": "team_selection"
                    }
                
                print(f"✓ {action.message}")
                # Save after each team selection
                self.persistent_manager.save_game_state(game, game_id)
            
            print("\nStarting battle phase...")
            
            # Main game loop
            turn_count = 0
            while turn_count < max_turns:
                turn_count += 1
                current_player_idx = game.state.turn_player
                current_player = players[current_player_idx]
                
                print(f"\nTurn {turn_count}: {current_player.name}'s turn")
                print(f"Phase: {game.state.phase}")
                
                # Check for round over
                winner = game.round_over()
                if winner is not None:
                    winner_name = game.state.players[winner].name
                    print(f"\n🎉 Game Over! {winner_name} wins!")
                    
                    self.persistent_manager.save_game_state(game, game_id)
                    
                    return {
                        "success": True,
                        "winner": winner,
                        "winner_name": winner_name,
                        "turns": turn_count,
                        "game_id": game_id
                    }
                
                # Execute turn based on phase
                action = None
                if game.state.phase == "assertion":
                    action = current_player.make_assertion()
                    print(f"Assertion: {action.message}")
                    
                elif game.state.phase == "action":
                    action = current_player.make_action()
                    print(f"Action: {action.message}")
                
                if action and not action.success:
                    print(f"❌ Turn failed: {action.message}")
                    # Continue game even if individual turn fails
                
                # Save after each turn
                self.persistent_manager.save_game_state(game, game_id)
                
                # Display current team status
                self._display_team_status(game)
            
            # Game exceeded max turns
            return {
                "success": False,
                "error": f"Game exceeded maximum turns ({max_turns})",
                "turns": turn_count,
                "game_id": game_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Game execution error: {str(e)}",
                "game_id": game_id
            }
    
    def _display_team_status(self, game: Game):
        """Display current status of both teams."""
        print("\n--- Team Status ---")
        for i, player in enumerate(game.state.players):
            if player.team:
                living_count = len(player.team.living_fish())
                total_hp = sum(f.hp for f in player.team.fish if f.is_alive())
                print(f"{player.name}: {living_count}/4 fish alive, {total_hp} total HP")
        print("-------------------")