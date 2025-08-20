"""Persistent game manager for Aquawar.

Provides save/load functionality with turn-by-turn persistence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

from .game import Game


class PersistentGameManager:
    """Manages persistent Aquawar games with save/load functionality."""
    
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def __init__(self, save_dir: str = "saves", debug: bool = False):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        self.debug = debug
    

    
    def get_game_dir(self, player1_string: str, player2_string: str, round_num: int = 1) -> Path:
        """Get the directory for a specific game using structure saves/{player1}/{player2}/round_001/."""
        return self.save_dir / player1_string / player2_string / f"round_{round_num:03d}"
        
    def get_save_path(self, player1_string: str, player2_string: str, round_num: int = 1, turn: Optional[int] = None) -> Path:
        """Get the save file path for a game using new directory structure."""
        game_dir = self.get_game_dir(player1_string, player2_string, round_num)
        game_dir.mkdir(parents=True, exist_ok=True)
        if turn is not None:
            return game_dir / f"turn_{turn:03d}.pkl"
        return game_dir / "latest.pkl"
    
    def save_game_state(self, game: Game, player1_string: str, player2_string: str, round_num: int = 1, players_info: Optional[Dict[str, Any]] = None) -> str:
        """Save game state and return the save file path.
        
        Args:
            game: Game instance to save
            player1_string: Player 1 string identifier (e.g., 'llama3.1_8b_single')
            player2_string: Player 2 string identifier (e.g., 'llama3.1_8b_single')
            round_num: Round number (defaults to 1)
            players_info: Optional dictionary with player information in format:
                         {"1": [{"name": str, "model": str, "temperature": float, "top_p": float}],
                          "2": [{"name": str, "model": str, "temperature": float, "top_p": float}]}
        """
        save_path = self.get_save_path(player1_string, player2_string, round_num, game.state.game_turn)
        latest_path = self.get_save_path(player1_string, player2_string, round_num)
        
        self._debug_log(f"Saving game state to {save_path} and {latest_path}")
        game.save_game(str(save_path), players_info)
        game.save_game(str(latest_path), players_info)  # Also save as latest
        
        return str(save_path)
    

    def load_game_state(self, player1_string: str, player2_string: str, round_num: int = 1, turn: Optional[int] = None) -> Game:
        """Load game state from save file."""
        if turn is not None:
            save_path = self.get_save_path(player1_string, player2_string, round_num, turn)
        else:
            save_path = self.get_save_path(player1_string, player2_string, round_num)
            
        if not save_path.exists():
            raise FileNotFoundError(f"Save file not found: {save_path}")
            
        return Game.load_game(str(save_path))
    

    
    def initialize_new_game(self, player1_string: str, player2_string: str, player_names: tuple[str, str], max_tries: int = 3, round_num: int = 1) -> Game:
        """Initialize a new game and save it.
        
        Args:
            player1_string: Player 1 string identifier (e.g., 'llama3.1_8b_single')
            player2_string: Player 2 string identifier (e.g., 'llama3.1_8b_single')
            player_names: Tuple of player names
            max_tries: Maximum retry attempts for invalid moves
            round_num: Round number (defaults to 1)
        """
        game = Game(player_names, debug=self.debug, max_tries=max_tries)
        
        # Create game directory
        game_dir = self.get_game_dir(player1_string, player2_string, round_num)
        game_dir.mkdir(parents=True, exist_ok=True)
        
        # Save initial game state
        self.save_game_state(game, player1_string, player2_string, round_num)
        return game
    
