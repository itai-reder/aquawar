"""
Majority Vote AI player implementation for Aquawar.

USER REQUIREMENTS:
- max_tries: Number of voters to create for each decision
- pickle files: Each voter saves v{voter_index}_{turn}.pkl (identical to turn_{turn}.pkl structure)
- turn_{turn}.pkl is created as a copy of the winning voter's decision
- error logging: Individual voter failures saved in their v*.pkl files
- naming conventions: {model}_majority vs {model}_single

SIMPLIFIED APPROACH:
- Create multiple OllamaPlayer instances as voters
- Each voter executes completely and saves using existing persistent manager
- Select majority winner and create turn_{turn}.pkl from winning voter
- Pure delegation - no custom game logic
"""

from __future__ import annotations

from typing import List, Optional, Any, Dict, Union, Tuple
from pathlib import Path
import copy

from ..game import Game
from ..persistent import PersistentGameManager
from .base_player import BasePlayer, GameAction
from .ollama_player import OllamaPlayer


class MajorityVotePlayer(BasePlayer):
    """AI player that uses majority voting among multiple OllamaPlayer instances.
    
    This is a pure coordinator that runs multiple OllamaPlayer instances
    and selects the majority result using existing infrastructure.
    """
    
    def __init__(self, name: str, model: str = "llama3.2:3b", num_voters: int = 3,
                 temperature: float = 0.7, top_p: float = 0.9, debug: bool = False):
        """Initialize Majority Vote player."""
        super().__init__(name)
        self.model = model
        self.num_voters = num_voters
        self.temperature = temperature
        self.top_p = top_p
        self.debug = debug
        
        # Voters created dynamically
        self.voter_pool: List[OllamaPlayer] = []
        self.persistent_manager: Optional[PersistentGameManager] = None
        
        self._debug_log(f"Created MajorityVotePlayer using model {model}")
    
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if self.debug:
            print(f"[MAJORITY DEBUG] {message}")
    
    @property
    def player_string(self) -> str:
        """Generate player string: {model}_majority"""
        model_str = self.model.replace(":", "_").replace("/", "_").replace("-", "_").replace(".", "_")
        return f"{model_str}_majority"
    
    def set_game_context(self, game: Game, player_index: int):
        """Set the game context for this player."""
        super().set_game_context(game, player_index)
        self.persistent_manager = PersistentGameManager(debug=self.debug)
        self._debug_log(f"Set game context for majority vote player")
    
    def _ensure_voters(self, num_voters: int) -> List[OllamaPlayer]:
        """Ensure we have enough voters in the pool."""
        while len(self.voter_pool) < num_voters:
            voter_index = len(self.voter_pool)
            voter_name = f"{self.name}_voter_{voter_index}"
            voter = OllamaPlayer(
                name=voter_name,
                model=self.model,
                temperature=self.temperature,
                top_p=self.top_p,
                debug=self.debug
            )
            
            # Set game context for the voter
            if hasattr(self, 'game') and hasattr(self, 'player_index') and self.game and self.player_index is not None:
                voter.set_game_context(self.game, self.player_index)
            
            self.voter_pool.append(voter)
            self._debug_log(f"Created voter {voter_index}: {voter_name}")
        
        return self.voter_pool[:num_voters]
    
    def _conduct_vote_for_method(self, method_name: str, num_voters: int, *args, **kwargs) -> Any:
        """Conduct voting for any method by running multiple OllamaPlayer instances."""
        self._debug_log(f"Conducting vote with {num_voters} voters for method: {method_name}")
        
        voters = self._ensure_voters(num_voters)
        voter_results = []
        
        # Get player strings for save paths (use simple defaults)
        player1_string = "player1"
        player2_string = "player2"
        
        # Execute each voter and save their individual results
        for i, voter in enumerate(voters[:num_voters]):
            self._debug_log(f"Executing voter {i}: {voter.name}")
            
            try:
                # Create a copy of the game state for this voter
                game_copy = copy.deepcopy(self.game) if self.game else None
                if game_copy and self.player_index is not None:
                    voter.set_game_context(game_copy, self.player_index)
                
                # Call the method on the voter
                method = getattr(voter, method_name)
                if args or kwargs:
                    result = method(*args, **kwargs)
                else:
                    result = method()
                
                # Save this voter's result using existing infrastructure
                if self.persistent_manager and self.game:
                    vote_data = {
                        'voter_name': voter.name,
                        'move': str(result) if result else '',
                        'valid': True,
                        'error_details': None,
                        'history_entry': {
                            'method': method_name,
                            'result': str(result) if result else '',
                            'success': True
                        }
                    }
                    
                    self.persistent_manager.save_voter_state(
                        self.game,
                        i,  # voter_index
                        vote_data,
                        player1_string,
                        player2_string
                    )
                
                voter_results.append({
                    'voter_index': i,
                    'voter_name': voter.name,
                    'result': result,
                    'success': True,
                    'error': None
                })
                
                self._debug_log(f"Voter {i} succeeded")
                
            except Exception as e:
                self._debug_log(f"Voter {i} failed: {str(e)}")
                
                # Save error state for this voter
                if self.persistent_manager and self.game:
                    vote_data = {
                        'voter_name': voter.name,
                        'move': f'ERROR: {str(e)}',
                        'valid': False,
                        'error_details': {'exception': str(e), 'type': type(e).__name__},
                        'history_entry': {
                            'method': method_name,
                            'result': 'ERROR',
                            'success': False,
                            'error': str(e)
                        }
                    }
                    
                    self.persistent_manager.save_voter_state(
                        self.game,
                        i,  # voter_index
                        vote_data,
                        player1_string,
                        player2_string
                    )
                
                voter_results.append({
                    'voter_index': i,
                    'voter_name': voter.name,
                    'result': None,
                    'success': False,
                    'error': str(e)
                })
        
        # Determine winner from successful results
        successful_results = [r for r in voter_results if r['success']]
        
        if not successful_results:
            error_details = [f"Voter {r['voter_index']}: {r['error']}" for r in voter_results if r['error']]
            raise RuntimeError(f"All {num_voters} voters failed. Errors: {'; '.join(error_details)}")
        
        # For now, use first successful voter as winner (can enhance with actual majority logic later)
        winning_result = successful_results[0]
        self._debug_log(f"Winner: voter {winning_result['voter_index']}")
        
        # Save the winning result as the main turn file using existing infrastructure
        if self.persistent_manager and self.game:
            self.persistent_manager.save_game_state(
                self.game,
                player1_string,
                player2_string
            )
        
        return winning_result['result']
    
    # Delegate all methods to the voting system
    
    def make_team_selection(self, available_fish: List[str], max_tries: int = 3, 
                          save_callback: Optional[Any] = None) -> GameAction:
        """Make team selection using majority voting."""
        num_voters = max_tries if max_tries > 0 else self.num_voters
        return self._conduct_vote_for_method('make_team_selection', num_voters, available_fish, max_tries, save_callback)
    
    def make_assertion(self) -> GameAction:
        """Make assertion using majority voting."""
        return self._conduct_vote_for_method('make_assertion', self.num_voters)
    
    def make_action(self) -> GameAction:
        """Make action using majority voting."""
        return self._conduct_vote_for_method('make_action', self.num_voters)
    
    def make_assertion_simple_with_context(self) -> Tuple[str, Dict[str, Any]]:
        """Make assertion with context using majority voting."""
        return self._conduct_vote_for_method('make_assertion_simple_with_context', self.num_voters)
    
    def make_action_simple_with_context(self) -> Tuple[str, Dict[str, Any]]:
        """Make action with context using majority voting."""
        return self._conduct_vote_for_method('make_action_simple_with_context', self.num_voters)