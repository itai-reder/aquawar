from langchain_core.tools import tool
from typing import List, Optional
# Tool definitions for Langchain

@tool
def select_team_tool(fish_indices: str, mimic_choice: str = "") -> str:
    """Select your team of 4 fish from the available roster.
    
    Args:
        fish_indices: Comma-separated fish indices like "0,1,2,3" (4 fish from roster 0-11)
        mimic_choice: Fish name for Mimic Fish to copy (required if Mimic Fish selected)
    
    Returns:
        String describing the result of team selection
    """
    return f"Tool called: select_team with indices {fish_indices}, mimic: {mimic_choice}"


@tool
def assert_fish_tool(enemy_index: str, fish_name: str) -> str:
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
def normal_attack_tool(fish_index: str, target_index: str) -> str:
    """Perform a normal attack with one of your fish.
    
    Args:
        fish_index: Index of your fish to attack with (0-3)
        target_index: Index of enemy fish to attack (0-3)
    
    Returns:
        String describing the attack result
    """
    return f"Tool called: normal_attack - fish {fish_index} attacks enemy {target_index}"


@tool
def active_skill_tool(fish_index: str, target_index: str = "") -> str:
    """Use the active skill of one of your fish.
    
    Args:
        fish_index: Index of your fish to use skill with (0-3)
        target_index: Target index if skill requires a target (optional, leave empty if not needed)
    
    Returns:
        String describing the skill usage result
    """
    return f"Tool called: active_skill - fish {fish_index} uses skill on target {target_index}"

