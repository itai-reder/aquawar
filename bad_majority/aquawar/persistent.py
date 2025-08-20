"""Persistent game manager for Aquawar.

Provides save/load functionality with turn-by-turn persistence.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional, Dict, Any, List

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
    
    # ======================================================================
    # Majority Vote Support - Phase 2 Implementation
    # ======================================================================
    
    def get_voter_save_path(self, player1_string: str, player2_string: str, round_num: int, voter_index: int, turn: int) -> Path:
        """Get the save file path for a specific voter's decision.
        
        Args:
            player1_string: Player 1 string identifier
            player2_string: Player 2 string identifier  
            round_num: Round number
            voter_index: Index of the voter (0, 1, 2, ...)
            turn: Turn number
            
        Returns:
            Path to voter's save file (e.g., saves/player1/player2/round_001/v0_003.pkl)
        """
        game_dir = self.get_game_dir(player1_string, player2_string, round_num)
        game_dir.mkdir(parents=True, exist_ok=True)
        return game_dir / f"v{voter_index}_{turn:03d}.pkl"
    
    def save_voter_state(self, game: Game, voter_index: int, vote_data: Dict[str, Any], 
                        player1_string: str, player2_string: str, round_num: int = 1) -> str:
        """Save individual voter's decision and game state.
        
        Args:
            game: Game instance 
            voter_index: Index of the voter making this decision
            vote_data: Dictionary containing voter-specific information:
                      {"voter_name": str, "move": str, "valid": bool, "error_details": Optional[Dict]}
            player1_string: Player 1 string identifier
            player2_string: Player 2 string identifier
            round_num: Round number
            
        Returns:
            Path where voter state was saved
        """
        save_path = self.get_voter_save_path(player1_string, player2_string, round_num, voter_index, game.state.game_turn)
        
        # Create save data combining game state with voter-specific info
        voter_save_data = {
            'voter_index': voter_index,
            'voter_name': vote_data.get('voter_name', f'voter_{voter_index}'),
            'game_state': game._serialize_state(),  # Full game state for this voter
            'move': vote_data.get('move', ''),
            'valid': vote_data.get('valid', False),
            'error_details': vote_data.get('error_details', None),
            'history_entry': vote_data.get('history_entry', None),  # Individual voter's history
            'turn': game.state.game_turn,
            'player_turn': game.state.player_turn
        }
        
        self._debug_log(f"Saving voter {voter_index} state to {save_path}")
        
        # Save voter-specific data
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'wb') as f:
            pickle.dump(voter_save_data, f)
        
        return str(save_path)
    
    def save_majority_decision(self, game: Game, votes: List[Dict[str, Any]], final_decision: Dict[str, Any],
                             player1_string: str, player2_string: str, round_num: int = 1, 
                             players_info: Optional[Dict[str, Any]] = None) -> str:
        """Save the final majority voting decision along with all votes.
        
        Args:
            game: Game instance
            votes: List of all voter decisions
            final_decision: Dictionary with final majority decision:
                          {"final_move": str, "winning_voter_index": int, "vote_counts": Dict}
            player1_string: Player 1 string identifier
            player2_string: Player 2 string identifier
            round_num: Round number
            players_info: Optional player information
            
        Returns:
            Path where majority decision was saved
        """
        # Use existing save_game_state method but with extended data
        save_path = self.get_save_path(player1_string, player2_string, round_num, game.state.game_turn)
        latest_path = self.get_save_path(player1_string, player2_string, round_num)
        
        # Create extended save data with voting information
        majority_save_data = {
            'state': game._serialize_state(),
            'history': getattr(game, 'history', []),
            'evaluation': getattr(game, 'evaluation', game._initialize_evaluation()),
            
            # Majority vote specific data
            'is_majority_vote': True,
            'num_voters': len(votes),
            'votes': votes,
            'final_move': final_decision.get('final_move', ''),
            'winning_voter_index': final_decision.get('winning_voter_index', 0),
            'vote_counts': final_decision.get('vote_counts', {}),
            'all_voters_failed': final_decision.get('all_voters_failed', False)
        }
        
        # Add players info if provided
        if players_info is not None:
            majority_save_data['players'] = players_info
        
        self._debug_log(f"Saving majority decision to {save_path} and {latest_path}")
        
        # Save the majority decision data
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'wb') as f:
            pickle.dump(majority_save_data, f)
        
        # Also save as latest
        with open(latest_path, 'wb') as f:
            pickle.dump(majority_save_data, f)
        
        return str(save_path)
    
    def load_voter_state(self, player1_string: str, player2_string: str, round_num: int, voter_index: int, turn: int) -> Dict[str, Any]:
        """Load a specific voter's state from save file.
        
        Args:
            player1_string: Player 1 string identifier
            player2_string: Player 2 string identifier
            round_num: Round number
            voter_index: Index of the voter
            turn: Turn number
            
        Returns:
            Dictionary with voter's saved state
        """
        save_path = self.get_voter_save_path(player1_string, player2_string, round_num, voter_index, turn)
        
        if not save_path.exists():
            raise FileNotFoundError(f"Voter save file not found: {save_path}")
            
        with open(save_path, 'rb') as f:
            return pickle.load(f)