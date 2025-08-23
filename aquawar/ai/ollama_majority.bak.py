"""
OllamaVoter and MajorityPlayer classes for Aquawar majority voting logic.

- OllamaVoter: Generates a move using the same logic as OllamaPlayer, but only one attempt per move, and saves result as v{i}_###.pkl.
- MajorityPlayer: Aggregates moves from multiple voters and selects the majority move.
"""


from .ollama_player import OllamaPlayer
from pathlib import Path
from typing import List, Dict, Any

from copy import deepcopy

class OllamaVoter(OllamaPlayer):
    """
    OllamaVoter: Like OllamaPlayer, but:
    - Only one attempt per move (no retries)
    - Does NOT increment game turn (game.state.game_turn is unchanged)
    - Does NOT call end_game_turn or update main game history
    - Saves v{i}_###.pkl and latest.pkl after every attempt, using same players_info logic as OllamaPlayer
    """
    def __init__(self, voter_index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voter_index = voter_index
        self.ends_turn = False  # Voters never increment game turn
        self.max_tries = 1

    def set_pseudo_game(self, game):
        self.game = deepcopy(game)

    def get_pseudo_game(self):
        return self.game

    def get_player_info(self) -> Dict[str, Any]:
        """Get player information for saving."""
        return {
            "name": self.player_name(),
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tries": self.max_tries
        }

    def set_index(self, voter_index):
        self.voter_index = voter_index

    def make_voter_move(self, phase: str, messages=None, save_dir=None, round_num=1, additional_data=None):
        """
        Make a single move (no retries), save as v{i}_###.pkl and latest.pkl using OllamaPlayer.save_turn_pickle, always, even on error.
        Args:
            phase: 'assertion' or 'action'
            messages: Optional messages for LLM
            save_dir: Directory to save pickle files
            round_num: Current round number
            additional_data: Optional dict for players_info, etc.
        Returns:
            (history_entry, parsed_move_result, context)
        """
        history_entry = None
        result = None
        context = None
        error = None
        try:
            history_entry, result, context = self.make_move(phase, messages)
            # if self.debug:
            #     print(f"[Voter {self.voter_index}] make_move succeeded for phase '{phase}'")
        except Exception as e:
            error = e
            context = {
                "error_location": f"{phase}_execution",
                "error": str(e)
            }
            history_entry = {
                "player": self.player_index + 1 if self.player_index is not None else 1,
                "game_turn": self.game.state.game_turn if self.game and hasattr(self.game, 'state') else 0,
                "player_turn": getattr(self.game.state, 'player_turn', 0) if self.game and hasattr(self.game, 'state') else 0,
                "phase": phase,
                "attempt": 1,
                "input_messages": messages if messages is not None else [],
                "response": {},
                "tool_call": None,
                "action_type": None,
                "raw_parameters": {},
                "validated_parameters": {},
                "success": False,
                "result": None,
                "error": {
                    "exception": str(e),
                    "exception_type": type(e).__name__,
                    "error_location": f"{phase}_execution",
                    "category": "voter_error"
                },
                "damage_dealt": 0,
                "damage_taken": 0,
                "timestamp": __import__('time').time(),
                "valid": False,
                "move": None
            }
            if self.debug:
                print(f"[Voter {self.voter_index}] make_move ERROR in phase '{phase}': {type(e).__name__}: {e}")
        finally:
            # Use OllamaPlayer.save_turn_pickle to save as v{i}_NNN.pkl and latest.pkl, never advancing the game turn
            voter_prefix = f"v{self.voter_index}"
            # Use game_turn+1 for the filename, but do NOT increment the game state
            # Pass round_num and additional_data for correct directory and players_info
            self.save_turn_pickle(voter_prefix, additional_data)
            if self.debug:
                print(f"[Voter {self.voter_index}] Saved via save_turn_pickle with prefix '{voter_prefix}'")
        return history_entry, result, context

# MajorityPlayer stub (to be implemented)
import pickle
from collections import Counter


from .base_player import BasePlayer, GameAction

class MajorityPlayer(BasePlayer):
    def make_assertion_simple_with_context(self):
        """
        Run the majority voting logic for assertion phase and return (result, context).
        Context can include details of the vote for debugging.
        """
        # Use the same logic as make_assertion, but also return context
        turn = self.game.state.game_turn if self.game and hasattr(self.game, 'state') else 1
        voter_results = []
        for i, voter in enumerate(self.voters):
            voter.set_pseudo_game(self.game)
            voter.set_index(i)
            voter.ends_turn = False
            result = voter.make_voter_move(phase="assertion", save_dir=self._get_game_dir().parent.parent.parent, round_num=self.game.round_num)
            history_entry, parsed_move_result, context = result
            valid = history_entry.get('valid', False) if isinstance(history_entry, dict) else False
            move_message = history_entry.get('move') if isinstance(history_entry, dict) else None
            class DummyResult:
                def __init__(self, success, message):
                    self.success = success
                    self.message = message
            voter_results.append((i, DummyResult(valid, move_message), voter, result))
        valid_moves = [(i, r, v, res) for i, r, v, res in voter_results if r.success]
        if not valid_moves:
            msg = f"All {len(voter_results)} voters made invalid moves for phase 'assertion' at turn {turn}. Game terminated."
            if self.game and hasattr(self.game, '_update_evaluation_game_status'):
                self.game._update_evaluation_game_status("error")
            return GameAction("assertion", False, msg, "invalid action"), {"voter_results": voter_results}
        from collections import Counter
        move_list = [r.message for _, r, _, _ in valid_moves]
        counter = Counter(move_list)
        majority_move, count = counter.most_common(1)[0]
        for i, r, v, res in valid_moves:
            if r.message == majority_move:
                self._save_majority_turn(v.game, turn)
                self._advance_turn()
                return GameAction("assertion", True, f"Majority move: {majority_move}", "valid"), {"majority_move": majority_move, "voter_results": voter_results}
        i, r, v, res = valid_moves[0]
        self._save_majority_turn(v.game, turn)
        self._advance_turn()
        return GameAction("assertion", True, f"Majority move: {r.message}", "valid"), {"majority_move": r.message, "voter_results": voter_results}

    def make_action_simple_with_context(self):
        """
        Run the majority voting logic for action phase and return (result, context).
        Context can include details of the vote for debugging.
        """
        turn = self.game.state.game_turn if self.game and hasattr(self.game, 'state') else 1
        voter_results = []
        for i, voter in enumerate(self.voters):
            voter.set_pseudo_game(self.game)
            voter.set_index(i)
            voter.ends_turn = False
            result = voter.make_voter_move(phase="action", save_dir=self._get_game_dir().parent.parent.parent, round_num=self.game.round_num)
            history_entry, parsed_move_result, context = result
            valid = history_entry.get('valid', False) if isinstance(history_entry, dict) else False
            move_message = history_entry.get('move') if isinstance(history_entry, dict) else None
            class DummyResult:
                def __init__(self, success, message):
                    self.success = success
                    self.message = message
            voter_results.append((i, DummyResult(valid, move_message), voter, result))
        valid_moves = [(i, r, v, res) for i, r, v, res in voter_results if r.success]
        if not valid_moves:
            msg = f"All {len(voter_results)} voters made invalid moves for phase 'action' at turn {turn}. Game terminated."
            if self.game and hasattr(self.game, '_update_evaluation_game_status'):
                self.game._update_evaluation_game_status("error")
            return GameAction("action", False, msg, "invalid action"), {"voter_results": voter_results}
        from collections import Counter
        move_list = [r.message for _, r, _, _ in valid_moves]
        counter = Counter(move_list)
        majority_move, count = counter.most_common(1)[0]
        for i, r, v, res in valid_moves:
            if r.message == majority_move:
                self._save_majority_turn(v.game, turn)
                self._advance_turn()
                return GameAction("action", True, f"Majority move: {majority_move}", "valid"), {"majority_move": majority_move, "voter_results": voter_results}
        i, r, v, res = valid_moves[0]
        self._save_majority_turn(v.game, turn)
        self._advance_turn()
        return GameAction("action", True, f"Majority move: {r.message}", "valid"), {"majority_move": r.message, "voter_results": voter_results}
    """
    Aggregates moves from multiple OllamaVoters, selects the majority move, and saves as turn_###.pkl.
    Compatible with the AI manager and CLI.
    """
    # def __init__(self, name: str, model: str = "llama3.2:3b", temperature: float = 0.7, top_p: float = 0.9, debug: bool = False, max_tries: int = 3, **kwargs):
    def __init__(self, name: str, model: str = "llama3.2:3b", max_tries: int = 3, temperature: float = 0.7, top_p: float = 0.9, debug: bool = False, **kwargs):
        super().__init__(name)
        self.model = model
        self.max_tries = max_tries
        self.temperature = temperature
        self.top_p = top_p
        self.debug = debug
        self._game_manager = None
        self._other_player = None
        self.game = None
        self.player_index = None
        # Create voter agents
        self.voters = [OllamaVoter(i, name=f"{name} Voter {i+1}", model=model, temperature=temperature, top_p=top_p, debug=debug) for i in range(self.max_tries)]
        for voter in self.voters:
            voter.ends_turn = False  # Ensure voters never increment the turn
        # Optionally accept additional kwargs for compatibility
        for k, v in kwargs.items():
            setattr(self, k, v)

    def set_game_manager(self, game_manager, other_player=None):
        self._game_manager = game_manager
        self._other_player = other_player
        for voter in self.voters:
            voter.set_game_manager(game_manager, other_player)

    @property
    def player_name(self):
        return f"{self.model} (Majority)"

    @property
    def player_string(self) -> str:
        # Use a unique string for directory naming
        return f"majority_{self.name.replace(' ', '_').lower()}"

    def get_player_info(self) -> Dict[str, Any]:
        """Get player information for saving."""
        return {
            "name": self.player_name(),
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tries": self.max_tries
        }

    def set_game_context(self, game, player_index: int, round_num: int = 1):
        self.game = game
        self.player_index = player_index
        self.round_num = round_num
        for voter in self.voters:
            voter.set_game_context(game, player_index)


    def _get_game_dir(self):
        # Use the same directory structure as OllamaPlayer, using self.round_num
        if hasattr(self, '_other_player') and self._other_player:
            player1_string = self.player_string
            player2_string = self._other_player.player_string
        else:
            player1_string = self.player_string
            player2_string = self.player_string
        round_num = getattr(self, 'round_num', 1)
        save_dir = getattr(self, '_game_manager', None)
        if save_dir and hasattr(save_dir, 'save_dir'):
            save_dir = save_dir.save_dir
        else:
            save_dir = "saves"
        return Path(save_dir) / player1_string / player2_string / f"round_{round_num:03d}"

    def _get_voter_pickles(self, phase, turn):
        # Find all v{i}_###.pkl files for this turn
        import glob
        game_dir = self._get_game_dir()
        pattern = str(game_dir / f"v*_{turn:03d}.pkl")
        files = glob.glob(pattern)
        voters = []
        for f in files:
            stem = Path(f).stem
            if stem.startswith('v') and '_' in stem:
                idx = int(stem[1:].split('_')[0])
                voters.append((idx, f))
        return voters

    def _load_voter_moves(self, phase, turn):
        # Load all voter moves for a given turn and phase
        moves = []
        for idx, path in self._get_voter_pickles(phase, turn):
            with open(path, 'rb') as f:
                data = pickle.load(f)
            # Try to extract the move from the last history entry
            try:
                history = data['history'] if isinstance(data, dict) else getattr(data, 'history', [])
                if not history:
                    move = None
                    valid = False
                else:
                    entry = history[-1]
                    move = entry.get('move')
                    valid = entry.get('valid', False)
            except Exception:
                move = None
                valid = False
            moves.append((idx, move, valid, data, path))
        return moves

    def _select_majority_valid_move(self, moves):
        # Only consider valid moves
        valid_moves = [(idx, move, data, path) for idx, move, valid, data, path in moves if valid]
        if not valid_moves:
            return None, None, None, None
        from collections import Counter
        move_list = [move for _, move, _, _ in valid_moves]
        counter = Counter(move_list)
        majority_move, count = counter.most_common(1)[0]
        # Find the first voter with the majority move
        for idx, move, data, path in valid_moves:
            if move == majority_move:
                return idx, move, data, path
        return valid_moves[0]  # fallback

    def _save_majority_turn(self, chosen_data, turn):
        game_dir = self._get_game_dir()
        turn_path = game_dir / f"turn_{turn:03d}.pkl"
        latest_path = game_dir / "latest.pkl"
        with open(turn_path, 'wb') as f:
            pickle.dump(chosen_data, f)
        with open(latest_path, 'wb') as f:
            pickle.dump(chosen_data, f)

    def _advance_turn(self):
        if self.game and hasattr(self.game, 'increment_game_turn'):
            self.game.increment_game_turn()

    def _majority_phase(self, phase, *args, **kwargs):
        # Determine current turn
        turn = self.game.state.game_turn if self.game and hasattr(self.game, 'state') else 1
        voter_results = []
        for i, voter in enumerate(self.voters):
            voter.set_pseudo_game(self.game)
            voter.set_index(i)
            voter.ends_turn = False  # Ensure voters never increment the turn
            if phase == "select_team":
                available_fish = args[0] if len(args) > 0 else []
                result = voter.make_voter_move(phase="select_team", messages=available_fish, save_dir=self._get_game_dir().parent.parent.parent, round_num=self.round_num)
            elif phase == "assertion":
                result = voter.make_voter_move(phase="assertion", save_dir=self._get_game_dir().parent.parent.parent, round_num=self.round_num)
            elif phase == "action":
                result = voter.make_voter_move(phase="action", save_dir=self._get_game_dir().parent.parent.parent, round_num=self.round_num)
            else:
                raise ValueError(f"Unknown phase: {phase}")
            history_entry, parsed_move_result, context = result
            valid = history_entry.get('valid', False) if isinstance(history_entry, dict) else False
            move_message = history_entry.get('move') if isinstance(history_entry, dict) else None
            class DummyResult:
                def __init__(self, success, message):
                    self.success = success
                    self.message = message
            voter_results.append((i, DummyResult(valid, move_message), voter, result))
        # Only count successful votes
        valid_moves = [(i, r, v, res) for i, r, v, res in voter_results if r.success]
        if not valid_moves:
            msg = f"All {len(voter_results)} voters made invalid moves for phase '{phase}' at turn {turn}. Game terminated."
            if self.game and hasattr(self.game, '_update_evaluation_game_status'):
                self.game._update_evaluation_game_status("error")
            return GameAction(phase, False, msg, "invalid action")
        from collections import Counter
        move_list = [r.message for _, r, _, _ in valid_moves]
        counter = Counter(move_list)
        majority_move, count = counter.most_common(1)[0]
        for i, r, v, res in valid_moves:
            if r.message == majority_move:
                # Save this voter's state as turn_###.pkl and latest.pkl
                # Use the same logic as before
                # The voter's game state is in v.game, but we want to save the actual game object (as in OllamaVoter)
                # The third element of result is context, but the game object is v.game
                self._save_majority_turn(v.game, turn)
                self._advance_turn()
                return GameAction(phase, True, f"Majority move: {majority_move}", "valid")
        # Fallback (should not happen)
        i, r, v, res = valid_moves[0]
        self._save_majority_turn(v.game, turn)
        self._advance_turn()
        return GameAction(phase, True, f"Majority move: {r.message}", "valid")

    def make_team_selection(self, available_fish, max_tries=3, save_callback=None) -> GameAction:
        # Use the same logic as _majority_phase, but for team selection
        return self._majority_phase("select_team", available_fish)

    def make_assertion(self) -> GameAction:
        return self._majority_phase("assertion")

    def make_action(self) -> GameAction:
        return self._majority_phase("action")

    def _debug_log(self, msg):
        if self.debug:
            print(f"[MajorityPlayer DEBUG] {msg}")

    def get_voter_pickles(self, turn):
        """Return list of (voter_index, path) for all v{i}_###.pkl files for this turn."""
        import glob
        game_dir = Path(self.save_dir) / self.player1_string / self.player2_string / f"round_{self.round_num:03d}"
        pattern = str(game_dir / f"v*_%.3d.pkl" % turn)
        files = glob.glob(pattern)
        voters = []
        for f in files:
            # Extract voter index from filename
            stem = Path(f).stem
            if stem.startswith('v') and '_' in stem:
                idx = int(stem[1:].split('_')[0])
                voters.append((idx, f))
        self._debug_log(f"Found voter pickles: {voters}")
        return voters

    def load_voter_moves(self, turn):
        """Load all voter moves for a given turn. Returns list of (voter_index, move, full_data)."""
        moves = []
        for idx, path in self.get_voter_pickles(turn):
            with open(path, 'rb') as f:
                data = pickle.load(f)
            # Try to extract the move from the last history entry
            try:
                move = data['history'][-1]['move']
            except Exception:
                move = None
            moves.append((idx, move, data))
            self._debug_log(f"Voter {idx} move: {move}")
        return moves

    def select_majority_move(self, moves):
        """Return the move string with the most votes (arbitrary tie-break)."""
        move_list = [m for _, m, _ in moves if m is not None]
        if not move_list:
            self._debug_log("No valid moves found among voters!")
            return None
        counter = Counter(move_list)
        majority_move, count = counter.most_common(1)[0]
        self._debug_log(f"Majority move: {majority_move} (votes: {count})")
        return majority_move

    def save_majority_turn(self, chosen_data, turn):
        """Save the chosen voter's game state as turn_###.pkl and latest.pkl."""
        game_dir = Path(self.save_dir) / self.player1_string / self.player2_string / f"round_{self.round_num:03d}"
        turn_path = game_dir / f"turn_{turn:03d}.pkl"
        latest_path = game_dir / "latest.pkl"
        with open(turn_path, 'wb') as f:
            pickle.dump(chosen_data, f)
        with open(latest_path, 'wb') as f:
            pickle.dump(chosen_data, f)
        self._debug_log(f"Saved majority turn to {turn_path} and latest.pkl")

    def run_majority_vote(self, turn):
        """
        Loads all voter pickles for the given turn, selects the majority move, and saves as turn_###.pkl.
        Returns the chosen move and voter index.
        """
        moves = self.load_voter_moves(turn)
        if not moves:
            self._debug_log("No voter moves found!")
            return None, None
        majority_move = self.select_majority_move(moves)
        if majority_move is None:
            self._debug_log("No valid majority move!")
            return None, None
        # Find the first voter with the majority move
        for idx, move, data in moves:
            if move == majority_move:
                self.save_majority_turn(data, turn)
                return majority_move, idx
        self._debug_log("Majority move found but no matching voter data!")
        return None, None
