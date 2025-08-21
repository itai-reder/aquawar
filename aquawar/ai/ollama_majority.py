"""
OllamaVoter and MajorityPlayer classes for Aquawar majority voting logic.

- OllamaVoter: Generates a move using the same logic as OllamaPlayer, but only one attempt per move, and saves result as v{i}_###.pkl.
- MajorityPlayer: Aggregates moves from multiple voters and selects the majority move.
"""


from .ollama_player import OllamaPlayer
from pathlib import Path

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

    def make_voter_move(self, phase: str, messages=None, save_dir=None, round_num=1, additional_data=None):
        """
        Make a single move (no retries), save as v{i}_###.pkl and latest.pkl.
        Args:
            phase: 'assertion' or 'action'
            messages: Optional messages for LLM
            save_dir: Directory to save pickle files
            round_num: Current round number
            additional_data: Optional dict for players_info, etc.
        Returns:
            (history_entry, parsed_move_result, context)
        """
        history_entry, result, context = self.make_move(phase, messages)

        # Save as v{i}_###.pkl and latest.pkl, using same players_info logic as OllamaPlayer
        voter_prefix = f"v{self.voter_index}"
        # For voters, game_turn is the next turn (since ends_turn is False, increment_game_turn is not called)
        game_turn = self.game.state.game_turn + 1
        if hasattr(self, '_other_player'):
            player1_string = self.player_string
            player2_string = self._other_player.player_string
        else:
            player1_string = self.player_string
            player2_string = self.player_string
        if additional_data and 'players_info' in additional_data:
            players_info = additional_data['players_info']
        else:
            players_info = {
                "1": [{"name": f"{self.model} (Voter)", "model": self.model, "temperature": self.temperature, "top_p": self.top_p}],
                "2": [{"name": f"{self.model} (Voter)", "model": self.model, "temperature": self.temperature, "top_p": self.top_p}]
            }
        game_dir = Path(save_dir) / player1_string / player2_string / f"round_{round_num:03d}"
        game_dir.mkdir(parents=True, exist_ok=True)
        save_path = game_dir / f"{voter_prefix}_{game_turn:03d}.pkl"
        latest_path = game_dir / "latest.pkl"
        # Use the same save method as the main game (if available)
        if hasattr(self.game, 'save_game'):
            self.game.save_game(str(save_path), players_info)
            self.game.save_game(str(latest_path), players_info)
        else:
            import pickle
            with open(save_path, "wb") as f:
                pickle.dump(self.game, f)
            with open(latest_path, "wb") as f:
                pickle.dump(self.game, f)
        return history_entry, result, context

# MajorityPlayer stub (to be implemented)
import pickle
from collections import Counter

class MajorityPlayer:
    """
    Aggregates moves from multiple OllamaVoters, selects the majority move, and saves as turn_###.pkl.
    """
    def __init__(self, player_index, player1_string, player2_string, round_num, save_dir, debug=False):
        self.player_index = player_index
        self.player1_string = player1_string
        self.player2_string = player2_string
        self.round_num = round_num
        self.save_dir = save_dir
        self.debug = debug

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
