"""Ollama AI player implementation for Aquawar using Langchain."""

from __future__ import annotations

import json
from typing import List, Optional, Any, Dict, Union
from pathlib import Path

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from pydantic import BaseModel, Field

from ..game import Game, FISH_NAMES
from ..persistent import PersistentGameManager
from ..config import GameConfig
from .base_player import BasePlayer, GameAction


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


# Tool definitions for Langchain
@tool
def select_team_tool(fish_indices: List[int], mimic_choice: Optional[str] = None) -> str:
    """Select your team of 4 fish from the available roster.
    
    Args:
        fish_indices: List of 4 fish indices to select (0-11 from roster)
        mimic_choice: Fish name for Mimic Fish to copy (required if Mimic Fish selected)
    
    Returns:
        String describing the result of team selection
    """
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
def select_team_tool_gpt_oss(fish_indices: str, mimic_choice: str = "") -> str:
    """Select your team of 4 fish from the available roster (GPT-OSS compatible).
    
    Args:
        fish_indices: Comma-separated fish indices like "0,1,2,3" (4 fish from roster 0-11)
        mimic_choice: Fish name for Mimic Fish to copy (required if Mimic Fish selected)
    
    Returns:
        String describing the result of team selection
    """
    return f"Tool called: select_team with indices {fish_indices}, mimic: {mimic_choice}"


@tool
def assert_fish_tool_gpt_oss(enemy_index: str, fish_name: str) -> str:
    """Assert the identity of a hidden enemy fish (GPT-OSS compatible).
    
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
def normal_attack_tool_gpt_oss(fish_index: str, target_index: str) -> str:
    """Perform a normal attack with one of your fish (GPT-OSS compatible).
    
    Args:
        fish_index: Index of your fish to attack with (0-3)
        target_index: Index of enemy fish to attack (0-3)
    
    Returns:
        String describing the attack result
    """
    return f"Tool called: normal_attack - fish {fish_index} attacks enemy {target_index}"


@tool
def active_skill_tool_gpt_oss(fish_index: str, target_index: str = "") -> str:
    """Use the active skill of one of your fish (GPT-OSS compatible).
    
    Args:
        fish_index: Index of your fish to use skill with (0-3)
        target_index: Target index if skill requires a target (optional, leave empty if not needed)
    
    Returns:
        String describing the skill usage result
    """
    return f"Tool called: active_skill - fish {fish_index} uses skill on target {target_index}"


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


class OllamaPlayer(BasePlayer):
    """AI player using Ollama LLM with Langchain tool calling."""
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if getattr(self, 'debug', False):
            print(f"[DEBUG] {message}")

    def __init__(self, name: str, model: str = "llama3.2:3b", temperature: float = 0.7, top_p: float = 0.9, debug: bool = False):
        """Initialize Ollama player.
        
        Args:
            name: Player name
            model: Ollama model to use 
            temperature: Temperature for LLM responses
            top_p: Top-p sampling parameter
        """
        super().__init__(name)
        self.debug = debug
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        
        # Select tools based on model compatibility
        if "gpt-oss" in model.lower():
            # Use string-based tools for GPT-OSS models
            tools = [
                select_team_tool_gpt_oss,
                assert_fish_tool_gpt_oss,
                skip_assertion_tool,
                normal_attack_tool_gpt_oss,
                active_skill_tool_gpt_oss
            ]
        else:
            # Use standard tools for other models
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
        ).bind_tools(tools)
        
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
    
    def _capture_full_response(self, response) -> str:
        """Capture full LLM response details for debugging purposes."""
        import json
        
        response_data = {
            "content": str(response.content) if hasattr(response, 'content') else None,
            "response_metadata": getattr(response, 'response_metadata', {}),
            "tool_calls": [],
            "raw_response_type": str(type(response)),
        }
        
        # Try to extract tool calls
        try:
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls:
                for tool_call in tool_calls:
                    call_data = {
                        "name": getattr(tool_call, 'name', str(tool_call)),
                        "args": getattr(tool_call, 'args', {}),
                        "id": getattr(tool_call, 'id', None),
                        "raw": str(tool_call)
                    }
                    response_data["tool_calls"].append(call_data)
        except Exception as e:
            response_data["tool_call_extraction_error"] = str(e)
        
        # Try to get any additional attributes
        try:
            response_data["additional_attrs"] = {
                attr: str(getattr(response, attr))[:200] for attr in dir(response) 
                if not attr.startswith('_') and attr not in ['content', 'response_metadata', 'tool_calls']
            }
        except Exception as e:
            response_data["attr_extraction_error"] = str(e)
        
        try:
            return json.dumps(response_data, indent=2)
        except Exception as e:
            return f"JSON serialization failed: {e}\nRaw response: {str(response)[:500]}"

    def _extract_tool_call(self, response: BaseMessage) -> Optional[Dict[str, Any]]:
        """Extract tool call from response if available."""
        self._debug_log(f"_extract_tool_call: entering with response type {type(response)}")
        try:
            # Try to access tool_calls attribute if it exists
            self._debug_log(f"_extract_tool_call: accessing tool_calls attribute")
            tool_calls = getattr(response, 'tool_calls', None)
            self._debug_log(f"_extract_tool_call: tool_calls = {tool_calls}")
            if tool_calls and len(tool_calls) > 0:
                result = tool_calls[0]
                self._debug_log(f"_extract_tool_call: returning {result}")
                return result
        except (AttributeError, IndexError) as e:
            self._debug_log(f"_extract_tool_call: caught exception {e} (type: {type(e).__name__})")
            pass
        except Exception as e:
            self._debug_log(f"_extract_tool_call: unexpected exception {e} (type: {type(e).__name__})")
            raise
        self._debug_log(f"_extract_tool_call: returning None")
        return None

    def make_team_selection(self, available_fish: List[str], max_tries: int = 3) -> GameAction:
        """Make team selection using LLM tool calling with retry logic.
        
        Args:
            available_fish: List of available fish names
            max_tries: Maximum number of retry attempts
            
        Returns:
            GameAction with selection result and captured response
        """
        if not self.game or self.player_index is None:
            return GameAction("select_team", False, "No game context set", "invalid action")
        
        prompt = self.game.prompt_for_selection(self.player_index)
        messages = [prompt]  # Exact messages passed to llm.invoke()
        responses = []
        
        for attempt in range(max_tries):
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
                if attempt > 0 and responses:
                    last_error = f"Previous attempt failed: {responses[-1].get('error', 'Unknown error')}"
                    messages.append(last_error)
                    llm_input[1] = ("user", llm_input[1][1] + f"\n\nPREVIOUS ERROR: {last_error}\nPlease correct the issue and try again.")
                
                # Increment game turn for each LLM invocation attempt
                self.game.increment_game_turn()
                
                response = self.llm.invoke(llm_input)
                response_dict = json.loads(response.model_dump_json())  # Raw LLM response object
                responses.append(response_dict)
                
                tool_call = self._extract_tool_call(response)
                if not tool_call:
                    response_dict["error"] = "No tool call made"
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                if tool_call['name'] not in ['select_team_tool', 'select_team_tool_gpt_oss']:
                    response_dict["error"] = f"Wrong tool called: {tool_call['name']}"
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                args = tool_call['args']
                
                # Handle different tool formats based on model
                if "gpt-oss" in self.model.lower() and tool_call['name'] == 'select_team_tool_gpt_oss':
                    # Parse comma-separated string format for GPT-OSS
                    fish_indices_str = args.get('fish_indices', '')
                    mimic_choice = args.get('mimic_choice', '') or None
                    
                    # Convert "0,1,2,3" to [0,1,2,3]
                    try:
                        fish_indices = [int(x.strip()) for x in fish_indices_str.split(',') if x.strip()]
                    except (ValueError, TypeError):
                        response_dict["error"] = f"Invalid fish indices format: {fish_indices_str}"
                        if attempt == max_tries - 1:  # Last attempt
                            break
                        continue
                        
                    # Convert empty string to None for mimic_choice
                    if mimic_choice == "":
                        mimic_choice = None
                else:
                    # Standard format for other models
                    fish_indices = args.get('fish_indices', [])
                    mimic_choice = args.get('mimic_choice')
                
                # Validate indices
                if len(fish_indices) != 4:
                    response_dict["error"] = "Must select exactly 4 fish"
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                for idx in fish_indices:
                    if not isinstance(idx, int) or idx < 0 or idx >= len(available_fish):
                        response_dict["error"] = f"Invalid fish index: {idx}"
                        if attempt == max_tries - 1:  # Last attempt
                            break
                        continue
                
                # Convert indices to fish names
                fish_names = [available_fish[i] for i in fish_indices]
                
                # Check for Mimic Fish
                if "Mimic Fish" in fish_names and not mimic_choice:
                    response_dict["error"] = "Mimic Fish selected but no mimic choice provided"
                    if attempt == max_tries - 1:  # Last attempt
                        break
                    continue
                
                # Success! Make the selection
                self.game.select_team(self.player_index, fish_names, mimic_choice)
                
                # Track in history with retry information
                response_text = f"Selected fish indices: {fish_indices}"
                if mimic_choice:
                    response_text += f", Mimic choice: {mimic_choice}"
                
                # Get the latest response for history
                latest_response = responses[-1] if responses else {"content": "No response data"}
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, latest_response, True, response_text
                )
                
                return GameAction("select_team", True, f"Selected team: {fish_names}", "valid")
                
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
                response_dict = {
                    "attempt": attempt + 1,
                    "content": f"OLLAMA SERVER ERROR - No LLM response received:\n{json.dumps(error_details, indent=2)}",
                    "error": f"Server error: {e}"
                }
                responses.append(response_dict)
                
                if attempt == max_tries - 1:  # Last attempt
                    break
        
        # All attempts failed - save failure to history and return error
        final_error = responses[-1].get('error', 'Unknown error') if responses else 'No responses received'
        
        # Increment game turn for failed attempt
        self.game.increment_game_turn()
        
        self.game.add_history_entry_with_retry(
            self.player_index, messages, responses[-1] if responses else {"content": "No response received"}, False, final_error
        )
        
        action = GameAction("select_team", False, f"Failed after {max_tries} attempts: {final_error}", "invalid action")
        action.captured_response = responses[-1].get('content', '') if responses else ''
        return action
    
    def make_assertion(self) -> GameAction:
        """Make assertion decision using LLM tool calling.
        
        Returns:
            GameAction with assertion result
        """
        if not self.game or self.player_index is None:
            return GameAction("assertion", False, "No game context set", "invalid action")
        
        # Increment game turn for any assertion attempt (valid or invalid)
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
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, False, "No tool call made"
                )
                action = GameAction("assertion", False, "No tool call made", "invalid response")
                return action
            
            tool_name = tool_call['name']
            args = tool_call['args']
            
            if tool_name == 'skip_assertion_tool':
                result = self.game.skip_assertion(self.player_index)
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, True, "SKIP"
                )
                return GameAction("assertion", True, result, "valid")
                
            elif tool_name == 'assert_fish_tool' or tool_name == 'assert_fish_tool_gpt_oss':
                enemy_index = args.get('enemy_index')
                fish_name = args.get('fish_name')
                
                if enemy_index is None or fish_name is None:
                    error_msg = "Missing assertion parameters"
                    self.game.add_history_entry_with_retry(
                        self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("assertion", False, error_msg, "invalid argument")
                    return action
                
                # Convert string argument to integer (works for both formats)
                try:
                    enemy_index = int(enemy_index)
                except (ValueError, TypeError):
                    error_msg = f"Invalid enemy_index type: {enemy_index}"
                    self.game.add_history_entry_with_retry(
                        self.player_index, messages, response_dict, False, error_msg
                    )
                    action = GameAction("assertion", False, error_msg, "invalid argument")
                    return action
                
                result = self.game.perform_assertion(self.player_index, enemy_index, fish_name)
                response_text = f"ASSERT {enemy_index} {fish_name}"
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, True, response_text
                )
                return GameAction("assertion", True, result, "valid")
                
            else:
                error_msg = f"Wrong tool called: {tool_name}"
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, False, error_msg
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
            self.game.add_history_entry_with_retry(
                self.player_index, messages, response_dict, False, error_msg
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
        # self._debug_log(f"Game ID: {self.game}")
        if not self.game or self.player_index is None:
            self._debug_log("No game context set for action")
            return GameAction("action", False, "No game context set", "invalid action")
        
        # Increment game turn for any action attempt (valid or invalid)
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
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, False, error_msg
                )
                action = GameAction("action", False, error_msg, "invalid response")
                return action
            
            tool_name = tool_call['name']
            args = tool_call['args']
            
            self._debug_log(f"Processing tool call: name={tool_name}, args={args}")
            
            if tool_name == 'normal_attack_tool' or tool_name == 'normal_attack_tool_gpt_oss':
                self._debug_log(f"Processing normal attack tool")
                fish_index = args.get('fish_index')
                target_index = args.get('target_index')
                self._debug_log(f"Attack parameters: fish_index={fish_index}, target_index={target_index}")
                
                if fish_index is None or target_index is None:
                    error_msg = "Missing attack parameters"
                    self.game.add_history_entry_with_retry(
                        self.player_index, messages, response_dict, False, error_msg
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
                    self.game.add_history_entry_with_retry(
                        self.player_index, messages, response_dict, False, error_msg
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
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, True, response_text
                )
                return GameAction("action", True, result, "valid")
                
            elif tool_name == 'active_skill_tool' or tool_name == 'active_skill_tool_gpt_oss':
                self._debug_log(f"Processing active skill tool")
                fish_index = args.get('fish_index')
                target_index = args.get('target_index')
                self._debug_log(f"Active skill parameters: fish_index={fish_index}, target_index={target_index}")
                
                if fish_index is None:
                    error_msg = "Missing fish index for active skill"
                    self.game.add_history_entry_with_retry(
                        self.player_index, messages, response_dict, False, error_msg
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
                    self.game.add_history_entry_with_retry(
                        self.player_index, messages, response_dict, False, error_msg
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
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, True, response_text
                )
                return GameAction("action", True, result, "valid")
                
            else:
                error_msg = f"Wrong tool called: {tool_name}"
                self.game.add_history_entry_with_retry(
                    self.player_index, messages, response_dict, False, error_msg
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
            self.game.add_history_entry_with_retry(
                self.player_index, messages, response_dict, False, error_msg
            )
            action = GameAction("action", False, error_msg, "invalid action")
            return action


class OllamaGameManager:
    """Manages AI vs AI games using Ollama language models."""
    
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if getattr(self, 'debug', False):
            print(f"[DEBUG] {message}")
    
    def __init__(self, save_dir: str = "saves", model: str = "llama3.2:3b", debug: bool = False):
        """Initialize the game manager.
        
        Args:
            save_dir: Directory for saving games
            model: Ollama model to use for both players
            debug: Enable detailed debug logging
        """
        self.save_dir = save_dir
        self.persistent_manager = PersistentGameManager(save_dir, debug)
        self.model = model
        self.debug = debug
    
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
    
    def _get_players_info(self, player1: OllamaPlayer, player2: OllamaPlayer) -> Dict[str, Any]:
        """Build players info dictionary for saving."""
        return {
            "1": [{"name": f"{player1.model} (Single)", "model": player1.model, "temperature": player1.temperature, "top_p": player1.top_p}],
            "2": [{"name": f"{player2.model} (Single)", "model": player2.model, "temperature": player2.temperature, "top_p": player2.top_p}]
        }
        
    def create_ai_vs_ai_game(self, game_id: str, player1_name: str = "AI Player 1", 
                           player2_name: str = "AI Player 2", config=None) -> tuple[Game, OllamaPlayer, OllamaPlayer]:
        """Create a new AI vs AI game.
        
        Args:
            game_id: Unique game identifier
            player1_name: Name for player 1
            player2_name: Name for player 2
            config: Optional GameConfig for player setup
            
        Returns:
            Tuple of (game, player1, player2)
        """
        # Create or use provided configuration
        if config is None:
            from aquawar.config import create_default_ollama_config
            config = create_default_ollama_config(model=self.model)
        
        # Initialize game with configuration
        game = self.persistent_manager.initialize_new_game(game_id, (player1_name, player2_name), config)
        
        # Create AI players based on configuration
        player1_model = config.player_1.models[0].model
        player1_temp = config.player_1.models[0].temperature
        player1_top_p = config.player_1.models[0].top_p
        player2_model = config.player_2.models[0].model
        player2_temp = config.player_2.models[0].temperature
        player2_top_p = config.player_2.models[0].top_p
        
        player1 = OllamaPlayer(player1_name, player1_model, player1_temp, player1_top_p, debug=self.debug)
        player2 = OllamaPlayer(player2_name, player2_model, player2_temp, player2_top_p, debug=self.debug)
        
        # Set game context
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        
        return game, player1, player2
    
    def run_ai_vs_ai_game(self, game_id: str, max_turns: int = 100, auto_index: bool = True) -> Dict[str, Any]:
        """Run a complete AI vs AI game until completion.
        
        Args:
            game_id: Game identifier (will be auto-indexed if auto_index=True)
            max_turns: Maximum number of turns before forcing end
            auto_index: If True, automatically create indexed save directory
            
        Returns:
            Dictionary with game results
        """
        # Auto-generate indexed game ID if requested
        if auto_index:
            final_game_id = self.get_next_indexed_game_id(game_id)
            print(f"Using auto-indexed game ID: {final_game_id}")
        else:
            final_game_id = game_id
        
        game = None  # Initialize to None for error handling
        try:
            # Create game and players
            game, player1, player2 = self.create_ai_vs_ai_game(final_game_id)
            players = [player1, player2]
            players_info = self._get_players_info(player1, player2)
            
            print(f"Starting AI vs AI game: {player1.name} vs {player2.name}")
            print(f"Using model: {self.model}")
            
            # Team selection phase
            for i, player in enumerate(players):
                print(f"\n{player.name} selecting team...")
                available_fish = game.state.players[i].roster.copy()
                
                # Get max_tries from config if available
                max_tries = 3  # Default
                try:
                    config_path = Path(self.save_dir) / final_game_id / "config.json"
                    if config_path.exists():
                        from aquawar.config import GameConfig
                        config = GameConfig.load_from_file(config_path)
                        max_tries = config.max_tries
                except Exception:
                    pass  # Use default if config loading fails
                
                action = player.make_team_selection(available_fish, max_tries)
                
                if not action.success:
                    print(f"❌ Team selection failed for {player.name}: {action.message}")
                    # Save the failed turn to turn_{game_turn}.pkl
                    try:
                        self.persistent_manager.save_game_state(game, final_game_id, players_info)
                        print(f"Failed turn saved to turn_{game.state.game_turn:03d}.pkl")
                    except Exception as save_error:
                        print(f"Failed to save error state: {save_error}")
                    
                    return {
                        "success": False,
                        "error": f"Team selection failed for {player.name}: {action.message}",
                        "turn": game.state.game_turn,
                        "phase": "team_selection"
                    }
                
                print(f"✓ {action.message}")
                # Save after each team selection
                self.persistent_manager.save_game_state(game, final_game_id, players_info)
            
            print("\nStarting battle phase...")
            
            # Main game loop
            game_turn = 0
            while game_turn < max_turns:
                game_turn += 1
                current_player_idx = game.state.current_player - 1  # Convert 1/2 to 0/1
                current_player = players[current_player_idx]
                
                print(f"\nGame Turn {game_turn}: {current_player.name}'s turn (Player Turn {game.state.player_turn})")
                print(f"Phase: {game.state.phase}")
                
                # Check for round over
                winner = game.round_over()
                if winner is not None:
                    winner_name = game.state.players[winner].name
                    print(f"\n🎉 Game Over! {winner_name} wins!")
                    
                    # Update evaluation: game completed
                    game._update_evaluation_game_status("completed")
                    
                    self.persistent_manager.save_game_state(game, final_game_id, players_info)
                    
                    return {
                        "success": True,
                        "winner": winner,
                        "winner_name": winner_name,
                        "turns": game_turn,
                        "game_id": final_game_id
                    }
                
                # Get max_tries from config
                max_tries = 3  # Default
                try:
                    config_path = Path(self.save_dir) / final_game_id / "config.json"
                    if config_path.exists():
                        from aquawar.config import GameConfig
                        config = GameConfig.load_from_file(config_path)
                        max_tries = config.max_tries
                except Exception:
                    pass
                
                # Execute turn with retry logic
                self._debug_log(f"Starting turn execution - Game turn: {game_turn}, Current player: {current_player_idx}, Phase: {game.state.phase}")
                success = False
                for attempt in range(max_tries):
                    self._debug_log(f"Attempt {attempt + 1}/{max_tries}")
                    action = None
                    if game.state.phase == "assertion":
                        self._debug_log("Executing assertion phase")
                        action = current_player.make_assertion()
                        print(f"Assertion (attempt {attempt + 1}): {action.message}")
                        self._debug_log(f"Assertion result: success={action.success}, message='{action.message}'")
                        
                    elif game.state.phase == "action":
                        self._debug_log(f"Executing action phase ({current_player.name})")
                        action = current_player.make_action()
                        print(f"Action (attempt {attempt + 1}): {action.message}")
                        self._debug_log(f"Action result: success={action.success}, message='{action.message}'")
                    
                    if action and action.success:
                        self._debug_log("Turn successful, breaking retry loop")
                        success = True
                        break
                    else:
                        print(f"❌ Turn failed: {action.message if action else 'No action returned'}")
                        if attempt < max_tries - 1:
                            print(f"Retrying... ({attempt + 2}/{max_tries})")
                        
                if not success:
                    print(f"❌ Turn failed after {max_tries} attempts. Terminating game.")
                    if game:
                        game._update_evaluation_game_status("error")
                        self.persistent_manager.save_game_state(game, final_game_id, players_info)
                    return {
                        "success": False,
                        "error": f"Turn failed after {max_tries} attempts",
                        "turns": game_turn,
                        "game_id": final_game_id
                    }
                
                # Save after each turn
                self._debug_log("Starting post-turn save operation")
                self.persistent_manager.save_game_state(game, final_game_id, players_info)
                self._debug_log("Save operation completed")
                
                # Display current team status
                self._debug_log("Starting team status display")
                self._display_team_status(game)
                self._debug_log("Team status display completed")
            
            # Game exceeded max turns
            if game:
                game._update_evaluation_game_status("timeout")
            return {
                "success": False,
                "error": f"Game exceeded maximum turns ({max_turns})",
                "turns": game_turn,
                "game_id": final_game_id
            }
            
        except Exception as e:
            # Only try to update game status if game variable is available
            if game:
                try:
                    game._update_evaluation_game_status("error")
                except:
                    pass  # Ignore errors when updating evaluation status
            return {
                "success": False,
                "error": f"Game execution error: {str(e)}",
                "game_id": final_game_id
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