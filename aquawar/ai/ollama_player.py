"""
Ollama AI player implementation for Aquawar using Langchain.

KEY REQUIREMENTS - Comprehensive Error Capture & Round Logic:
=============================================================
1. ALWAYS save turn_{i}.pkl - no exceptions
2. ALWAYS save error details in history entry 
3. ALWAYS increment game_turn (even for failures)
4. ALWAYS update latest.pkl = copy of turn_{i}.pkl
5. ALWAYS respect max_tries before changing game status from "ongoing"
6. Final status for terminated games: "error" (not "completed")

Default Mode Logic:
- Find first round that needs work (ongoing, missing, or corrupted)
- Attempt that ONE round only, then stop regardless of outcome
- On failure: set game_status to "error" (not "ongoing" or "completed")

Error Handling Architecture:
- Hybrid approach with master wrapper + granular handlers
- Master wrapper guarantees pickle/history creation on EVERY exit path
- Granular handlers provide detailed context for specific error types
- ErrorHandlingRegistry tracks all error handling locations
"""

from __future__ import annotations

import json
import time
import traceback
from typing import List, Optional, Any, Dict, Union, Tuple, Callable
from pathlib import Path

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from pydantic import BaseModel, Field

from ..game import Game, FISH_NAMES
from ..persistent import PersistentGameManager
from .base_player import BasePlayer, GameAction
from .tools import *

import copy # for pseudo games (prevent voters from making changes to the game)

class ErrorHandlingRegistry:
    """
    Central registry for tracking all error handling locations and ensuring consistency.
    
    This registry implements the KEY REQUIREMENTS for comprehensive error capture:
    - Tracks all error handlers across the codebase
    - Ensures standardized error context format
    - Provides consistent error handler interface
    """
    
    ERROR_HANDLERS = {
        'llm_invocation': 'OllamaPlayer._handle_llm_invocation_error',
        'response_parsing': 'OllamaPlayer._handle_response_parsing_error',
        'tool_extraction': 'OllamaPlayer._handle_tool_extraction_error',
        'team_selection': 'OllamaPlayer._handle_team_selection_error',
        'game_action': 'OllamaPlayer._handle_game_action_error',
        'assertion': 'OllamaPlayer._handle_assertion_error',
        'master_wrapper': 'OllamaGameManager._handle_turn_execution_error'
    }
    
    @staticmethod
    def create_error_context(error: Exception, operation: str, attempt: int, 
                           player_idx: int, game_turn: int, additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create standardized error context for all error handlers.
        
        Args:
            error: The exception that occurred
            operation: Name of the operation that failed
            attempt: Current attempt number
            player_idx: Player index (0 or 1)
            game_turn: Current game turn
            additional_context: Additional context specific to the operation
            
        Returns:
            Standardized error context dictionary
        """
        print(f"[DEBUG] Player {player_idx}, Turn {game_turn}, Operation {operation}, Attempt {attempt}")
        context = {
            "operation": operation,
            "attempt": attempt,
            "player_idx": player_idx,
            "game_turn": game_turn,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc()
            },
            "timestamp": time.time(),
            "success": False
        }
        
        if additional_context:
            context.update(additional_context)
            
        return context


# Pydantic models for tool inputs
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


class OllamaPlayer(BasePlayer):
    def get_system_message(self) -> str:
        """Get system message for the LLM."""
        return f"""You are {self.name}, an expert Aquawar player competing in a tournament.\n\nAquawar is a turn-based strategy game where you select 4 fish and battle against an opponent.\n\nGAME PHASES:\n1. TEAM SELECTION: Select 4 fish from 12 available (indices 0-11)\n2. ASSERTION PHASE: Optionally guess hidden enemy fish identity  \n3. ACTION PHASE: Attack or use active skills\n\nKEY RULES:\n- All fish start with 400 HP, 100 ATK\n- Each fish has a unique active skill\n- You win by defeating all enemy fish\n\nRefer to the game manual for detailed rules.\n"""
    def set_game_manager(self, game_manager, other_player=None):
        """Set game manager reference for save functionality."""
        self._game_manager = game_manager
        self._other_player = other_player

    @property
    def game_manager(self):
        """Get the game manager reference."""
        return self._game_manager

    @property
    def opponent(self):
        """Get the opponent player reference."""
        return self._other_player
    
    @property
    def player_name(self) -> str:
        return f"{self.model} (Single {self.max_tries})"

    @property
    def player_string(self) -> str:
        """Generate player string for directory naming.
        Converts model format like 'llama3.1:8b' with 3 tries to 'llama3.1_8b_S3'.
        """
        return f"{self.model.replace(':', '_')}_S{self.max_tries}"
    """AI player using Ollama LLM with Langchain tool calling."""


    def get_player_info(self) -> Dict[str, Any]:
        """Get player information for saving."""
        return [{
            "name": self.player_name,
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tries": self.max_tries
        }]

    # def __init__(self, name: str, model: str = "llama3.2:3b", temperature: float = 0.7, top_p: float = 0.9, host: str = "http://localhost:11434", debug: bool = False):
    def __init__(self, name: str, model: str = "llama3.2:3b", max_tries=3, temperature: float = 0.7, top_p: float = 0.9, host: str = "http://localhost:11434", debug: bool = False):    
        """Initialize Ollama player.
        
        Args:
            name: Player name
            model: Ollama model to use
            max_tries: Maximum retry attempts for invalid moves
            temperature: Temperature for LLM responses
            top_p: Top-p sampling parameter
        """
        super().__init__(name)
        self.debug = debug
        self.model = model
        self.max_tries = max_tries
        self.temperature = temperature
        self.top_p = top_p
        tools = [
            select_team_tool,
            assert_fish_tool,
            skip_assertion_tool,
            normal_attack_tool,
            active_skill_tool
        ]
        # Initialize Ollama chat model with appropriate tools
        self.llm = ChatOllama(
            model=model,
            temperature=temperature,
            top_p=top_p,
            base_url=host,
        ).bind_tools(tools)
        # References for save functionality (set by game manager)
        self._game_manager = None
        self._other_player = None
        self.ends_turn = True

    def _extract_tool_call(self, response: BaseMessage) -> Optional[Dict[str, Any]]:
        """Extract tool call from response if available."""
        self._debug_log(f"_extract_tool_call: entering with response type {type(response)}")
        try:
            # Try to access tool_calls attribute if it exists
            self._debug_log(f"_extract_tool_call: accessing tool_calls attribute")
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls and len(tool_calls) > 0:
                result = tool_calls[0]
                return result
        except (AttributeError, IndexError) as e:
            self._debug_log(f"_extract_tool_call: caught exception {e} (type: {type(e).__name__})")
            pass
        except Exception as e:
            self._debug_log(f"_extract_tool_call: unexpected exception {e} (type: {type(e).__name__})")
            raise
        self._debug_log(f"_extract_tool_call: returning None")
        return None
    
    def _handle_llm_invocation_error(self, error: Exception, operation: str, attempt: int, 
                                   player_idx: int, game_turn: int, 
                                   additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle errors during LLM invocation (server communication, timeouts, etc.)
        Part of the comprehensive error capture system per KEY REQUIREMENTS.
        """
        context = ErrorHandlingRegistry.create_error_context(
            error, f"llm_invocation_{operation}", attempt, player_idx, game_turn, 
            additional_context
        )
        self._debug_log(f"LLM invocation error in {operation}: {error}")
        return context
    
    def _handle_response_parsing_error(self, error: Exception, operation: str, attempt: int,
                                     player_idx: int, game_turn: int, response: Any,
                                     additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle errors during response parsing (JSON parsing, format issues, etc.)
        Part of the comprehensive error capture system per KEY REQUIREMENTS.
        """
        parsing_context = {
            "response_type": str(type(response)),
            "response_content": str(response)[:500] if response else "None"
        }
        if additional_context:
            parsing_context.update(additional_context)
            
        context = ErrorHandlingRegistry.create_error_context(
            error, f"response_parsing_{operation}", attempt, player_idx, game_turn,
            parsing_context
        )
        self._debug_log(f"Response parsing error in {operation}: {error}")
        return context
    
    def _handle_tool_extraction_error(self, error: Exception, operation: str, attempt: int,
                                    player_idx: int, game_turn: int, response: Any,
                                    additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle errors during tool call extraction (missing tool calls, invalid format, etc.)
        Part of the comprehensive error capture system per KEY REQUIREMENTS.
        """
        extraction_context = {
            "response_type": str(type(response)),
            "has_tool_calls_attr": hasattr(response, 'tool_calls'),
            "full_response": self._capture_full_response(response)
        }
        if additional_context:
            extraction_context.update(additional_context)
            
        context = ErrorHandlingRegistry.create_error_context(
            error, f"tool_extraction_{operation}", attempt, player_idx, game_turn,
            extraction_context
        )
        self._debug_log(f"Tool extraction error in {operation}: {error}")
        return context
    
    def _handle_team_selection_error(self, error: Exception, attempt: int, player_idx: int, 
                                   game_turn: int, available_fish: List[str],
                                   additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle errors during team selection process.
        Part of the comprehensive error capture system per KEY REQUIREMENTS.
        """
        selection_context = {
            "available_fish_count": len(available_fish),
            "available_fish": available_fish
        }
        if additional_context:
            selection_context.update(additional_context)
            
        context = ErrorHandlingRegistry.create_error_context(
            error, "team_selection", attempt, player_idx, game_turn,
            selection_context
        )
        self._debug_log(f"Team selection error: {error}")
        return context
    
    def _handle_game_action_error(self, error: Exception, operation: str, attempt: int,
                                player_idx: int, game_turn: int, phase: str,
                                additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle errors during game actions (attacks, skills, etc.)
        Part of the comprehensive error capture system per KEY REQUIREMENTS.
        """
        action_context = {
            "phase": phase,
            "operation_type": operation
        }
        if additional_context:
            action_context.update(additional_context)
            
        context = ErrorHandlingRegistry.create_error_context(
            error, f"game_action_{operation}", attempt, player_idx, game_turn,
            action_context
        )
        self._debug_log(f"Game action error in {operation}: {error}")
        return context
    
    def _handle_assertion_error(self, error: Exception, attempt: int, player_idx: int,
                               game_turn: int, additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle errors during assertion process.
        Part of the comprehensive error capture system per KEY REQUIREMENTS.
        """
        context = ErrorHandlingRegistry.create_error_context(
            error, "assertion", attempt, player_idx, game_turn, additional_context
        )
        self._debug_log(f"Assertion error: {error}")
        return context
    
    def _create_fallback_history_entry(self, context: Dict[str, Any]) -> None:
        """
        Create a fallback history entry when normal history creation fails.
        Ensures KEY REQUIREMENT: ALWAYS save error details in history entry.
        """
        if not self.game:
            return
            
        try:
            # Create a minimal history entry for the error using the correct method
            error_message = context.get("error", {}).get("message", "Unknown error")
            player_idx = context.get("player_idx", 0)
            
            self.game.add_history_entry_unified(
                player_idx,  # Use 0-based player index (no +1)
                [("system", f"Error in {context.get('operation', 'unknown')}")],  # input_messages
                {"error": context.get("error", {}), "context": context},  # response dict
                False,  # valid = False since this is an error
                f"Error: {error_message}"  # move description
            )
        except Exception as e:
            self._debug_log(f"Failed to create fallback history entry: {e}")
            # Even this failed - at least log it

    def make_team_selection(self, available_fish: List[str], max_tries: int = 3, save_callback: Optional[Callable[[], None]] = None, preset_response: Optional[Dict[str, Any]] = None) -> GameAction:
        """Make team selection using LLM tool calling with retry logic.
        
        Args:
            available_fish: List of available fish names
            max_tries: Maximum number of retry attempts
            save_callback: Optional callback to save game state
            preset_response: Optional preset response to use instead of calling LLM (Majority Vote)

        Returns:
            GameAction with selection result and captured response
        """
        self._debug_log(f"{self.player_name}: Making team selection...")
        if not self.game or self.player_index is None:
            print(f"[WARNING] No game context set")
            return GameAction("select_team", False, "No game context set", "invalid action")
        
        prompt = self.game.prompt_for_selection(self.player_index)
        messages = [prompt]  # Exact messages passed to llm.invoke()
        captured_responses = []
        raw_responses = []
        for attempt in range(max_tries):
            llm_input = None  # Initialize to avoid unbound variable issues
            try:
                llm_input = [
                    ("system", self.get_system_message()),
                    ("user", f"""{prompt}

Select your team of 4 fish using the select_team_tool. Use fish indices from the roster.

IMPORTANT: If you select Mimic Fish, you MUST provide mimic_choice parameter with the fish name to copy.

EXAMPLES:
- To select fish at indices [0, 2, 5, 8] without Mimic Fish:
  Use select_team_tool with fish_indices=[0, 2, 5, 8]

- To select fish at indices [1, 3, 7, 11] where index 11 is Mimic Fish copying "Great White Shark":
  Use select_team_tool with fish_indices=[1, 3, 7, 11], mimic_choice="Great White Shark"

RECOMMENDED STRATEGY: For this game, avoid selecting Mimic Fish (if present) to keep selection simple. Choose 4 different fish with good synergies.

{f"This is attempt {attempt + 1} of {max_tries}." if attempt > 0 else ""}""")
                ]
                
                # Add previous error information for retry attempts
                if attempt > 0 and captured_responses:
                    last_error = f"Previous attempt failed: {captured_responses[-1].get('error', 'Unknown error')}"
                    messages = messages.copy() + [last_error]
                    llm_input[1] = ("user", llm_input[1][1] + f"\n\nPREVIOUS ERROR: {last_error}\nPlease correct the issue and try again.")
                
                # if self.ends_turn:
                    # Increment game turn for each LLM invocation attempt
                    # self.game.increment_game_turn()
                self._debug_log(f"Incrementing game turn: {self.game.state.game_turn} -> {self.game.state.game_turn + 1}")
                self.game.increment_game_turn()

                if preset_response:
                    self._debug_log(f"Using preset response for attempt {attempt + 1}")
                    response = preset_response
                else:
                    response = self.llm.invoke(llm_input)
                response_dict = json.loads(response.model_dump_json())  # Raw LLM response object
                captured_responses.append(response_dict)
                raw_responses.append(response)

                tool_call = self._extract_tool_call(response)
                if not tool_call:
                    response_dict["error"] = "No tool call made"
                    # Add history entry for validation error
                    try:
                        self.game.add_history_entry_unified(
                            self.player_index, messages, response_dict, False, response_dict["error"]
                        )
                    except Exception as hist_error:
                        self._debug_log(f"Failed to add history for validation error: {hist_error}")
                    # Save after validation error if save callback provided
                    if save_callback:
                        try:
                            save_callback()
                            self._debug_log(f"Sequential save completed for validation error - attempt {attempt + 1}")
                        except Exception as save_error:
                            self._debug_log(f"Failed to save after validation error - attempt {attempt + 1}: {save_error}")
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                if tool_call['name'] != 'select_team_tool':
                    response_dict["error"] = f"Wrong tool called: {tool_call['name']}"
                    # Add history entry for tool validation error
                    try:
                        self.game.add_history_entry_unified(
                            self.player_index, messages, response_dict, False, response_dict["error"]
                        )
                    except Exception as hist_error:
                        self._debug_log(f"Failed to add history for tool validation error: {hist_error}")
                    # Save after tool validation error if save callback provided
                    if save_callback:
                        try:
                            save_callback()
                            self._debug_log(f"Sequential save completed for tool validation error - attempt {attempt + 1}")
                        except Exception as save_error:
                            self._debug_log(f"Failed to save after tool validation error - attempt {attempt + 1}: {save_error}")
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                args = tool_call['args']
                
                # Parse comma-separated string format for GPT-OSS
                fish_indices = args.get('fish_indices', '')
                mimic_choice = args.get('mimic_choice', '') or None
                self._debug_log(f"Parsed tool args: fish_indices_str={fish_indices}, mimic_choice={mimic_choice}")
                # Convert "0,1,2,3" to [0,1,2,3]
                try:
                    if isinstance(fish_indices, str):
                        fish_indices = [int(x.strip()) for x in fish_indices.split(',') if x.strip()]
                # except (ValueError, TypeError) as e:
                except Exception as e:
                    self._debug_log(f"Failed to parse fish indices: {fish_indices} ({e})")
                    response_dict["error"] = f"Invalid fish indices format: {fish_indices}"
                    # Add history entry for validation error
                    try:
                        self.game.add_history_entry_unified(
                            self.player_index, messages, response_dict, False, response_dict["error"]
                        )
                    except Exception as hist_error:
                        self._debug_log(f"Failed to add history for validation error: {hist_error}")
                    # Save after parsing error if save callback provided
                    if save_callback:
                        try:
                            save_callback()
                            self._debug_log(f"Sequential save completed for parsing error - attempt {attempt + 1}")
                        except Exception as save_error:
                            self._debug_log(f"Failed to save after parsing error - attempt {attempt + 1}: {save_error}")
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                    
                # Convert empty string to None for mimic_choice
                if mimic_choice == "":
                    mimic_choice = None
                
                # Validate indices
                if len(fish_indices) != 4:
                    response_dict["error"] = "Must select exactly 4 fish"
                    # Add history entry for validation error
                    try:
                        self.game.add_history_entry_unified(
                            self.player_index, messages, response_dict, False, response_dict["error"]
                        )
                    except Exception as hist_error:
                        self._debug_log(f"Failed to add history for validation error: {hist_error}")
                    # Save after count validation error if save callback provided
                    if save_callback:
                        try:
                            save_callback()
                            self._debug_log(f"Sequential save completed for count validation error - attempt {attempt + 1}")
                        except Exception as save_error:
                            self._debug_log(f"Failed to save after count validation error - attempt {attempt + 1}: {save_error}")
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                for idx in fish_indices:
                    if not isinstance(idx, int) or idx < 0 or idx >= len(available_fish):
                        response_dict["error"] = f"Invalid fish index: {idx}"
                        # Add history entry for validation error
                        try:
                            self.game.add_history_entry_unified(
                                self.player_index, messages, response_dict, False, response_dict["error"]
                            )
                        except Exception as hist_error:
                            self._debug_log(f"Failed to add history for validation error: {hist_error}")
                        # Save after index validation error if save callback provided
                        if save_callback:
                            try:
                                save_callback()
                                self._debug_log(f"Sequential save completed for index validation error - attempt {attempt + 1}")
                            except Exception as save_error:
                                self._debug_log(f"Failed to save after index validation error - attempt {attempt + 1}: {save_error}")
                        if attempt == max_tries - 1:  # Last attempt
                            break
                        continue
                
                # Convert indices to fish names
                fish_names = [available_fish[i] for i in fish_indices]
                
                # Check for Mimic Fish
                if "Mimic Fish" in fish_names and not mimic_choice:
                    response_dict["error"] = "Mimic Fish selected but no mimic choice provided"
                    # Add history entry for validation error
                    try:
                        self.game.add_history_entry_unified(
                            self.player_index, messages, response_dict, False, response_dict["error"]
                        )
                    except Exception as hist_error:
                        self._debug_log(f"Failed to add history for validation error: {hist_error}")
                    # Save after mimic validation error if save callback provided
                    if save_callback:
                        try:
                            save_callback()
                            self._debug_log(f"Sequential save completed for mimic validation error - attempt {attempt + 1}")
                        except Exception as save_error:
                            self._debug_log(f"Failed to save after mimic validation error - attempt {attempt + 1}: {save_error}")
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                # Success! Make the selection
                self.game.select_team(self.player_index, fish_names, mimic_choice)
                
                # Track in history with retry information
                response_text = f"Selected fish indices: {sorted(fish_indices)}"
                if mimic_choice:
                    response_text += f", Mimic choice: {mimic_choice}"
                
                # Get the latest response for history
                latest_captured_response = captured_responses[-1] if captured_responses else {"content": "No response data"}
                self.game.add_history_entry_unified(self.player_index, messages, latest_captured_response, True, response_text
                )
                latest_raw_response = raw_responses[-1] if raw_responses else None
                return GameAction("select_team", True, f"Selected team: {fish_names}", "valid", latest_captured_response, latest_raw_response)

            except Exception as e:
                # Use comprehensive error handling system
                error_context = self._handle_llm_invocation_error(
                    e, "team_selection", attempt + 1, 
                    self.player_index, self.game.state.game_turn,
                    {
                        "available_fish": available_fish,
                        "llm_input": str(llm_input.copy()) if llm_input else "Not available",
                        "attempt": attempt + 1,
                        "max_tries": max_tries
                    }
                )
                
                # Create response entry with comprehensive error details
                response_dict = {
                    "attempt": attempt + 1,
                    "content": f"COMPREHENSIVE ERROR CAPTURE:\n{json.dumps(error_context, indent=2)}",
                    "error": f"Error: {error_context['error']['message']}",
                    "error_context": error_context
                }
                captured_responses.append(response_dict)
                
                # Create fallback history entry to ensure error is always captured
                try:
                    self._create_fallback_history_entry(error_context)
                except Exception as fallback_error:
                    self._debug_log(f"Failed to create fallback history entry: {fallback_error}")
                
                # Save after each failed attempt if save callback provided
                if save_callback:
                    try:
                        save_callback()
                        self._debug_log(f"Sequential save completed for failed attempt {attempt + 1}")
                    except Exception as save_error:
                        self._debug_log(f"Failed to save after failed attempt {attempt + 1}: {save_error}")
                
                if attempt == max_tries - 1:  # Last attempt
                    break
        
        # All attempts failed - save failure to history and return error
        final_error = captured_responses[-1].get('error', 'Unknown error') if captured_responses else 'No responses received'
        
        captured_response = captured_responses[-1].get('content', '') if captured_responses else ''
        raw_response = raw_responses[-1] if raw_responses else None
        action = GameAction("select_team", False, f"Failed after {max_tries} attempts: {final_error}", "invalid action", captured_response, raw_response)

        return action
    
    def make_assertion(self) -> GameAction:
        """Make assertion decision using LLM tool calling.
        
        Returns:
            GameAction with assertion result
        """
        if not self.game or self.player_index is None:
            return GameAction("assertion", False, "No game context set", "invalid action")

        # if self.ends_turn:
            # Increment game turn for any assertion attempt (valid or invalid)
            # self.game.increment_game_turn()
        self.game.increment_game_turn()
        

        prompt = self.game.prompt_for_assertion(self.player_index)
        
        messages = [
            ("system", self.get_system_message()),
            ("user", f"{prompt}\n\nMake your assertion decision using either assert_fish_tool or skip_assertion_tool.")
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_dict = json.loads(response.model_dump_json())  # Raw LLM response object
            
            tool_call = self._extract_tool_call(response)
            if not tool_call:
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, "No tool call made"
                )
                action = GameAction("assertion", False, "No tool call made", "invalid response")
                return action
            
            tool_name = tool_call['name']
            args = tool_call['args']
            
            if tool_name == 'skip_assertion_tool':
                result = self.game.skip_assertion(self.player_index)
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, True, "SKIP"
                )
                return GameAction("assertion", True, result, "valid")
                
            elif tool_name == 'assert_fish_tool':
                enemy_index = args.get('enemy_index')
                fish_name = args.get('fish_name')
                
                if enemy_index is None or fish_name is None:
                    error_msg = "Missing assertion parameters"
                    self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("assertion", False, error_msg, "invalid argument")
                    return action
                
                # Convert string argument to integer (works for both formats)
                try:
                    enemy_index = int(enemy_index)
                except (ValueError, TypeError):
                    error_msg = f"Invalid enemy_index type: {enemy_index}"
                    self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("assertion", False, error_msg, "invalid argument")
                    return action
                
                result = self.game.perform_assertion(self.player_index, enemy_index, fish_name)
                response_text = f"ASSERT {enemy_index} {fish_name}"
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, True, response_text
                )
                return GameAction("assertion", True, result, "valid")
                
            else:
                error_msg = f"Wrong tool called: {tool_name}"
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                )
                action = GameAction("assertion", False, error_msg, "invalid response")
                return action
            
        except Exception as e:
            # Capture detailed exception information for server errors
            import traceback
            error_details = {
                "exception_type": str(type(e).__name__),
                "exception_message": str(e),
                "full_traceback": traceback.format_exc(),
                "ollama_server_error": True,
                "no_llm_response_received": True
            }
            response_dict = {"content": f"OLLAMA SERVER ERROR - No LLM response received:\n{json.dumps(error_details, indent=2)}"}
            
            error_msg = f"Error in assertion: {e}"
            self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
            )
            action = GameAction("assertion", False, error_msg, "invalid action")
            return action
    
    def make_action(self) -> GameAction:
        """Make action decision using LLM tool calling.
        
        Returns:
            GameAction with action result
        """
        self._debug_log(f"Making action decision:")
        self._debug_log(f"Player index: {self.player_index}")
        if not self.game or self.player_index is None:
            self._debug_log("No game context set for action")
            return GameAction("action", False, "No game context set", "invalid action")

        self._debug_log(f"Incrementing game turn for player {self.player_index}")
        self.game.increment_game_turn()

        self._debug_log(f"Prompting for action for player {self.player_index}")
        prompt = self.game.prompt_for_action(self.player_index)
        
        messages = [
            ("system", self.get_system_message()),
            ("user", f"{prompt}\n\nMake your action using either normal_attack_tool or active_skill_tool.")
        ]
        
        try:
            self._debug_log(f"Invoking LLM with {len(messages)} messages")
            response = self.llm.invoke(messages)
            self._debug_log(f"LLM response received, type: {type(response)}")
            self._debug_log(f"About to parse response JSON")
            try:
                response_dict = json.loads(response.model_dump_json())  # Raw LLM response object
                self._debug_log(f"Response JSON parsed successfully")
            except Exception as e:
                self._debug_log(f"ERROR parsing response JSON: {e} (type: {type(e).__name__})")
                raise
            
            self._debug_log(f"Extracting tool call from response")
            self._debug_log(f"About to call _extract_tool_call with response type: {type(response)}")
            try:
                tool_call = self._extract_tool_call(response)
                self._debug_log(f"Tool call extraction result: {tool_call}")
            except Exception as e:
                self._debug_log(f"ERROR in _extract_tool_call: {e} (type: {type(e)})")
                raise
            
            if not tool_call:
                error_msg = "No tool call made"
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                )
                action = GameAction("action", False, error_msg, "invalid response")
                return action
            
            tool_name = tool_call['name']
            args = tool_call['args']
            
            self._debug_log(f"Processing tool call: name={tool_name}, args={args}")
            
            if tool_name == 'normal_attack_tool':
                self._debug_log(f"Processing normal attack tool")
                fish_index = args.get('fish_index')
                target_index = args.get('target_index')
                self._debug_log(f"Attack parameters: fish_index={fish_index}, target_index={target_index}")
                
                if fish_index is None or target_index is None:
                    error_msg = "Missing attack parameters"
                    self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("action", False, error_msg, "invalid argument")
                    return action
                
                # Convert string arguments to integers (works for both formats)
                self._debug_log(f"About to convert parameters to integers")
                try:
                    fish_index = int(fish_index)
                    target_index = int(target_index)
                    self._debug_log(f"Parameter conversion successful: fish_index={fish_index}, target_index={target_index}")
                except (ValueError, TypeError) as e:
                    self._debug_log(f"Parameter conversion failed: {e}")
                    error_msg = f"Invalid parameter types: fish_index={fish_index}, target_index={target_index}"
                    self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("action", False, error_msg, "invalid argument")
                    return action
                
                self._debug_log(f"About to call self.game.perform_action({self.player_index}, {fish_index}, 'NORMAL', {target_index})")
                try:
                    result = self.game.perform_action(self.player_index, fish_index, "NORMAL", target_index)
                    self._debug_log(f"perform_action result: {result}")
                except Exception as e:
                    self._debug_log(f"ERROR in perform_action: {e} (type: {type(e).__name__})")
                    raise
                response_text = f"ACT {fish_index} NORMAL {target_index}"
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, True, response_text
                )
                return GameAction("action", True, result, "valid")

            elif tool_name == 'active_skill_tool':
                self._debug_log(f"Processing active skill tool")
                fish_index = args.get('fish_index')
                target_index = args.get('target_index')
                self._debug_log(f"Active skill parameters: fish_index={fish_index}, target_index={target_index}")
                
                if fish_index is None:
                    error_msg = "Missing fish index for active skill"
                    self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("action", False, error_msg, "invalid argument")
                    return action
                
                # Convert string arguments to integers (works for both formats)
                # Handle empty string as None for target_index in GPT-OSS format
                self._debug_log(f"About to convert active skill parameters")
                try:
                    fish_index = int(fish_index)
                    if target_index is not None and target_index != "":
                        target_index = int(target_index)
                    else:
                        target_index = None
                    self._debug_log(f"Active skill parameter conversion successful: fish_index={fish_index}, target_index={target_index}")
                except (ValueError, TypeError) as e:
                    self._debug_log(f"Active skill parameter conversion failed: {e}")
                    error_msg = f"Invalid parameter types: fish_index={fish_index}, target_index={target_index}"
                    self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("action", False, error_msg, "invalid argument")
                    return action
                
                self._debug_log(f"About to call self.game.perform_action({self.player_index}, {fish_index}, 'ACTIVE', {target_index})")
                try:
                    result = self.game.perform_action(self.player_index, fish_index, "ACTIVE", target_index)
                    self._debug_log(f"perform_action (active) result: {result}")
                except Exception as e:
                    self._debug_log(f"ERROR in perform_action (active): {e} (type: {type(e).__name__})")
                    raise
                response_text = f"ACT {fish_index} ACTIVE"
                if target_index is not None:
                    response_text += f" {target_index}"
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, True, response_text
                )
                return GameAction("action", True, result, "valid")
                
            else:
                error_msg = f"Wrong tool called: {tool_name}"
                self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
                )
                action = GameAction("action", False, error_msg, "invalid response")
                return action
            
        except Exception as e:
            # Capture detailed exception information for server errors
            self._debug_log(f"EXCEPTION CAUGHT: {e} (type: {type(e).__name__})")
            import traceback
            self._debug_log(f"FULL TRACEBACK: {traceback.format_exc()}")
            error_details = {
                "exception_type": str(type(e).__name__),
                "exception_message": str(e),
                "full_traceback": traceback.format_exc(),
                "ollama_server_error": True,
                "no_llm_response_received": True
            }
            response_dict = {"content": f"OLLAMA SERVER ERROR - No LLM response received:\n{json.dumps(error_details, indent=2)}"}
            
            error_msg = f"Error in action: {e}"
            self.game.add_history_entry_unified(self.player_index, messages, response_dict, False, error_msg
            )
            action = GameAction("action", False, error_msg, "invalid action")
            return action

    # ------------------------------------------------------------------
    # Refactored Core Methods for Move Generation, Persistence, and Turn Management
    # ------------------------------------------------------------------

    def _map_fish_index_to_name(self, player_index, fish_index):
        team = self.game.state.players[player_index].team
        return team.fish[fish_index].name

    def describe_move(self, context, move_type, **kwargs):
        """
        Updates the context to describe the move being made in an organized format:

        Updates:
        {
            "move_type": <move_type>,           # Required
            "player_fish_index": <fish_index|None>,
            "player_fish_name": <fish_name|None>,
            "target_fish_index": <target_index|None>,
            "target_fish_name": <target_name|None>,
            "assert_fish_name": <assert_fish_name|None>
        }
        """
        context.update({
            "move_type": move_type,
            "player_fish_index": kwargs.get("player_fish_index", None),
            "player_fish_name": kwargs.get("player_fish_name", None),
            "target_fish_index": kwargs.get("target_fish_index", None),
            "target_fish_name": kwargs.get("target_fish_name", None),
            "assert_fish_name": kwargs.get("assert_fish_name", None),
        })

    def make_move(self, phase: str, messages: List[Any] = None, preset_response = None) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """Core move generation method that can be reused by different player types.
        
        Args:
            phase: "assertion" or "action" or "team_selection"  
            messages: Optional pre-built messages, if None will generate from game state
            preset_response: Optional preset response to use instead of calling LLM
        Returns:
            Tuple of (history_entry, parsed_move_result, additional_context)
        """
        if not self.game or self.player_index is None:
            print(f"[DEBUG] make_move: No game context set for move generation (phase={phase}, player={self.player_index})")
            raise ValueError("No game context set for move generation")
        response = None
        # Generate messages if not provided
        if messages is None:
            if phase == "assertion":
                prompt = self.game.prompt_for_assertion(self.player_index)
                messages = [
                    ("system", self.get_system_message()),
                    ("user", f"{prompt}\n\nMake your assertion decision using either assert_fish_tool or skip_assertion_tool.")
                ]
            elif phase == "action":
                prompt = self.game.prompt_for_action(self.player_index)
                messages = [
                    ("system", self.get_system_message()),
                    ("user", f"{prompt}\n\nMake your action using either normal_attack_tool or active_skill_tool.")
                ]
            else:
                print(f"[DEBUG] make_move: Unsupported phase for automatic message generation: {phase}")
                raise ValueError(f"Unsupported phase for automatic message generation: {phase}")

        print(f"[DEBUG] make_move: phase={phase}, player={self.player_index}, messages={[(m[0], str(m[1])[:60]) for m in messages]}")

        # Context for tracking move generation
        context = {
            "phase": phase,
            "prompts": messages,
            "llm_response": None,
            "tool_call": None,
            "parameters": None,
            "validated_parameters": None,
            "move_type": None,
            "success": False,
        }

        try:
            # if self.ends_turn:
                # Increment game turn for move attempt
                # self.game.increment_game_turn()
            self.game.increment_game_turn()

            # Call LLM
            if not preset_response:
                self._debug_log(f"Game turn {self.game.state.game_turn}: Invoking LLM for phase={phase}, player={self.player_index}")
                response = self.llm.invoke(messages)
            else:
                self._debug_log(f"Game turn {self.game.state.game_turn}: Using preset response for phase={phase}, player={self.player_index}")
                response = preset_response
            context["llm_response"] = json.loads(response.model_dump_json())

            # Extract and validate tool call
            tool_call = self._extract_tool_call(response)
            context["tool_call"] = tool_call

            if not tool_call:
                print(f"[DEBUG] make_move: No tool call made by LLM (phase={phase}, player={self.player_index})")
                raise RuntimeError("No tool call made by LLM")

            tool_name = tool_call['name']
            args = tool_call['args']
            context["parameters"] = {"tool_name": tool_name, "args": args}

            # Execute move based on phase and tool
            if phase == "assertion":
                if tool_name == 'skip_assertion_tool':
                    # context["move_type"] = "skip_assertion"
                    # context["validated_parameters"] = {}
                    self.describe_move(context, move_type="skip_assertion")
                    result = self.game.skip_assertion(self.player_index)

                elif tool_name == 'assert_fish_tool':
                    enemy_fish_index = args.get('enemy_index')
                    fish_name = args.get('fish_name')

                    if enemy_fish_index is None or fish_name is None:
                        print(f"[DEBUG] make_move: Missing assertion parameters from LLM/tool call (phase={phase}, player={self.player_index})")
                        raise RuntimeError("Missing assertion parameters from LLM/tool call")

                    try:
                        enemy_fish_index = int(enemy_fish_index)
                    except Exception:
                        print(f"[DEBUG] make_move: Invalid enemy_index value: {enemy_fish_index} (phase={phase}, player={self.player_index})")
                        raise RuntimeError(f"Invalid enemy_index value: {enemy_fish_index}")
                    # context["move_type"] = "assert_fish"
                    # context["validated_parameters"] = {"enemy_index": enemy_index, "fish_name": fish_name}
                    enemy_fish_name = self._map_fish_index_to_name(1-self.player_index, enemy_fish_index)
                    self.describe_move(context, move_type="assert_fish", target_fish_index=enemy_fish_index, target_fish_name=enemy_fish_name, assert_fish_name=fish_name)
                    result = self.game.perform_assertion(self.player_index, enemy_fish_index, fish_name)
                else:
                    print(f"[DEBUG] make_move: Invalid tool for assertion phase: {tool_name} (phase={phase}, player={self.player_index})")
                    raise RuntimeError(f"Invalid tool for assertion phase: {tool_name}")

            elif phase == "action":
                if tool_name == 'normal_attack_tool':
                    fish_index = args.get('fish_index')
                    target_index = args.get('target_index')

                    if fish_index is None or target_index is None:
                        print(f"[DEBUG] make_move: Missing attack parameters from LLM/tool call (phase={phase}, player={self.player_index})")
                        raise RuntimeError("Missing attack parameters from LLM/tool call")
                    try:
                        fish_index = int(fish_index)
                        target_index = int(target_index)
                    except Exception:
                        print(f"[DEBUG] make_move: Invalid attack indices: fish_index={fish_index}, target_index={target_index} (phase={phase}, player={self.player_index})")
                        raise RuntimeError(f"Invalid attack indices: fish_index={fish_index}, target_index={target_index}")

                    # context["move_type"] = "normal_attack"
                    # context["validated_parameters"] = {"fish_index": fish_index, "target_index": target_index}
                    player_fish_name = self._map_fish_index_to_name(self.player_index, fish_index)
                    target_fish_name = self._map_fish_index_to_name(1-self.player_index, target_index)
                    self.describe_move(context, move_type="normal_attack", player_fish_index=fish_index, player_fish_name=player_fish_name, target_fish_index=target_index, target_fish_name=target_fish_name)
                    result = self.game.perform_action(self.player_index, fish_index, "NORMAL", target_index)

                elif tool_name == 'active_skill_tool':
                    fish_index = args.get('fish_index')
                    target_index = args.get('target_index')

                    if fish_index is None:
                        print(f"[DEBUG] make_move: Missing fish index for active skill from LLM/tool call (phase={phase}, player={self.player_index})")
                        raise RuntimeError("Missing fish index for active skill from LLM/tool call")
                    try:
                        fish_index = int(fish_index)
                        player_fish_name = self._map_fish_index_to_name(self.player_index, fish_index)
                    except Exception:
                        print(f"[DEBUG] make_move: Invalid fish_index value: {fish_index} (phase={phase}, player={self.player_index})")
                        raise RuntimeError(f"Invalid fish_index value: {fish_index}")

                    # Handle optional target_index
                    if target_index is not None and target_index != "" and target_index != "None":
                        try:
                            target_index = int(target_index)
                            target_fish_name = self._map_fish_index_to_name(1-self.player_index, target_index)
                        except Exception:
                            print(f"[DEBUG] make_move: Invalid target_index value: {target_index} (phase={phase}, player={self.player_index})")
                            raise RuntimeError(f"Invalid target_index value: {target_index}")
                    else:
                        target_index = None
                        target_fish_name = None

                    # context["move_type"] = "active_skill"
                    # context["validated_parameters"] = {"fish_index": fish_index, "target_index": target_index}
                    self.describe_move(context, move_type="active_skill", player_fish_index=fish_index, player_fish_name=player_fish_name, target_fish_index=target_index, target_fish_name=target_fish_name)
                    result = self.game.perform_action(self.player_index, fish_index, "ACTIVE", target_index)
                else:
                    print(f"[DEBUG] make_move: Invalid tool for action phase: {tool_name} (phase={phase}, player={self.player_index})")
                    raise RuntimeError(f"Invalid tool for action phase: {tool_name}")
            else:
                print(f"[DEBUG] make_move: Unsupported phase: {phase} (player={self.player_index})")
                raise RuntimeError(f"Unsupported phase: {phase}")

            # Create history entry
            history_entry = {
                "player": self.player_index,
                "input_messages": messages,
                "response": context["llm_response"],
                "valid": True,
                "move": f"Turn {self.game.state.game_turn}: {phase} - {result}",
                "context": context,
                "success": True
            }
            context["success"] = True
            print(f"[DEBUG] make_move: Completed phase={phase}, player={self.player_index}, turn={self.game.state.game_turn}")
            # return history_entry, result, context
            return result, context, response

        except Exception as e:
            context["error"] = str(e)
            context["success"] = False
            print(f"[DEBUG] make_move ERROR: {type(e).__name__}: {e} (phase={phase}, player={self.player_index}, turn={self.game.state.game_turn if self.game and hasattr(self.game, 'state') else 'N/A'})")
            history_entry = {
                "player": self.player_index,
                "input_messages": messages,
                "response": context.get("llm_response", {"content": f"Error: {e}"}),
                "valid": False,
                "move": f"Turn {self.game.state.game_turn}: {phase} - Error: {e}",
                "context": context,
                "success": False
            }
            # return history_entry, str(e), context
            return str(e), context, response
    
    def save_turn_pickle(self, file_prefix: str, additional_data: Dict[str, Any] = None) -> str:
        """Save current game state to pickle file with specified prefix.
        
        Args:
            file_prefix: Prefix for the file (e.g., "turn", "v1", "v2")
            additional_data: Optional additional data to include in save
        Returns:
            Path to saved file
        """
        if not hasattr(self, '_game_manager') or not self._game_manager:
            print(f"[DEBUG] save_turn_pickle: No game manager available for saving (prefix={file_prefix})")
            raise ValueError("No game manager available for saving")

        # Get player strings for directory structure
        if hasattr(self, '_other_player'):
            player1_string = self.player_string
            player2_string = self._other_player.player_string
        else:
            player1_string = self.player_string
            player2_string = self.player_string

        # Create players_info for saving
        players_info = {}
        if additional_data and 'players_info' in additional_data:
            players_info = additional_data['players_info']
        else:
            players_info = self._game_manager._get_players_info(self, self.opponent)

        game_turn = self.game.state.game_turn
        round_num = additional_data.get('round_num', 1) if additional_data else 1

        game_dir = self._game_manager.persistent_manager.get_game_dir(player1_string, player2_string, round_num)
        game_dir.mkdir(parents=True, exist_ok=True)

        save_path = game_dir / f"{file_prefix}_{game_turn:03d}.pkl"
        latest_path = game_dir / "latest.pkl"

        print(f"[DEBUG] save_turn_pickle: prefix={file_prefix}, turn={game_turn}, round={round_num}, path={save_path}")

        self.game.save_game(str(save_path), players_info)
        self.game.save_game(str(latest_path), players_info)

        return str(save_path)
    
    def end_game_turn(self, history_entry: Dict[str, Any], additional_data: Dict[str, Any] = None) -> None:
        """Complete the current turn by adding history and saving state.
        
        Args:
            history_entry: History entry to add to game
            additional_data: Optional additional data for saving
        """
        # Add history entry to game
        self.game.history.append(history_entry)
        
        # Save turn state with "turn" prefix
        save_path = self.save_turn_pickle("turn", additional_data)
        self._debug_log(f"Turn completed and saved to: {save_path}")

    # ------------------------------------------------------------------
    # Enhanced context-capturing methods for global error handling
    # ------------------------------------------------------------------
    
    def _identify_error_location(self, error: Exception, context: Dict[str, Any]) -> str:
        """Identify where in the turn execution the error occurred."""
        
        # LLM invocation errors
        if not context.get("llm_response"):
            return "llm_invocation"
        
        # Tool extraction errors
        if not context.get("tool_call"):
            return "tool_extraction"
        
        # Parameter validation errors
        if not context.get("validated_parameters"):
            if isinstance(error, (ValueError, TypeError)):
                return "parameter_validation"
            return "parameter_processing"
        
        # Game logic errors
        if "perform_action" in str(error) or "perform_assertion" in str(error):
            return "game_logic"
        
        # System errors
        if isinstance(error, KeyError):
            return "system_tracking"
        
        return "unknown"

    def make_action_simple_with_context(self, preset_response=None) -> Tuple[str, Dict[str, Any]]:
        """Make action decision with full context capture for documentation.
        
        This method now delegates to the refactored make_move method.
        """
        try:
            # history_entry, result, context = self.make_move("action")
            result, context, response = self.make_move("action", preset_response=preset_response)
            return result, context, response
        except Exception as e:
            # For backward compatibility, ensure error location is identified
            context = {
                "error_location": "action_execution",
                "error": str(e)
            }
            raise  # Re-raise for global handling

    def make_assertion_simple_with_context(self, preset_response=None) -> Tuple[str, Dict[str, Any]]:
        """Make assertion decision with full context capture for documentation.
        
        This method now delegates to the refactored make_move method.
        """
        try:
            # history_entry, result, context = self.make_move("assertion", preset_response=preset_response)
            result, context, response = self.make_move("assertion", preset_response=preset_response)
            return result, context, response
        except Exception as e:
            # For backward compatibility, ensure error location is identified  
            context = {
                "error_location": "assertion_execution",
                "error": str(e)
            }
            raise  # Re-raise for global handling


class OllamaGameManager:
    """Manages AI vs AI games using Ollama language models."""
    
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if getattr(self, 'debug', False):
            print(f"[DEBUG] {message}")
    
    def __init__(self, save_dir: str = "saves", model: str = "llama3.2:3b", debug: bool = False, max_tries: int = 3, prefix="turn"):
        """Initialize the game manager.
        
        Args:
            save_dir: Directory for saving games
            model: Ollama model to use for both players
            debug: Enable detailed debug logging
            max_tries: Maximum retry attempts for invalid moves
        """
        self.save_dir = save_dir
        self.persistent_manager = PersistentGameManager(save_dir, debug)
        self.model = model
        self.debug = debug
        self.max_tries = max_tries
        self.turn_prefix = prefix
    
    def _set_turn_prefix(self, prefix):
        self.turn_prefix = prefix

    def _handle_turn_execution_error(self, error: Exception, game: Game, 
                                   player1: 'BasePlayer', player2: 'BasePlayer',
                                   round_num: int, operation: str = "turn_execution",
                                   output_prefix: str = "turn") -> Dict[str, Any]:
        """
        Master error handler that ensures KEY REQUIREMENTS are always met.
        GUARANTEES:
        1. ALWAYS save turn_{i}.pkl - no exceptions
        2. ALWAYS save error details in history entry 
        3. ALWAYS increment game_turn (even for failures)
        4. ALWAYS update latest.pkl = copy of turn_{i}.pkl
        5. ALWAYS respect max_tries before changing game status from "ongoing"
        6. Final status for terminated games: "error" (not "completed")
        """
        players_info = self._get_players_info(player1, player2)
        error_context = {"error": {"message": str(error)}}  # Default fallback
        
        try:
            # Master error handler should ONLY change game status to "error"
            # All turn increments and history entries are handled by the normal retry flow
            
            # Set game status to error (KEY REQUIREMENT #6)
            if hasattr(game, '_update_evaluation_game_status'):
                game._update_evaluation_game_status("error")
            
            # GUARANTEE: Save pickle files (KEY REQUIREMENTS #1 and #4)
            try:
                self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)
                self._debug_log(f"Emergency save completed for error: {error}")
            except Exception as save_error:
                self._debug_log(f"CRITICAL: Failed to save game state during error handling: {save_error}")
                # This is the absolute worst case - log everything we can
                print(f"CRITICAL ERROR: Unable to save game state: {save_error}")
                print(f"Original error: {error}")
                print(f"Game turn: {game.state.game_turn}")
                print(f"Round: {round_num}")
            
        except Exception as handler_error:
            # Even the error handler failed - log everything
            self._debug_log(f"Master error handler itself failed: {handler_error}")
            print(f"CRITICAL: Master error handler failed: {handler_error}")
            print(f"Original error: {error}")
        
        return {
            "success": False,
            "error": f"Critical error in {operation}: {str(error)}",
            "save_path": f"{player1.player_string}/{player2.player_string}/round_{round_num:03d}/"
        }
    
    def get_next_indexed_game_id(self, base_game_id: str) -> str:
        """Generate the next available indexed game ID.
        
        Args:
            base_game_id: Base name for the game (e.g., "ai_vs_ai_demo")
            
        Returns:
            Indexed game ID (e.g., "ai_vs_ai_demo_001")
        """
        from pathlib import Path
        
        counter = 1
        while True:
            indexed_id = f"{base_game_id}_{counter:03d}"
            game_dir = Path(self.save_dir) / indexed_id
            if not game_dir.exists():
                return indexed_id
            counter += 1
    
    def check_round_status(self, player1_string: str, player2_string: str, round_num: int) -> Dict[str, Any]:
        """Check the status of a specific round.
        
        Args:
            player1_string: Player 1 string identifier
            player2_string: Player 2 string identifier  
            round_num: Round number to check
            
        Returns:
            Dictionary with status information:
            - exists: bool - whether round directory exists
            - has_latest: bool - whether latest.pkl exists
            - status: str - game status ("ongoing", "completed", etc.) or None
            - needs_execution: bool - whether this round needs to be executed
            - error: str - error message if any issues
        """
        game_dir = self.persistent_manager.get_game_dir(player1_string, player2_string, round_num)
        latest_path = self.persistent_manager.get_save_path(player1_string, player2_string, round_num)
        
        result = {
            "round_num": round_num,
            "game_dir": str(game_dir),
            "exists": game_dir.exists(),
            "has_latest": latest_path.exists() if game_dir.exists() else False,
            "status": None,
            "needs_execution": False,
            "error": None
        }
        
        if not result["exists"]:
            result["needs_execution"] = True
            return result
            
        if not result["has_latest"]:
            result["needs_execution"] = True
            return result
            
        # Check game status from latest.pkl
        try:
            # Load the pickle file to get status
            import pickle
            with open(latest_path, 'rb') as f:
                turn_data = pickle.load(f)
                
            if "evaluation" not in turn_data:
                result["error"] = f"Missing 'evaluation' key in latest.pkl"
                return result
                
            if "game_status" not in turn_data["evaluation"]:
                result["error"] = f"Missing 'game_status' in evaluation"
                return result
                
            result["status"] = turn_data["evaluation"]["game_status"]
            
            # Determine if execution is needed
            if result["status"] == "ongoing":
                result["needs_execution"] = True
            else:
                result["needs_execution"] = False  # completed, error, etc.
                
        except Exception as e:
            result["error"] = f"Error reading latest.pkl: {e}"
            return result
            
        return result

    def execute_multiple_rounds(self, player1_name: str, player2_name: str, 
                               player1_model: str, player2_model: str,
                               max_turns: int = 200, rounds: Optional[int] = None) -> Dict[str, Any]:
        """Execute multiple rounds with automatic detection and resumption.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            player1_model: Model for player 1
            player2_model: Model for player 2
            max_turns: Maximum turns per game
            rounds: Number of rounds to execute (None = find first available)
            
        Returns:
            Dictionary with execution results
        """
        # Create temporary players to get player strings
        temp_player1 = OllamaPlayer(player1_name, player1_model, debug=self.debug)
        temp_player2 = OllamaPlayer(player2_name, player2_model, debug=self.debug)
        player1_string = temp_player1.player_string
        player2_string = temp_player2.player_string
        
        results = {
            "player1_string": player1_string,
            "player2_string": player2_string,
            "total_rounds_executed": 0,
            "rounds_completed": 0,
            "rounds_skipped": 0,
            "rounds_failed": 0,
            "round_results": [],
            "success": True,
            "error": None
        }
        
        if rounds is None:
            # Default behavior: execute rounds sequentially until finding completed one
            round_num = 1
            while True:
                print(f"\n🔍 Checking round {round_num:03d}...")
                status = self.check_round_status(player1_string, player2_string, round_num)
                
                if status["error"]:
                    print(f"❌ Error in {status['game_dir']}: {status['error']}")
                    results["error"] = status["error"]
                    results["success"] = False
                    break
                
                if not status["needs_execution"]:
                    print(f"✅ Round {round_num:03d} already completed ({status['status']}) - skipping")
                    print(f"📁 Path: {status['game_dir']}")
                    results["rounds_skipped"] += 1
                    results["round_results"].append({
                        "round": round_num,
                        "action": "skipped",
                        "status": status["status"],
                        "path": status["game_dir"]
                    })
                    round_num += 1
                    continue
                
                # Execute this round
                print(f"🎮 Executing round {round_num:03d}...")
                print(f"📁 Path: {status['game_dir']}")
                
                if status["exists"] and status["has_latest"] and status["status"] == "ongoing":
                    print(f"♻️ Resuming from existing save...")
                    result = self.resume_existing_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns)
                else:
                    print(f"🆕 Initializing new round...")
                    result = self.run_single_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns)
                
                results["total_rounds_executed"] += 1
                results["round_results"].append({
                    "round": round_num,
                    "action": "executed",
                    "result": result,
                    "path": status["game_dir"]
                })
                
                if result["success"]:
                    results["rounds_completed"] += 1
                    print(f"✅ Round {round_num:03d} completed successfully")
                    # Stop after completing one round in default mode
                    break
                else:
                    results["rounds_failed"] += 1
                    print(f"❌ Round {round_num:03d} failed: {result.get('error', 'Unknown error')}")
                    # KEY REQUIREMENT: In default mode, stop after attempting first round regardless of outcome
                    print(f"🛑 Stopping after attempting round {round_num:03d} (default mode)")
                    break
        else:
            # Execute specific number of rounds
            for round_num in range(1, rounds + 1):
                print(f"\n🔍 Checking round {round_num:03d}...")
                status = self.check_round_status(player1_string, player2_string, round_num)
                
                if status["error"]:
                    print(f"❌ Error in {status['game_dir']}: {status['error']}")
                    results["error"] = status["error"]
                    results["success"] = False
                    break
                
                if not status["needs_execution"]:
                    print(f"✅ Round {round_num:03d} already completed ({status['status']}) - skipping")
                    print(f"📁 Path: {status['game_dir']}")
                    results["rounds_skipped"] += 1
                    results["round_results"].append({
                        "round": round_num,
                        "action": "skipped",
                        "status": status["status"],
                        "path": status["game_dir"]
                    })
                    continue
                
                # Execute this round
                print(f"🎮 Executing round {round_num:03d}...")
                print(f"📁 Path: {status['game_dir']}")
                
                if status["exists"] and status["has_latest"] and status["status"] == "ongoing":
                    print(f"♻️ Resuming from existing save...")
                    result = self.resume_existing_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns)
                else:
                    print(f"🆕 Initializing new round...")
                    result = self.run_single_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns)
                
                results["total_rounds_executed"] += 1
                results["round_results"].append({
                    "round": round_num,
                    "action": "executed",
                    "result": result,
                    "path": status["game_dir"]
                })
                
                if result["success"]:
                    results["rounds_completed"] += 1
                    print(f"✅ Round {round_num:03d} completed successfully")
                else:
                    results["rounds_failed"] += 1
                    print(f"❌ Round {round_num:03d} failed: {result.get('error', 'Unknown error')}")
        
        return results

    def run_single_round(self, player1_name: str, player2_name: str, 
                        player1_model: str, player2_model: str, round_num: int, 
                        max_turns: int = 200) -> Dict[str, Any]:
        """Run a single round (new game).
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            player1_model: Model for player 1
            player2_model: Model for player 2
            round_num: Round number
            max_turns: Maximum turns per game
            
        Returns:
            Dictionary with game results
        """
        # Create players
        player1 = OllamaPlayer(player1_name, player1_model, debug=self.debug)
        player2 = OllamaPlayer(player2_name, player2_model, debug=self.debug)
        
        # Set game manager references for save functionality
        player1.set_game_manager(self, player2)
        player2.set_game_manager(self, player1)
        
        # Clear any existing round directory
        game_dir = self.persistent_manager.get_game_dir(player1.player_string, player2.player_string, round_num)
        if game_dir.exists():
            import shutil
            shutil.rmtree(game_dir)
        
        # Initialize new game
        game = self.persistent_manager.initialize_new_game(
            player1.player_string, 
            player2.player_string,
            (player1_name, player2_name),
            self.max_tries,
            round_num
        )
        
        # Set game context
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        
        # Run the game using existing logic
        return self._execute_game_loop(game, player1, player2, max_turns, round_num)

    def resume_existing_round(self, player1_name: str, player2_name: str,
                             player1_model: str, player2_model: str, round_num: int,
                             max_turns: int = 200) -> Dict[str, Any]:
        """Resume an existing round from latest.pkl.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            player1_model: Model for player 1
            player2_model: Model for player 2
            round_num: Round number
            max_turns: Maximum turns per game
            
        Returns:
            Dictionary with game results
        """
        # Create players
        player1 = OllamaPlayer(player1_name, player1_model, debug=self.debug)
        player2 = OllamaPlayer(player2_name, player2_model, debug=self.debug)
        
        # Set game manager references for save functionality
        player1.set_game_manager(self, player2)
        player2.set_game_manager(self, player1)
        
        # Load existing game
        game = self.persistent_manager.load_game_state(player1.player_string, player2.player_string, round_num)
        
        # Set game context
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        
        # Continue the game using existing logic
        return self._execute_game_loop(game, player1, player2, max_turns, round_num)
        
    def create_ai_vs_ai_game(self, player1_name: str = "AI Player 1", 
                           player2_name: str = "AI Player 2", player1_model: Optional[str] = None, 
                           player2_model: Optional[str] = None, temperature: float = 0.7, 
                           top_p: float = 0.9) -> tuple[Game, OllamaPlayer, OllamaPlayer]:
        """Create a new AI vs AI game.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            player1_model: Model for player 1 (defaults to self.model)
            player2_model: Model for player 2 (defaults to self.model)
            temperature: Temperature for LLM responses
            top_p: Top-p sampling parameter
            
        Returns:
            Tuple of (game, player1, player2)
        """
        # Use provided models or default to self.model
        if player1_model is None:
            player1_model = self.model
        if player2_model is None:
            player2_model = self.model
            
        # Create AI players
        player1 = OllamaPlayer(player1_name, player1_model, temperature, top_p, debug=self.debug)
        player2 = OllamaPlayer(player2_name, player2_model, temperature, top_p, debug=self.debug)
        
        # Set game manager references for save functionality
        player1.set_game_manager(self, player2)
        player2.set_game_manager(self, player1)
        
        # Initialize game with new structure
        game = self.persistent_manager.initialize_new_game(
            player1.player_string, 
            player2.player_string,
            (player1_name, player2_name),
            self.max_tries
        )
        
        # Set game context
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        
        return game, player1, player2
    
    # ------------------------------------------------------------------
    # Global error handling and documentation methods
    # ------------------------------------------------------------------
    
    def _categorize_error(self, exception: Exception) -> str:
        """Categorize errors for consistent handling."""
        
        # LLM/Network errors
        if any(keyword in str(exception).lower() for keyword in ['connection', 'timeout', 'server', 'ollama']):
            return "llm_error"
        
        # Parameter validation errors  
        if isinstance(exception, (ValueError, TypeError)) and any(keyword in str(exception) for keyword in ['invalid literal', 'parameter', 'index']):
            return "parameter_error"
        
        # Game logic errors
        if any(keyword in str(exception) for keyword in ['fish', 'team', 'attack', 'skill']):
            return "game_logic_error"
            
        # System errors (like our KeyError: '0')
        if isinstance(exception, (KeyError, AttributeError)):
            return "system_error"
        
        # Default
        return "unknown_error"
    
    def _format_error_message(self, exception: Exception, error_category: str) -> str:
        """Generate user-friendly error messages."""
        
        if error_category == "parameter_error":
            if "invalid literal" in str(exception) and "None" in str(exception):
                return "Invalid parameter types: received 'None' where number expected"
            elif "missing" in str(exception).lower():
                return "Missing required parameters for action"
            else:
                return "Invalid parameter values provided"
                
        elif error_category == "llm_error":
            return "LLM communication error - server may be unavailable"
            
        elif error_category == "game_logic_error":
            return f"Game logic error: {str(exception)}"
            
        elif error_category == "system_error":
            return "Internal system error - will retry"
            
        else:
            return f"Unexpected error: {str(exception)}"
    
    def _log_detailed_error(self, exception: Exception, attempt: int, player_idx: int, game_turn: int) -> None:
        """Log detailed error information for debugging."""
        if self.debug:
            import traceback
            self._debug_log(f"=== DETAILED ERROR LOG ===")
            self._debug_log(f"Game turn: {game_turn}")
            self._debug_log(f"Player: {player_idx}")
            self._debug_log(f"Attempt: {attempt}")
            self._debug_log(f"Exception type: {type(exception).__name__}")
            self._debug_log(f"Exception message: {str(exception)}")
            self._debug_log(f"Full traceback:")
            for line in traceback.format_exc().split('\n'):
                self._debug_log(f"  {line}")
            self._debug_log(f"=== END ERROR LOG ===")
    
    def _track_error_for_evaluation_safely(self, game: 'Game', player_idx: int, error_category: str) -> None:
        """Track errors in evaluation without causing KeyError."""
        try:
            player_key = str(player_idx + 1)  # Convert 0/1 to "1"/"2"
            
            # Initialize structure if missing
            if not hasattr(game, 'evaluation') or game.evaluation is None:
                game.evaluation = {"players": {}}
            if "players" not in game.evaluation:
                game.evaluation["players"] = {}
            if player_key not in game.evaluation["players"]:
                game.evaluation["players"][player_key] = {
                    "invalid_moves": {"total": 0, "by_type": {}}
                }
            if "invalid_moves" not in game.evaluation["players"][player_key]:
                game.evaluation["players"][player_key]["invalid_moves"] = {"total": 0, "by_type": {}}
                
            # Safe increment
            game.evaluation["players"][player_key]["invalid_moves"]["total"] += 1
            if error_category not in game.evaluation["players"][player_key]["invalid_moves"]["by_type"]:
                game.evaluation["players"][player_key]["invalid_moves"]["by_type"][error_category] = 0
            game.evaluation["players"][player_key]["invalid_moves"]["by_type"][error_category] += 1
            
        except Exception as e:
            # If evaluation tracking fails, just log and continue
            self._debug_log(f"Evaluation tracking failed (non-fatal): {e}")
    
    def _add_history_entry_safely(self, game: 'Game', turn_context: Dict[str, Any]) -> None:
        """Add history entry without triggering evaluation errors."""
        try:
            # Build comprehensive history entry
            history_entry = {
                # Core turn identification
                "player": turn_context["player_idx"] + 1,  # 1 or 2
                "game_turn": game.state.game_turn,
                "player_turn": game.state.player_turn,
                "phase": turn_context["phase"],
                "attempt": turn_context["attempt"],
                
                # LLM interaction data (preserved from current system)
                "input_messages": turn_context.get("prompts", []),
                "response": turn_context.get("llm_response", {}),
                "tool_call": turn_context.get("tool_call"),
                
                # Action/assertion specifics
                "action_type": turn_context.get("action_type"),
                "raw_parameters": turn_context.get("parameters", {}),
                "validated_parameters": turn_context.get("validated_parameters", {}),
                
                # Outcome
                "success": turn_context["success"],
                "result": turn_context.get("result", ""),
                
                # Error information (if failed)
                "error": {
                    "exception": str(turn_context["error"]) if turn_context.get("error") else None,
                    "exception_type": type(turn_context["error"]).__name__ if turn_context.get("error") else None,
                    "error_location": turn_context.get("error_location"),
                    "category": self._categorize_error(turn_context["error"]) if turn_context.get("error") else None
                } if turn_context.get("error") else None,
                
                # Damage tracking (preserved from current system)
                "damage_dealt": getattr(game, 'current_turn_damage', {}).get('dealt', 0),
                "damage_taken": getattr(game, 'current_turn_damage', {}).get('taken', 0),
                
                # Timestamp for debugging
                "timestamp": time.time()
            }
            
            # Debug player indexing in history (Issue 2)
            self._debug_log(f"[HISTORY DEBUG] Writing history entry with player: {history_entry['player']} (from turn_context player_idx: {turn_context['player_idx']})")
            
            # Add to game history
            game.history.append(history_entry)
            
            # Safe evaluation tracking (only for failed attempts)
            if not turn_context["success"] and turn_context.get("error"):
                error_category = history_entry["error"]["category"]
                self._track_error_for_evaluation_safely(game, turn_context["player_idx"], error_category)
                
        except Exception as e:
            # If history tracking fails, just log and continue
            self._debug_log(f"History tracking failed (non-fatal): {e}")
    
    def _save_error_state_safely(self, game: 'Game', player1: OllamaPlayer, player2: OllamaPlayer, 
                                 players_info: Dict[str, Any], exception: Exception, attempt: int) -> None:
        """Save error state for debugging without crashing."""
        try:
            self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, 1, players_info, self.turn_prefix)
            self._debug_log(f"Error state saved for turn {game.state.game_turn} attempt {attempt}")
        except Exception as save_error:
            self._debug_log(f"Failed to save error state (non-fatal): {save_error}")
    
    def _process_turn_error(self, exception: Exception, attempt: int, max_tries: int, 
                           player_idx: int, game: 'Game', player1: OllamaPlayer, player2: OllamaPlayer, 
                           players_info: Dict[str, Any]) -> Dict[str, Any]:
        """Centralized error processing for turn failures."""
        
        # 1. Error categorization
        error_category = self._categorize_error(exception)
        
        # 2. User-friendly message generation  
        user_message = self._format_error_message(exception, error_category)
        
        # 3. Debug logging (detailed technical info)
        self._log_detailed_error(exception, attempt, player_idx, game.state.game_turn)
        
        # 4. Error state preservation
        self._save_error_state_safely(game, player1, player2, players_info, exception, attempt)
        
        return {
            "user_message": user_message,
            "final_error": f"Turn failed after {max_tries} attempts: {user_message}",
            "category": error_category,
            "technical_details": str(exception)
        }
    
    def run_ai_vs_ai_game(self,
                          player1=None, player2=None,
                          max_turns: int = 100,
                          rounds: Optional[int] = None) -> Dict[str, Any]:
        """Run AI vs AI game(s) with multiple rounds support.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            max_turns: Maximum number of turns before forcing end
            player1_model: Model for player 1 (defaults to self.model)
            player2_model: Model for player 2 (defaults to self.model)
            rounds: Number of rounds to execute (None = find first available)
            
        Returns:
            Dictionary with game results
        """
        # If player objects are provided, use them directly
        if player1 is not None and player2 is not None:
            results = self.execute_multiple_rounds_with_players(player1, player2, max_turns, rounds)
        else:
            raise ValueError("Player objects must be provided.")
        # For compatibility with existing CLI, adapt results format for single round mode
        if rounds is None and results["round_results"]:
            for round_result in results["round_results"]:
                if round_result["action"] == "executed":
                    single_result = round_result["result"]
                    if "save_path" not in single_result:
                        single_result["save_path"] = round_result["path"]
                    return single_result
            return {
                "success": results["success"],
                "error": results.get("error", "No rounds needed execution"),
                "rounds_skipped": results["rounds_skipped"],
                "save_path": f"{results['player1_string']}/{results['player2_string']}/"
            }
        return results

    def execute_multiple_rounds_with_players(self, player1, player2, max_turns: int = 200, rounds: Optional[int] = None) -> Dict[str, Any]:
        """Execute multiple rounds using pre-instantiated player objects."""
        player1_string = player1.player_string
        player2_string = player2.player_string
        results = {
            "player1_string": player1_string,
            "player2_string": player2_string,
            "total_rounds_executed": 0,
            "rounds_completed": 0,
            "rounds_skipped": 0,
            "rounds_failed": 0,
            "round_results": [],
            "success": True,
            "error": None
        }
        if rounds is None:
            round_num = 1
            while True:
                status = self.check_round_status(player1_string, player2_string, round_num)
                if status["error"]:
                    results["error"] = status["error"]
                    results["success"] = False
                    # break
                if not (status["needs_execution"] or status["status"] == "error"):
                    results["rounds_skipped"] += 1
                    results["round_results"].append({
                        "round": round_num,
                        "action": "skipped",
                        "status": status["status"],
                        "path": status["game_dir"]
                    })
                    round_num += 1
                    continue
                if status["exists"] and status["has_latest"] and status["status"] == "ongoing":
                    result = self.resume_existing_round_with_players(player1, player2, round_num, max_turns)
                else:
                    result = self.run_single_round_with_players(player1, player2, round_num, max_turns)
                results["total_rounds_executed"] += 1
                results["round_results"].append({
                    "round": round_num,
                    "action": "executed",
                    "result": result,
                    "path": status["game_dir"]
                })
                if result["success"]:
                    results["rounds_completed"] += 1
                    break
                else:
                    results["rounds_failed"] += 1
                    break
        else:
            for round_num in range(1, rounds + 1):
                status = self.check_round_status(player1_string, player2_string, round_num)
                if status["error"]:
                    results["error"] = status["error"]
                    # break
                if not (status["needs_execution"] or status["status"] == "error"):
                    results["rounds_skipped"] += 1
                    results["round_results"].append({
                        "round": round_num,
                        "action": "skipped",
                        "status": status["status"],
                        "path": status["game_dir"]
                    })
                    continue
                if status["exists"] and status["has_latest"] and status["status"] == "ongoing":
                    result = self.resume_existing_round_with_players(player1, player2, round_num, max_turns)
                else:
                    result = self.run_single_round_with_players(player1, player2, round_num, max_turns)
                results["total_rounds_executed"] += 1
                results["round_results"].append({
                    "round": round_num,
                    "action": "executed",
                    "result": result,
                    "path": status["game_dir"]
                })
                if result["success"]:
                    results["rounds_completed"] += 1
                else:
                    results["rounds_failed"] += 1
        return results

    def run_single_round_with_players(self, player1, player2, round_num: int, max_turns: int = 200) -> Dict[str, Any]:
        """Run a single round (new game) with player objects."""
        player1.set_game_manager(self, player2)
        player2.set_game_manager(self, player1)
        game_dir = self.persistent_manager.get_game_dir(player1.player_string, player2.player_string, round_num)
        print(f"[GAME DIR] {game_dir}")
        if game_dir.exists():
            import shutil
            shutil.rmtree(game_dir)
        game = self.persistent_manager.initialize_new_game(
            player1.player_string,
            player2.player_string,
            (player1.name, player2.name),
            # self.max_tries,
            round_num
        )
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        return self._execute_game_loop(game, player1, player2, max_turns, round_num)

    def resume_existing_round_with_players(self, player1, player2, round_num: int, max_turns: int = 200) -> Dict[str, Any]:
        player1.set_game_manager(self, player2)
        player2.set_game_manager(self, player1)
        game = self.persistent_manager.load_game_state(player1.player_string, player2.player_string, round_num)
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        return self._execute_game_loop(game, player1, player2, max_turns, round_num)
    
    def _display_team_status(self, game: Game):
        """Display current status of both teams."""
        print("\n--- Team Status ---")
        for i, player in enumerate(game.state.players):
            if player.team:
                living_count = len(player.team.living_fish())
                total_hp = sum(f.hp for f in player.team.fish if f.is_alive())
                print(f"{player.name}: {living_count}/4 fish alive, {total_hp} total HP")
        print("-------------------")

    def _get_players_info(self, player1: BasePlayer, player2: BasePlayer) -> Dict[str, Any]:
        """Build players info dictionary for saving."""
        return {
            # "1": [{"name": f"{player1.model} (Single)", "model": player1.model, "temperature": player1.temperature, "top_p": player1.top_p}],
            # "2": [{"name": f"{player2.model} (Single)", "model": player2.model, "temperature": player2.temperature, "top_p": player2.top_p}]
            "1": player1.get_player_info(),
            "2": player2.get_player_info()
        }

    def _save_callback(self, game, player1, player2, round_num, players_info, turn_prefix):
        self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, turn_prefix)

    def _execute_game_loop(self, game: Game, player1: BasePlayer, player2: BasePlayer, 
                          max_turns: int, round_num: int) -> Dict[str, Any]:
        """Execute the main game loop for a round.
        
        Args:
            game: Game instance
            player1: Player 1
            player2: Player 2 current_player
            max_turns: Maximum turns per game
            round_num: Round number
            
        Returns:
            Dictionary with game results
        """
        self._debug_log(f"=== Starting game loop for round {round_num} ===")
        players = [player1, player2]
        players_info = self._get_players_info(player1, player2)
        self._debug_log(f"Players:\n{players_info['1']}\n{players_info['2']}")
        # Attempt counter
        attempt = 0
        
        try:
            # Check if teams are already selected
            teams_selected = all(player.team is not None for player in game.state.players)
            
            if not teams_selected:
                print("Team selection phase...")
                # Team selection phase
                for i, player in enumerate(players):
                    if game.state.players[i].team is None:
                        print(f"\n{player.name} selecting team...")
                        available_fish = game.state.players[i].roster.copy()
                        
                        try:
                            # Create save callback for sequential turn files
                            def save_callback():
                                self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)

                            # action = player.make_team_selection(available_fish, self.max_tries, save_callback)
                            action = player.make_team_selection(available_fish, player.max_tries, save_callback)
                            
                            if not action.success:
                                print(f"❌ Team selection failed for {player.name}: {action.message}")
                                # Ensure game status is set to error for failed team selection
                                game._update_evaluation_game_status("error")
                                # Save the failed turn with error status
                                self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)
                                return {
                                    "success": False,
                                    "error": f"Team selection failed for {player.name}: {action.message}",
                                    "turn": game.state.game_turn,
                                    "phase": "team_selection",
                                    "save_path": f"{player1.player_string}/{player2.player_string}/round_{round_num:03d}/"
                                }
                            
                        except Exception as team_error:
                            # Critical error during team selection - use master error handler
                            self._debug_log(f"Critical error during team selection for {player.name}: {team_error}")
                            self._log_detailed_error(team_error, attempt, i, game.state.game_turn)
                            return self._handle_turn_execution_error(
                                team_error, game, player1, player2, round_num, 
                                f"team_selection_{player.name}"
                            )
                        
                        print(f"✓ {action.message}")
                        # Save after each team selection
                        self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)
            else:
                print("Teams already selected, continuing battle phase...")
            
            print("\nStarting/continuing battle phase...")
            
            # Main game loop
            # game_turn = 0
            game_turn = game.state.game_turn
            while game_turn < max_turns:
                game_turn += 1
                current_player_idx = game.state.current_player - 1  # Convert 1/2 to 0/1
                current_player = players[current_player_idx]
                
                print(f"\nGame Turn {game_turn}: {current_player.name}'s turn (Player Turn {game.state.player_turn})")
                print(f"Phase: {game.state.phase}")
                
                # Check for round over
                winner = game.round_over()
                if winner is not None: # Also applies to voters
                    winner_name = game.state.players[winner].name
                    print(f"\n🎉 Game Over! {winner_name} wins!")
                    
                    # Update evaluation: game completed
                    game._update_evaluation_game_status("completed")

                    self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)

                    return {
                        "success": True,
                        "winner": winner,
                        "winner_name": winner_name,
                        "turns": game_turn,
                        "save_path": f"{player1.player_string}/{player2.player_string}/round_{round_num:03d}/"
                    }
                
                # Execute turn with global error handling
                self._debug_log(f"Starting turn execution - Game turn: {game_turn}, Current player: {current_player_idx}, Phase: {game.state.phase}")
                success = False
                
                # if attempt < self.max_tries:
                if attempt < current_player.max_tries:

                    attempt += 1
                    # Create turn context for documentation
                    turn_context = {
                        # "attempt": attempt + 1,
                        "attempt": attempt,
                        "player_idx": current_player_idx,
                        "phase": game.state.phase,
                        "game_turn": game.state.game_turn,
                        "success": False,
                        "error": None
                    }
                    # self._debug_log(f"Attempt {attempt}/{self.max_tries}")
                    self._debug_log(f"Attempt {attempt}/{current_player.max_tries}")
                    
                    try:
                        # Business logic with context capture
                        result = None
                        context = {}

                        current_phase = game.state.phase

                        if current_phase == "assertion":
                            self._debug_log("Executing assertion phase")
                            result, context, _ = current_player.make_assertion_simple_with_context()
                            # print(f"Assertion (attempt {attempt + 1}): {result}")
                            print(f"Assertion (attempt {attempt}): {result}")

                        elif current_phase == "action":
                            self._debug_log(f"Executing action phase ({current_player.name})")
                            result, context, _ = current_player.make_action_simple_with_context()
                            # print(f"Action (attempt {attempt + 1}): {result}")
                            print(f"Action (attempt {attempt}): {result}")

                        # Success - merge contexts and document
                        turn_context.update(context)
                        valid = context.get("success", False)
                        # turn_context["success"] = valid
                        turn_context["result"] = result
                        
                        # Document successful attempt with correct attempt number
                        player = player1 if current_player_idx == 0 else player2
                        game.add_history_entry_unified(
                            current_player_idx,  # player_index (0-based)
                            context.get("prompts", []),  # input_messages from context
                            {
                                "content": str(result),
                                "context": context,
                                "turn_context": turn_context
                            },  # response dict
                            valid,  # valid = True for successful attempts
                            f"Turn {game.state.game_turn}: {current_phase.capitalize()} - {result}",  # move_description
                            # attempt=attempt+1,
                            attempt=attempt,
                            # max_attempts=self.max_tries,
                            max_attempts=current_player.max_tries,
                        )
                        
                        success = context.get("success", False)
                        if success:
                            attempt = 0
                            self._debug_log("Turn successful, resetting attempts counter")
                        else:
                            # self._debug_log(f"Turn failed, {self.max_tries - attempt} attempts remaining")
                            self._debug_log(f"Turn failed, {current_player.max_tries - attempt} attempts remaining")
                        # self._debug_log("Turn successful, breaking retry loop")
                        # success = True
                        # break
                        
                    except Exception as e:
                        turn_context["error"] = e
                        turn_context["success"] = False
                        
                        # Document failed attempt with full context
                        # NEW: Using unified history function called directly in business logic
                        
                        # Process error for retry logic
                        # error_info = self._process_turn_error(e, attempt+1, self.max_tries, current_player_idx, game, player1, player2, players_info)
                        error_info = self._process_turn_error(e, attempt+1, current_player.max_tries, current_player_idx, game, player1, player2, players_info)
                        
                        print(f"❌ Turn failed: {error_info['user_message']}")
                        
                        # Save after each failed turn attempt 
                        try:
                            self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)
                            self._debug_log(f"Sequential save completed for failed turn attempt {attempt + 1}")
                        except Exception as save_error:
                            self._debug_log(f"Failed to save after failed turn attempt {attempt + 1}: {save_error}")
                        
                        # if attempt < self.max_tries - 1:
                            # print(f"Retrying... ({attempt + 2}/{self.max_tries})")
                        if attempt < current_player.max_tries - 1:
                            print(f"Retrying... ({attempt + 2}/{current_player.max_tries})")
                
                # if not success and attempt >= self.max_tries:
                if not success and attempt >= current_player.max_tries:
                    # print(f"❌ Turn failed after {self.max_tries} attempts. Terminating game.")
                    print(f"❌ Turn failed after {attempt} attempts. Terminating game.")
                    game._update_evaluation_game_status("error")
                    self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)
                    return {
                        "success": False,
                        # "error": f"Turn failed after {self.max_tries} attempts",
                        "error": f"Turn failed after {current_player.max_tries} attempts",
                        "turns": game_turn,
                        "save_path": f"{player1.player_string}/{player2.player_string}/round_{round_num:03d}/"
                    }
                
                # Save after each turn
                self._debug_log("Starting post-turn save operation")
                self.persistent_manager.save_game_state(game, player1.player_string, player2.player_string, round_num, players_info, self.turn_prefix)
                self._debug_log("Save operation completed")
                
                # Display current team status
                self._debug_log("Starting team status display")
                self._display_team_status(game)
                self._debug_log("Team status display completed")
            
            # Game exceeded max turns
            game._update_evaluation_game_status("timeout")
            return {
                "success": False,
                "error": f"Game exceeded maximum turns ({max_turns})",
                "turns": game_turn,
                "save_path": f"{player1.player_string}/{player2.player_string}/round_{round_num:03d}/"
            }
            
        except Exception as e:
            # Use master error handler to ensure KEY REQUIREMENTS are met
            self._debug_log(f"Critical error in game loop: {e}")
            return self._handle_turn_execution_error(e, game, player1, player2, round_num, "game_loop")