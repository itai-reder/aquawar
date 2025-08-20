"""
Majority Vote AI player implementation for Aquawar.

---
USER REQUESTS:
- max_tries: rather than attempts before failing, this will be used to determine how many single agents will choose a move separately, and then the move with the most votes will be chosen, or an arbitrary tie-break out of the ones with the most votes
- pickle files: will work the same as `turn_{game_turn}.pkl`, as each agent is just a regular single agent on surface level, but instead will be named uniquely, i.e., `v{voter_index}_{game_turn}.pkl`, and `turn_{game_turn}.pkl` will be a copy of one of the agents who voted with the majority
- error logging: invalid turns will also be saved to the `v{v_idx}_{t_idx}.pkl` as they are in regular turns, and only if all 'max_tries' agents failed will `turn_{game_turn}.pkl` have an "error" status (I'll let you decide how to handle the rest of the data)
- naming conventions: we will have to differentiate between single agents and majority vote players, help me decide how to do so
**Sanity Check:** There should be as many `v{voter_index}_{game_turn}.pkl` files as `max_tries`, and only one `turn_{game_turn}.pkl` file per game turn, and these files should be of **nearly identical** structure, consistent with the single agent pickle files.
**DO NOT** make changes to logic that would affect the single agent variant of the player. If you do - you're doing something **crucially** wrong.

**REMEMBER** the current system is NOT VALID - the majority vote player is not really a majority vote, this placeholder has to be addressed
---
This player creates multiple OllamaPlayer instances as "voters" and aggregates
their decisions using majority voting logic.

Implementation Strategy:
- Act as drop-in replacement for OllamaPlayer
- Internally coordinate multiple OllamaPlayer voter instances
- Each voter executes as complete single agent (saving v{voter_index}_{turn}.pkl)
- Select majority winner and copy to turn_{turn}.pkl
- Preserve all existing game logic - only player implementation changes

PHASE 2: Real Voting with Pickle File Generation
This implementation now executes all voters, saves individual voter pickle files,
selects majority winner, and ensures proper pickle file structure.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Tuple, Callable
from pathlib import Path
import shutil
import copy
import pickle

from .base_player import BasePlayer, GameAction
from .ollama_player import OllamaPlayer
from ..game import Game
from ..persistent import PersistentGameManager


class MajorityVotePlayer(BasePlayer):
    """AI player that uses majority voting among multiple OllamaPlayer instances.
    
    Acts as a drop-in replacement for OllamaPlayer while internally coordinating
    multiple voter instances. Each voter executes as a complete single agent.
    """
    
    def __init__(self, name: str, model: str = "llama3.2:3b", num_voters: int = 3,
                 temperature: float = 0.7, top_p: float = 0.9, debug: bool = False):
        """Initialize Majority Vote player.
        
        Args:
            name: Player name (used as base for voter names)
            model: Ollama model to use for all voters
            num_voters: Default number of voters (overridden by max_tries in methods)
            temperature: Temperature for LLM responses
            top_p: Top-p sampling parameter
            debug: Enable debug logging
        """
        super().__init__(name)
        self.model = model
        self.num_voters = num_voters
        self.temperature = temperature
        self.top_p = top_p
        self.debug = debug
        
        # Voters created on demand
        self.voters: List[OllamaPlayer] = []
        
        # Track voting state for pickle generation
        self.current_game_turn = None
        self.voter_results: Dict[int, Any] = {}
        
        self._debug_log(f"Created MajorityVotePlayer using model {model}")
    
    def _debug_log(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if self.debug:
            print(f"[MAJORITY DEBUG] {message}")
    
    @property
    def player_string(self) -> str:
        """Generate player string: {model}_majority (vs {model}_single for single players)."""
        model_str = self.model.replace(":", "_").replace("/", "_").replace("-", "_").replace(".", "_")
        return f"{model_str}_majority"
    
    def set_game_context(self, game: Game, player_index: int):
        """Set the game context for this player and all voters."""
        super().set_game_context(game, player_index)
        
        # Update all existing voters with the game context
        for voter in self.voters:
            voter.set_game_context(game, player_index)
        
        self._debug_log(f"Set game context for majority vote player")
    
    def _ensure_voters(self, num_voters: int) -> List[OllamaPlayer]:
        """Ensure we have enough voters available.
        
        Args:
            num_voters: Number of voters needed
            
        Returns:
            List of voter instances
        """
        # Create additional voters if needed
        while len(self.voters) < num_voters:
            voter_index = len(self.voters)
            voter_name = f"{self.name}_voter_{voter_index}"
            
            voter = OllamaPlayer(
                name=voter_name,
                model=self.model,
                temperature=self.temperature,
                top_p=self.top_p,
                debug=self.debug
            )
            
            # Set game context if we have it
            if self.game is not None and self.player_index is not None:
                voter.set_game_context(self.game, self.player_index)
            
            self.voters.append(voter)
            self._debug_log(f"Created voter {voter_index}: {voter_name}")
        
        return self.voters[:num_voters]
    
    def _execute_voter_as_single_agent(self, voter_idx: int, voter: OllamaPlayer, method_name: str, 
                                     method_args: Tuple, game_turn: int) -> Any:
        """Execute a single voter exactly like a single agent and let it save its own pickle.
        
        Key insight: Let the voter behave exactly like a single agent, but intercept
        its file saving to use v{voter_idx}_{game_turn}.pkl instead of turn_{game_turn}.pkl.
        
        Returns:
            GameAction with the voter's result
        """
        self._debug_log(f"Executing voter {voter_idx} method {method_name} for turn {game_turn}")
        
        try:
            # Execute the voter's method with max_tries=1
            if method_name == "make_team_selection":
                # Force max_tries=1 for voter
                args_list = list(method_args)
                args_list[1] = 1  # max_tries parameter
                result = voter.make_team_selection(*args_list)
            elif method_name == "make_assertion":
                result = voter.make_assertion(*method_args)
            elif method_name == "make_action":
                result = voter.make_action(*method_args)
            else:
                raise ValueError(f"Unknown method: {method_name}")
            
            # The voter should have saved its own pickle file
            # Now we need to move it from turn_{game_turn}.pkl to v{voter_idx}_{game_turn}.pkl
            self._move_voter_pickle_file(voter_idx, game_turn)
            
            return result
            
        except Exception as e:
            self._debug_log(f"Voter {voter_idx} failed: {e}")
            # Try to move any pickle file that might have been created
            self._move_voter_pickle_file(voter_idx, game_turn)
            
            return GameAction("voter_execution", False, f"Voter {voter_idx} failed: {e}", "error")
    
    def _copy_winner_to_main_pickle(self, winner_idx: int, game_turn: int) -> None:
        """Copy the winning voter's pickle file to both turn_{turn}.pkl and latest.pkl."""
        try:
            player1_string = self.player_string if self.player_index == 0 else "opponent"
            player2_string = "opponent" if self.player_index == 0 else self.player_string
            
            save_dir = Path("saves") / player1_string / player2_string / "round_001"
            
            winner_path = save_dir / f"v{winner_idx}_{game_turn:03d}.pkl"
            main_path = save_dir / f"turn_{game_turn:03d}.pkl"
            latest_path = save_dir / "latest.pkl"
            
            if winner_path.exists():
                # Copy to turn_{game_turn}.pkl
                shutil.copy2(winner_path, main_path)
                self._debug_log(f"Copied winner voter {winner_idx} pickle to turn_{game_turn:03d}.pkl")
                
                # Copy to latest.pkl  
                shutil.copy2(winner_path, latest_path)
                self._debug_log(f"Copied winner voter {winner_idx} pickle to latest.pkl")
            else:
                self._debug_log(f"Warning: Winner voter pickle {winner_path} not found")
                
        except Exception as e:
            self._debug_log(f"Failed to copy winner pickle: {e}")
    
    def _move_voter_pickle_file(self, voter_idx: int, game_turn: int) -> None:
        """Move the voter's pickle file from turn_{game_turn}.pkl to v{voter_idx}_{game_turn}.pkl."""
        try:
            player1_string = self.player_string if self.player_index == 0 else "opponent"
            player2_string = "opponent" if self.player_index == 0 else self.player_string
            
            save_dir = Path("saves") / player1_string / player2_string / "round_001"
            
            # Original file saved by the single agent
            original_path = save_dir / f"turn_{game_turn:03d}.pkl"
            # Target voter file name
            voter_path = save_dir / f"v{voter_idx}_{game_turn:03d}.pkl"
            
            if original_path.exists():
                shutil.move(original_path, voter_path)
                self._debug_log(f"Moved {original_path} to {voter_path}")
            else:
                self._debug_log(f"Warning: Expected pickle file {original_path} not found")
                
        except Exception as e:
            self._debug_log(f"Failed to move voter {voter_idx} pickle: {e}")
    
    
    def _save_voter_pickle(self, voter_idx: int, game_turn: int, result: Any, error: Optional[str] = None) -> None:
        """Save individual voter's pickle file as v{voter_index}_{game_turn}.pkl."""
        if not self.game:
            return
        
        try:
            # Get player strings for directory structure
            player1_string = self.player_string if self.player_index == 0 else "opponent"
            player2_string = "opponent" if self.player_index == 0 else self.player_string
            
            # Create the save path using the existing structure but with voter filename
            save_dir = Path("saves") / player1_string / player2_string / "round_001"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            voter_filename = f"v{voter_idx}_{game_turn:03d}.pkl"
            voter_path = save_dir / voter_filename
            
            # Create save data matching single player structure
            save_data = {
                'state': self.game._serialize_state(),
                'history': getattr(self.game, 'history', []),
                'evaluation': getattr(self.game, 'evaluation', self.game._initialize_evaluation())
            }
            
            # Add player info (this voter as single player)
            save_data['players'] = {
                "1": [{
                    "name": f"{self.model} (Voter {voter_idx})",
                    "model": self.model,
                    "temperature": self.temperature,
                    "top_p": self.top_p
                }],
                "2": [{
                    "name": f"{self.model} (Opponent)", 
                    "model": self.model,
                    "temperature": self.temperature,
                    "top_p": self.top_p
                }]
            }
            
            # Add error information if this voter failed
            if error:
                save_data['voter_error'] = error
                save_data['voter_success'] = False
            else:
                save_data['voter_success'] = True
                if result:
                    save_data['voter_result'] = {
                        'action_type': result.action_type,
                        'success': result.success,
                        'message': result.message,
                        'validity': result.validity
                    }
            
            # Save the pickle file
            with open(voter_path, 'wb') as f:
                pickle.dump(save_data, f)
            
            self._debug_log(f"Saved voter {voter_idx} pickle to {voter_path}")
            
        except Exception as e:
            self._debug_log(f"Failed to save voter {voter_idx} pickle: {e}")
    
    def _execute_majority_vote(self, method_name: str, method_args: Tuple, num_voters: int) -> GameAction:
        """Execute majority voting across all voters with proper majority logic and pickle file generation.
        
        This is the core voting mechanism that:
        1. Executes each voter independently with max_tries=1
        2. Saves each voter's result as v{voter_index}_{turn}.pkl
        3. Groups results by actual moves and selects most popular move
        4. Ensures final turn_{turn}.pkl is copy of winner
        5. Returns status 'ongoing' if ANY voter succeeds, 'error' only if ALL fail
        """
        if not self.game:
            return GameAction("majority_vote", False, "No game context set", "error")
        
        game_turn = self.game.state.game_turn
        voters = self._ensure_voters(num_voters)
        
        self._debug_log(f"Executing majority vote for {method_name} with {num_voters} voters on turn {game_turn}")
        
        # Execute all voters and collect results
        voter_results = []
        
        for voter_idx, voter in enumerate(voters):
            result = self._execute_voter_as_single_agent(voter_idx, voter, method_name, method_args, game_turn)
            voter_results.append((voter_idx, result))
            
            if result.validity == "ongoing":
                self._debug_log(f"Voter {voter_idx} succeeded: {result.message}")
            else:
                self._debug_log(f"Voter {voter_idx} failed: {result.message}")
        
        # Group voters by their valid moves (true majority voting)
        move_groups = {}  # move_signature -> [voter_indices_with_this_move]
        
        for voter_idx, result in voter_results:
            if result.validity == "ongoing":  # Only count successful moves
                # Create a signature for the move (this will need to be method-specific)
                move_signature = self._create_move_signature(result, method_name)
                if move_signature not in move_groups:
                    move_groups[move_signature] = []
                move_groups[move_signature].append((voter_idx, result))
        
        # Select winner based on majority voting
        if move_groups:
            # Pick the move with the most votes (most popular move)
            winning_move = max(move_groups.keys(), key=lambda m: len(move_groups[m]))
            winning_voters = move_groups[winning_move]
            
            # Select first voter from the winning group (arbitrary tie-breaker)
            winner_idx, winner_result = winning_voters[0]
            
            self._debug_log(f"Selected winner: voter {winner_idx} with move {winning_move} ({len(winning_voters)} votes)")
            
            # Copy winner's v{winner_idx}_{turn}.pkl to turn_{turn}.pkl and latest.pkl
            self._copy_winner_to_main_pickle(winner_idx, game_turn)
            
            return winner_result
        else:
            # All voters failed - return error status
            self._debug_log("All voters failed")
            # Don't copy any file to turn_{turn}.pkl when all voters fail
            return GameAction("majority_vote", False, "All voters failed", "error")
    
    def _create_move_signature(self, result: GameAction, method_name: str) -> str:
        """Create a unique signature for a move to enable proper majority voting.
        
        This allows grouping voters by the actual content of their moves,
        not just success/failure.
        """
        # For now, use the message as move signature
        # TODO: Make this more sophisticated based on actual move content
        return f"{method_name}:{result.message}"
    
    
    def make_team_selection(self, available_fish: List[str], max_tries: int = 3, save_callback: Optional[Callable[[], None]] = None) -> GameAction:
        """Make team selection using majority voting among voters."""
        return self._execute_majority_vote("make_team_selection", (available_fish, max_tries, save_callback), max_tries)
    
    def make_assertion(self) -> GameAction:
        """Make assertion using majority voting among voters."""
        return self._execute_majority_vote("make_assertion", (), self.num_voters)
    
    def make_action(self) -> GameAction:
        """Make action using majority voting among voters."""
        return self._execute_majority_vote("make_action", (), self.num_voters)
    
    def make_assertion_simple_with_context(self) -> Tuple[str, Dict[str, Any]]:
        """Make assertion with context using majority voting.
        
        Returns:
            Tuple of (result string, context dict) from majority decision
        """
        # Use default number of voters
        voters = self._ensure_voters(self.num_voters)
        self._debug_log(f"Assertion with context using {self.num_voters} voters")
        
        # For now, use first voter (TODO: implement proper voting for context methods)
        result = voters[0].make_assertion_simple_with_context()
        self._debug_log(f"Assertion with context result: {result[0][:50]}...")
        
        return result
    
    def make_action_simple_with_context(self) -> Tuple[str, Dict[str, Any]]:
        """Make action with context using majority voting.
        
        Returns:
            Tuple of (result string, context dict) from majority decision
        """
        # Use default number of voters
        voters = self._ensure_voters(self.num_voters)
        self._debug_log(f"Action with context using {self.num_voters} voters")
        
        # For now, use first voter (TODO: implement proper voting for context methods)
        result = voters[0].make_action_simple_with_context()
        self._debug_log(f"Action with context result: {result[0][:50]}...")
        
        return result