"""
OllamaVoter and MajorityPlayer classes for Aquawar majority voting logic.

- OllamaVoter: Generates a move using the same logic as OllamaPlayer, but only one attempt per move, and saves result as v{i}_###.pkl.
- MajorityPlayer: Aggregates moves from multiple voters and selects the majority move.
"""


from .ollama_player import OllamaPlayer
from ..persistent import PersistentGameManager
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
    def __init__(self, majority_player, voter_index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.majority_player = majority_player
        self.voter_index = voter_index
        self.ends_turn = False  # Voters never increment game turn
        self.max_tries = 1
        self.pickle_prefix = f"v{self.voter_index}"

    @property
    def player_name(self):
        return f"{self.model} (Voter {self.voter_index + 1})"

    @property
    def player_string(self):
        """Generate player string for directory naming."""
        return self.majority_player.player_string

    @property
    def opponent(self):
        return self._other_player

    def save_pseudo_game_state(self):
        """Save the voter game state to a pickle file."""
        self._debug_log(f"Saving voter {self.voter_index} game state at turn {self.game.state.game_turn}")
        if self.player_index == 0:
            player1 = self
            player2 = self._other_player
        else:
            player1 = self._other_player
            player2 = self
        player1_string = player1.player_string
        player2_string = player2.player_string
        round_num = self.game.state.round_no
        players_info = self.game_manager._get_players_info(player1, player2)
        self.game_manager.persistent_manager.save_game_state(self.game, player1_string, player2_string, round_num, players_info, self.pickle_prefix)

    def set_pseudo_game(self, game, game_manager):
        pseudo_game = deepcopy(game)
        self.set_game_context(pseudo_game, self.player_index)

        pseudo_game_manager = deepcopy(game_manager)
        pseudo_game_manager._set_turn_prefix(self.pickle_prefix)
        self.set_game_manager(pseudo_game_manager, self._other_player)

    def get_pseudo_game(self):
        return self.game

    def get_player_info(self) -> Dict[str, Any]:
        """Get player information for saving."""
        return {
            "name": self.player_name,
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tries": self.max_tries
        }

    def set_index(self, voter_index):
        self.voter_index = voter_index

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
        pass

    def make_action_simple_with_context(self):
        """
        Run the majority voting logic for action phase and return (result, context).
        Context can include details of the vote for debugging.
        """
        pass
    
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
        self.pickle_prefix = "turn"
        # Create voter agents
        self.voters = [OllamaVoter(self, i, name=f"{name} Voter {i+1}", model=model, temperature=temperature, top_p=top_p, debug=debug) for i in range(self.max_tries)]
        for voter in self.voters:
            voter.ends_turn = False  # Ensure voters never increment the turn
        # Pseudo-player for making majority moves
        self.pseudo_player= OllamaPlayer(name=f"{name} (Majority {self.max_tries})", model=model, temperature=temperature, top_p=top_p, debug=debug)
        # Optionally accept additional kwargs for compatibility
        for k, v in kwargs.items():
            setattr(self, k, v)

    def set_game_manager(self, game_manager, other_player=None):
        self._game_manager = game_manager
        self._other_player = other_player
        for voter in self.voters:
            voter.set_game_manager(game_manager, other_player)
        self.pseudo_player.set_game_manager(game_manager, other_player)

    @property
    def player_name(self):
        return f"{self.model} (Majority {self.max_tries})"

    @property
    def opponent(self):
        """Get the opponent player reference."""
        return self._other_player

    @property
    def player_string(self) -> str:
        # Use a unique string for directory naming
        return f"{self.model.replace(' ', '_').lower()}_M{self.max_tries}"

    def get_player_info(self) -> Dict[str, Any]:
        """Get player information for saving."""
        return {
            "name": self.player_name,
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
        self.pseudo_player.set_game_context(game, player_index)

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

    def update_game_from_voter_pseudo_game(self, voter):
        self.set_game_context(voter.get_pseudo_game(), self.player_index)
        self.opponent.set_game_context(voter.get_pseudo_game(), 1 - self.player_index)

    def pick_majority_move(self, moves):
        if not moves:
            raise ValueError("No moves provided to pick_majority_move.")
        move_counts = {}
        for move in moves.values():
            if move is not None:
                move_counts[move] = move_counts.get(move, 0) + 1
        if not move_counts:
            raise ValueError("No valid moves found in pick_majority_move.")
        # Find the most popular move
        popular_move = max(move_counts, key=move_counts.get)
        self._debug_log(f"Majority move is '{popular_move}' with {move_counts[popular_move]} votes.")
        # Find the first voter index who made this move
        for voter_index, move in moves.items():
            if move == popular_move:
                return (voter_index, popular_move)
        raise ValueError("Majority move not found among voters, this should not happen.")

    def make_team_selection(self, available_fish, max_tries, save_callback) -> GameAction:
        """Make a team selection from the available fish.
        Run all voters, collect their selections, and pick the majority selection."""
        actions = {}
        messages = {}
        for i, voter in enumerate(self.voters):
            # voter.set_game_context(self.game, self.player_index)
            voter.set_pseudo_game(self.game, self._game_manager)
            def save_callback():
                self._debug_log(f"Saving voter {voter.voter_index} game state at turn {voter.game.state.game_turn}")
                return self._save_callback(voter.game, voter.player_string, self.opponent.player_string, voter.game.state.game_turn, self.get_player_info(), voter.pickle_prefix)

            voter.set_index(i)
            # One try, no callback
            action = voter.make_team_selection(available_fish, 1, save_callback)
            if action.success:
                actions[i] = action
                messages[i] = action.message
            # Save voter pseudo-game state
            voter.save_pseudo_game_state()
        # Pick the majority selection
        majority_selection = self.pick_majority_move(messages)
        majority_voter, majority_message = majority_selection
        self._debug_log(f"Majority selection made: {majority_message}")
        self._debug_log(f"Using voter {majority_voter} raw response")
        preset_response = actions[majority_voter].raw_response
        return self.pseudo_player.make_team_selection(available_fish, 1, save_callback, preset_response)
    


    def make_assertion_simple_with_context(self):
        assertions, contexts, responses = {}, {}, {}
        for i, voter in enumerate(self.voters):
            # voter.set_game_context(self.game, self.player_index)
            voter.set_pseudo_game(self.game, self._game_manager)
            voter.set_index(i)
            assertion, context, response = voter.make_assertion_simple_with_context()
            assertions[i] = assertion
            contexts[i] = context
            responses[i] = response

            voter.save_pseudo_game_state()
        majority_assertion = self.pick_majority_move(assertions)
        majority_voter, majority_message = majority_assertion
        self._debug_log(f"Majority assertion made: {majority_message}")
        self._debug_log(f"Using voter {majority_voter} raw response")
        preset_response = responses[majority_voter]
        return self.pseudo_player.make_assertion_simple_with_context(preset_response)

    def make_action_simple_with_context(self):
        actions, contexts, responses = {}, {}, {}
        for i, voter in enumerate(self.voters):
            # voter.set_game_context(self.game, self.player_index)
            voter.set_pseudo_game(self.game, self._game_manager)
            voter.set_index(i)
            action, context, response = voter.make_action_simple_with_context()
            actions[i] = action
            contexts[i] = context
            responses[i] = response

            voter.save_pseudo_game_state()
        majority_action = self.pick_majority_move(actions)
        majority_voter, majority_message = majority_action
        self._debug_log(f"Majority action made: {majority_message}")
        self._debug_log(f"Using voter {majority_voter} raw response")
        preset_response = responses[majority_voter]
        return self.pseudo_player.make_action_simple_with_context(preset_response)