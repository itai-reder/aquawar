"""Base AI player interface for Aquawar."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

from langchain_core.runnables.utils import Output

if TYPE_CHECKING:
    from ..game import Game


@dataclass
class GameAction:
    """Represents a game action with validation info."""
    action_type: str
    success: bool
    message: str
    validity: str = "valid"
    captured_response: Optional[Dict] = None  # Store full LLM response for debugging
    raw_response: Optional[Output] = None  # Store raw LLM output object for debugging

class BasePlayer(ABC):
    """Abstract base class for AI players."""
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if getattr(self, 'debug', False):
            print(f"[DEBUG] {message}")
    def __init__(self, name: str, *args):
        """Initialize the AI player.
        
        Args:
            name: Player name
        """
        self.name = name
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
    
    # @abstractmethod
    # def make_team_selection(self, available_fish: List[str], max_tries: int = 3) -> GameAction:
    #     """Make team selection using AI decision making.
        
    #     Args:
    #         available_fish: List of available fish names
    #         max_tries: Maximum number of retry attempts
            
    #     Returns:
    #         GameAction with selection result
    #     """
    #     pass
    
    # @abstractmethod
    # def make_assertion(self) -> GameAction:
    #     """Make assertion decision using AI.
        
    #     Returns:
    #         GameAction with assertion result
    #     """
    #     pass
    
    # @abstractmethod
    # def make_action(self) -> GameAction:
    #     """Make action decision using AI.
        
    #     Returns:
    #         GameAction with action result
    #     """
    #     pass