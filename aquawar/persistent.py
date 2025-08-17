"""Persistent game manager for Aquawar.

Provides save/load functionality with turn-by-turn persistence and 
command-line interface for viewing prompts and inputting actions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from .game import Game, FISH_NAMES


class PersistentGameManager:
    """Manages persistent Aquawar games with save/load functionality."""
    
    def __init__(self, save_dir: str = "saves", debug: bool = False):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        self.debug = debug
    
    def get_next_game_id(self) -> str:
        """Find the next available game_{i} ID."""
        i = 1
        while (self.save_dir / f"game_{i}").exists():
            i += 1
        return f"game_{i}"
    
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
    
    def list_saves(self, player1_string: str, player2_string: str, round_num: int = 1) -> List[int]:
        """List all available turn saves for a game."""
        game_dir = self.get_game_dir(player1_string, player2_string, round_num)
        if not game_dir.exists():
            return []
            
        pattern = "turn_*.pkl"
        saves = []
        for save_file in game_dir.glob(pattern):
            try:
                turn_str = save_file.stem.split('_')[1]
                saves.append(int(turn_str))
            except (IndexError, ValueError):
                continue
        return sorted(saves)
    
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
    
    def get_current_prompt(self, game: Game, requesting_player: Optional[int] = None) -> str:
        """Get the appropriate prompt for the current game state."""
        current_player = game.state.turn_player
        
        # Check if a specific player is requesting and if it's their turn
        if requesting_player is not None and requesting_player != current_player:
            # Check if any player still needs team selection first
            for i, player in enumerate(game.state.players):
                if player.team is None:
                    if requesting_player != i:
                        return f"This isn't player {requesting_player + 1}'s turn. Player {i + 1} ({game.state.players[i].name}) needs to select their team."
                    break
            else:
                # All teams selected, check actual turn
                return f"This isn't player {requesting_player + 1}'s turn. It's player {current_player + 1}'s ({game.state.players[current_player].name}) turn."
        
        # Check if we need team selection first
        if game.state.players[current_player].team is None:
            prompt = game.prompt_for_selection(current_player)
            return f"PLAYER {current_player + 1} ({game.state.players[current_player].name}) TURN:\n\n{prompt}"
        
        # Check if any player still needs team selection
        for i, player in enumerate(game.state.players):
            if player.team is None:
                prompt = game.prompt_for_selection(i)
                return f"PLAYER {i + 1} ({player.name}) TURN:\n\n{prompt}"
        
        # Game is in progress - check phase
        if game.state.phase == "assertion":
            prompt = game.prompt_for_assertion(current_player)
            return f"PLAYER {current_player + 1} ({game.state.players[current_player].name}) TURN:\n\n{prompt}"
        else:  # action phase
            prompt = game.prompt_for_action(current_player)
            return f"PLAYER {current_player + 1} ({game.state.players[current_player].name}) TURN:\n\n{prompt}"
    
    def process_selection_input(self, game: Game, player_idx: int, selection_input: str) -> tuple[bool, str]:
        """Process team selection input."""
        try:
            # Get prompt before processing
            prompt = game.prompt_for_selection(player_idx)
            
            # Parse selection format like "[0, 3, 7, 11]"
            selection_indices = eval(selection_input.strip())
            if not isinstance(selection_indices, list) or len(selection_indices) != 4:
                # Track invalid response
                game.add_history_entry(player_idx, prompt, selection_input, "invalid response")
                return False, "Must select exactly 4 fish as a list"
            
            player = game.state.players[player_idx]
            fish_names = []
            for idx in selection_indices:
                if not isinstance(idx, int) or idx < 0 or idx >= len(player.roster):
                    # Track invalid argument
                    game.add_history_entry(player_idx, prompt, selection_input, "invalid argument")
                    return False, f"Invalid fish index: {idx}"
                fish_names.append(player.roster[idx])
            
            # Check for Mimic Fish
            mimic_choice = None
            if "Mimic Fish" in fish_names:
                # Track invalid response (missing mimic choice)
                game.add_history_entry(player_idx, prompt, selection_input, "invalid response")
                return False, "Please specify mimic choice separately using --mimic-choice flag"
            
            game.select_team(player_idx, fish_names, mimic_choice)
            
            # Track valid response in history
            game.add_history_entry(player_idx, prompt, selection_input, "valid")
            
            return True, f"Team selected for {player.name}: {fish_names}"
            
        except Exception as e:
            # Track invalid response for parsing errors
            prompt = game.prompt_for_selection(player_idx)
            game.add_history_entry(player_idx, prompt, selection_input, "invalid response")
            return False, f"Error parsing selection: {e}"
    
    def process_assertion_input(self, game: Game, assertion_input: str) -> tuple[bool, str]:
        """Process assertion phase input."""
        current_player = game.state.turn_player
        
        # Get prompt before processing
        prompt = game.prompt_for_assertion(current_player)
        
        if assertion_input.upper().strip() == "SKIP":
            result = game.skip_assertion(current_player)
            # Track valid response in history
            game.add_history_entry(current_player, prompt, assertion_input, "valid")
            return True, result
        
        try:
            parts = assertion_input.strip().split()
            if len(parts) < 3 or parts[0].upper() != "ASSERT":
                # Track invalid response
                game.add_history_entry(current_player, prompt, assertion_input, "invalid response")
                return False, "Format: ASSERT <enemy_index> <Fish Name> or SKIP"
            
            enemy_index = int(parts[1])
            fish_name = " ".join(parts[2:])
            
            result = game.perform_assertion(current_player, enemy_index, fish_name)
            # Track valid response in history
            game.add_history_entry(current_player, prompt, assertion_input, "valid")
            return True, result
            
        except ValueError as e:
            # Track invalid argument (likely bad enemy_index)
            game.add_history_entry(current_player, prompt, assertion_input, "invalid argument")
            return False, f"Error processing assertion: {e}"
        except Exception as e:
            # Track invalid action (game logic error)
            game.add_history_entry(current_player, prompt, assertion_input, "invalid action")
            return False, f"Error processing assertion: {e}"
    
    def process_action_input(self, game: Game, action_input: str) -> tuple[bool, str]:
        """Process action phase input."""
        current_player = game.state.turn_player
        
        # Get prompt before processing
        prompt = game.prompt_for_action(current_player)
        
        try:
            parts = action_input.strip().split()
            if len(parts) < 3 or parts[0].upper() != "ACT":
                # Track invalid response
                game.add_history_entry(current_player, prompt, action_input, "invalid response")
                return False, "Format: ACT <fish_index> NORMAL <target> or ACT <fish_index> ACTIVE [target]"
            
            fish_index = int(parts[1])
            action = parts[2].upper()
            target_index = int(parts[3]) if len(parts) > 3 else None
            
            result = game.perform_action(current_player, fish_index, action, target_index)
            # Track valid response in history
            game.add_history_entry(current_player, prompt, action_input, "valid")
            return True, result
            
        except ValueError as e:
            # Track invalid argument (likely bad fish_index or target_index)
            game.add_history_entry(current_player, prompt, action_input, "invalid argument")
            return False, f"Error processing action: {e}"
        except Exception as e:
            # Track invalid action (game logic error)
            game.add_history_entry(current_player, prompt, action_input, "invalid action")
            return False, f"Error processing action: {e}"


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(description="Aquawar Persistent Game Manager")
    
    # Game management
    parser.add_argument("--game-id", help="Game identifier (auto-generated if not provided)")
    parser.add_argument("--save-dir", help="Custom save directory name (e.g., 'demo1' -> saves/demo1)")
    parser.add_argument("--player", type=int, choices=[1, 2], help="Which player is making the request")
    
    # Actions
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--init", action="store_true", help="Initialize new game")
    action_group.add_argument("--view-prompt", action="store_true", help="View current turn prompt")
    action_group.add_argument("--input-selection", help="Input team selection (e.g., '[0,3,7,11]')")
    action_group.add_argument("--input-assertion", help="Input assertion (e.g., 'ASSERT 2 Archerfish' or 'SKIP')")
    action_group.add_argument("--input-action", help="Input action (e.g., 'ACT 1 NORMAL 2')")
    action_group.add_argument("--list-saves", action="store_true", help="List available saves")
    action_group.add_argument("--load-turn", type=int, help="Load specific turn")
    
    # Game initialization options
    parser.add_argument("--player1", default="Player 1", help="Name of player 1")
    parser.add_argument("--player2", default="Player 2", help="Name of player 2")
    parser.add_argument("--mimic-choice", help="Fish name for mimic to copy")
    
    return parser


def main():
    """Main entry point for persistent game manager."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Determine save directory and game ID
    if args.save_dir:
        save_dir = f"saves/{args.save_dir}"
        game_id = args.game_id if args.game_id else "game"
    else:
        save_dir = "saves"
        game_id = args.game_id
    
    manager = PersistentGameManager(save_dir)
    
    # Auto-generate game ID if needed
    if not game_id:
        game_id = manager.get_next_game_id()
    
    try:
        if args.init:
            # Initialize new game
            game = manager.initialize_new_game(game_id, (args.player1, args.player2))
            print(f"New game '{game_id}' initialized in {save_dir}")
            print(f"Players: {args.player1} vs {args.player2}")
            
        elif args.list_saves:
            # List available saves
            saves = manager.list_saves(game_id)
            if saves:
                print(f"Available saves for '{game_id}': {saves}")
            else:
                print(f"No saves found for '{game_id}'")
                
        elif args.load_turn is not None:
            # Load specific turn
            game = manager.load_game_state(game_id, args.load_turn)
            save_path = manager.save_game_state(game, game_id)
            print(f"Loaded turn {args.load_turn} as current state")
            
        else:
            # Load current game state
            game = manager.load_game_state(game_id)
            
            if args.view_prompt:
                # View current prompt
                requesting_player = args.player - 1 if args.player else None
                prompt = manager.get_current_prompt(game, requesting_player)
                print(prompt)
                
            elif args.input_selection:
                # Process team selection
                # Find which player needs selection
                player_idx = None
                for i, player in enumerate(game.state.players):
                    if player.team is None:
                        player_idx = i
                        break
                
                if player_idx is None:
                    print("Error: All players already have teams selected")
                    sys.exit(1)
                
                # Check if requesting player matches the player who needs selection
                if args.player and (args.player - 1) != player_idx:
                    print(f"Error: This isn't player {args.player}'s turn. Player {player_idx + 1} needs to select their team.")
                    sys.exit(1)
                
                # Handle mimic choice if needed
                selection_input = args.input_selection
                fish_names = eval(selection_input)
                player = game.state.players[player_idx]
                actual_names = [player.roster[i] for i in fish_names]
                
                # Get prompt for history tracking
                prompt = game.prompt_for_selection(player_idx)
                full_response = selection_input
                
                mimic_choice = None
                if "Mimic Fish" in actual_names:
                    if not args.mimic_choice:
                        print("Error: Mimic Fish selected but --mimic-choice not specified")
                        sys.exit(1)
                    mimic_choice = args.mimic_choice
                    full_response += f" --mimic-choice {mimic_choice}"
                
                game.select_team(player_idx, actual_names, mimic_choice)
                
                # Track in history
                game.add_history_entry(player_idx, prompt, full_response, "valid")
                
                save_path = manager.save_game_state(game, game_id)
                print(f"Team selected for {player.name}: {actual_names}")
                if mimic_choice:
                    print(f"Mimic Fish will copy: {mimic_choice}")
                print(f"Game saved to: {save_path}")
                
            elif args.input_assertion:
                # Check if it's the requesting player's turn
                current_player = game.state.turn_player
                if args.player and (args.player - 1) != current_player:
                    print(f"Error: This isn't player {args.player}'s turn. It's player {current_player + 1}'s turn.")
                    sys.exit(1)
                
                # Process assertion
                success, message = manager.process_assertion_input(game, args.input_assertion)
                print(message)
                if success:
                    save_path = manager.save_game_state(game, game_id)
                    print(f"Game saved to: {save_path}")
                else:
                    sys.exit(1)
                    
            elif args.input_action:
                # Check if it's the requesting player's turn
                current_player = game.state.turn_player
                if args.player and (args.player - 1) != current_player:
                    print(f"Error: This isn't player {args.player}'s turn. It's player {current_player + 1}'s turn.")
                    sys.exit(1)
                
                # Process action
                success, message = manager.process_action_input(game, args.input_action)
                print(message)
                if success:
                    save_path = manager.save_game_state(game, game_id)
                    print(f"Game saved to: {save_path}")
                    
                    # Check if round is over
                    winner = game.round_over()
                    if winner is not None:
                        print(f"Round finished! Winner: {game.state.players[winner].name}")
                else:
                    sys.exit(1)
                    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()