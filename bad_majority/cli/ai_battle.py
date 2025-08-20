#!/usr/bin/env python3
"""Official AI vs AI battle script for Aquawar.

This is the production-ready replacement for demos/test_ollama_ai.py with enhanced
features including tournament mode, model comparison, and comprehensive reporting.
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to path for now (until proper package installation)
sys.path.insert(0, str(Path(__file__).parent.parent))

from aquawar.ai.ollama_player import OllamaGameManager, OllamaPlayer


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser for AI battle script."""
    parser = argparse.ArgumentParser(
        description="Aquawar AI vs AI Battle System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic AI vs AI game with default model
  python cli/ai_battle.py

  # Use specific model
  python cli/ai_battle.py --model llama3.2:1b

  # Different models for each player
  python cli/ai_battle.py --player1-model llama3.2:3b --player2-model gpt-oss:20b

  # Tournament mode (10 games)
  python cli/ai_battle.py --tournament 10

  # Majority vote mode with 5 voters
  python cli/ai_battle.py --majority-vote --num-voters 5

  # Majority vote tournament  
  python cli/ai_battle.py --majority-vote --num-voters 3 --tournament 5

  # Custom save directory
  python cli/ai_battle.py --save-dir tournament_results

  # Verbose logging
  python cli/ai_battle.py --verbose
        """
    )
    
    # Model selection
    parser.add_argument("--model", default="llama3.2:3b", 
                       help="Ollama model for both players (default: %(default)s)")
    parser.add_argument("--player1-model", 
                       help="Ollama model for player 1 (overrides --model)")
    parser.add_argument("--player2-model", 
                       help="Ollama model for player 2 (overrides --model)")
    
    # Game configuration
    parser.add_argument("--max-turns", type=int, default=200,
                       help="Maximum turns per game (default: %(default)s)")
    parser.add_argument("--max-tries", type=int, default=3,
                       help="Maximum retry attempts for failed moves (default: %(default)s)")
    parser.add_argument("--rounds", type=int, metavar="N",
                       help="Number of rounds to execute (default: run until first available round is completed)")
    
    # Tournament mode
    parser.add_argument("--tournament", type=int, metavar="N",
                       help="Run N games and collect statistics")
    
    # Output configuration
    parser.add_argument("--save-dir", default="saves",
                       help="Directory for saving games (default: %(default)s)")
    parser.add_argument("--game-id", default="ai_battle",
                       help="Base game ID (will be auto-indexed) (default: %(default)s)")
    
    # Logging and output
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--debug", action="store_true",
                       help="Enable detailed debug logging throughout game execution")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Minimize output (only final results)")
    
    # Player names
    parser.add_argument("--player1-name", default="AI Alpha",
                       help="Name for player 1 (default: %(default)s)")
    parser.add_argument("--player2-name", default="AI Beta",
                       help="Name for player 2 (default: %(default)s)")
    
    # Majority voting configuration
    parser.add_argument("--majority-vote", action="store_true",
                       help="Enable majority vote mode for both players")
    parser.add_argument("--player1-majority", action="store_true",
                       help="Enable majority vote mode for player 1 only")
    parser.add_argument("--player2-majority", action="store_true", 
                       help="Enable majority vote mode for player 2 only")
    parser.add_argument("--num-voters", type=int, default=3,
                       help="Number of voters for majority vote mode (3-9, default: %(default)s)")
    parser.add_argument("--player1-voters", type=int,
                       help="Number of voters for player 1 (overrides --num-voters)")
    parser.add_argument("--player2-voters", type=int,
                       help="Number of voters for player 2 (overrides --num-voters)")
    
    return parser


def validate_models(player1_model: str, player2_model: str, verbose: bool = False) -> bool:
    """Validate that Ollama models are available.
    
    Args:
        player1_model: Model name for player 1
        player2_model: Model name for player 2 
        verbose: Whether to print detailed validation info
        
    Returns:
        True if all models are available
    """
    if verbose:
        print("🔧 Validating Ollama models...")
    
    models_to_test = set([player1_model, player2_model])
    
    try:
        from langchain_ollama import ChatOllama
        
        for model in models_to_test:
            if verbose:
                print(f"  Testing {model}...")
            test_llm = ChatOllama(model=model, temperature=0)
            response = test_llm.invoke("Say 'Hello'")
            if verbose:
                print(f"  ✓ {model} accessible")
        
        if verbose:
            print("✓ All models validated successfully")
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install: pip install langchain-ollama langchain-core")
        return False
    except Exception as e:
        print(f"❌ Model validation failed: {e}")
        print("Please ensure Ollama is running and models are installed:")
        for model in models_to_test:
            print(f"  ollama pull {model}")
        return False


def validate_majority_vote_args(args) -> bool:
    """Validate majority vote arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        True if arguments are valid
    """
    # Check if any majority vote mode is enabled
    player1_majority = args.majority_vote or args.player1_majority
    player2_majority = args.majority_vote or args.player2_majority
    
    if not (player1_majority or player2_majority):
        return True  # No majority vote, nothing to validate
    
    # Determine voter counts for each player
    player1_voters = args.player1_voters or args.num_voters if player1_majority else 0
    player2_voters = args.player2_voters or args.num_voters if player2_majority else 0
    
    # Validate voter counts
    for player_num, voter_count in [("player1", player1_voters), ("player2", player2_voters)]:
        if voter_count > 0:
            if voter_count < 3 or voter_count > 9:
                print(f"❌ Number of voters for {player_num} must be between 3 and 9, got {voter_count}")
                return False
            
            if voter_count % 2 == 0:
                print(f"⚠️  Warning: Even number of voters for {player_num} ({voter_count}) may lead to ties")
                print("   Recommended to use odd numbers (3, 5, 7, 9) for cleaner majority decisions")
    
    return True


class MajorityVoteGameManager(OllamaGameManager):
    """Game manager that supports majority voting mode."""
    
    def __init__(self, save_dir: str = "saves", model: str = "llama3.2:3b", debug: bool = False, 
                 max_tries: int = 3, num_voters: int = 3):
        """Initialize majority vote game manager.
        
        Args:
            save_dir: Directory for saving games
            model: Ollama model to use for voters
            debug: Enable detailed debug logging
            max_tries: Maximum retry attempts for invalid moves
            num_voters: Number of voters for majority decisions
        """
        super().__init__(save_dir, model, debug, max_tries)
        self.num_voters = num_voters
        
    def _create_player(self, player_name: str, player_model: str, use_majority_vote: bool = False):
        """Create a player (either OllamaPlayer or MajorityVotePlayer).
        
        Args:
            player_name: Name for the player
            player_model: Model for the player (or voters)
            use_majority_vote: Whether to create a majority vote player
            
        Returns:
            Player instance (OllamaPlayer or MajorityVotePlayer)
        """
        if use_majority_vote:
            # Import here to avoid circular imports
            from aquawar.ai.majority_player import MajorityVotePlayer
            return MajorityVotePlayer(player_name, num_voters=self.num_voters, model=player_model, debug=self.debug)
        else:
            return OllamaPlayer(player_name, player_model, debug=self.debug)
            
    def run_single_round(self, player1_name: str, player2_name: str, 
                        player1_model: str, player2_model: str, round_num: int, 
                        max_turns: int = 200, use_majority_vote: bool = False) -> Dict[str, Any]:
        """Run a single round with optional majority voting.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            player1_model: Model for player 1
            player2_model: Model for player 2
            round_num: Round number
            max_turns: Maximum turns per game
            use_majority_vote: Whether to use majority voting
            
        Returns:
            Dictionary with game results
        """
        # Create players (majority vote or single)
        player1 = self._create_player(player1_name, player1_model, use_majority_vote)
        player2 = self._create_player(player2_name, player2_model, use_majority_vote)
        
        # Clear any existing round directory
        game_dir = self.persistent_manager.get_game_dir(player1.player_string, player2.player_string, round_num)
        if game_dir.exists():
            import shutil
            shutil.rmtree(game_dir)
        
        # Initialize new game
        game = self.persistent_manager.initialize_new_game(
            player1.player_string, 
            player2.player_string,
            (player1_name, player2_name),
            self.max_tries,
            round_num
        )
        
        # Set game context
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        
        # Run the game using existing logic
        return self._execute_game_loop(game, player1, player2, max_turns, round_num)

    def execute_multiple_rounds(self, player1_name: str, player2_name: str,
                               player1_model: str, player2_model: str,
                               max_turns: int = 200, rounds: Optional[int] = None,
                               use_majority_vote: bool = False, num_voters: int = 3) -> Dict[str, Any]:
        """Execute multiple rounds with optional majority voting.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            player1_model: Model for player 1
            player2_model: Model for player 2
            max_turns: Maximum turns per game
            rounds: Number of rounds to execute (None = find first available)
            use_majority_vote: Whether to use majority voting
            
        Returns:
            Dictionary with execution results
        """
        # Create temporary players to get player strings
        temp_player1 = self._create_player(player1_name, player1_model, use_majority_vote)
        temp_player2 = self._create_player(player2_name, player2_model, use_majority_vote)
        player1_string = temp_player1.player_string
        player2_string = temp_player2.player_string
        
        results = {
            "player1_string": player1_string,
            "player2_string": player2_string,
            "total_rounds_executed": 0,
            "rounds_completed": 0,
            "rounds_skipped": 0,
            "rounds_failed": 0,
            "round_results": [],
            "success": True,
            "error": None
        }
        
        if rounds is None:
            # Default behavior: execute rounds sequentially until finding completed one
            round_num = 1
            while True:
                print(f"\n🔍 Checking round {round_num:03d}...")
                status = self.check_round_status(player1_string, player2_string, round_num)
                
                if status["error"]:
                    print(f"❌ Error in {status['game_dir']}: {status['error']}")
                    results["error"] = status["error"]
                    results["success"] = False
                    break
                
                if not status["needs_execution"]:
                    print(f"✅ Round {round_num:03d} already completed ({status['status']}) - skipping")
                    print(f"📁 Path: {status['game_dir']}")
                    results["rounds_skipped"] += 1
                    results["round_results"].append({
                        "round": round_num,
                        "action": "skipped",
                        "status": status["status"],
                        "path": status["game_dir"]
                    })
                    round_num += 1
                    continue
                
                # Execute this round
                print(f"🎮 Executing round {round_num:03d}...")
                print(f"📁 Path: {status['game_dir']}")
                
                if status["exists"] and status["has_latest"] and status["status"] == "ongoing":
                    print(f"♻️ Resuming from existing save...")
                    result = self.resume_existing_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns, use_majority_vote)
                else:
                    print(f"🆕 Initializing new round...")
                    result = self.run_single_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns, use_majority_vote)
                
                results["total_rounds_executed"] += 1
                results["round_results"].append({
                    "round": round_num,
                    "action": "executed",
                    "result": result,
                    "path": status["game_dir"]
                })
                
                if result["success"]:
                    results["rounds_completed"] += 1
                    print(f"✅ Round {round_num:03d} completed successfully!")
                    break
                else:
                    results["rounds_failed"] += 1
                    print(f"❌ Round {round_num:03d} failed: {result.get('error', 'Unknown error')}")
                    
                    if result.get("critical_error"):
                        print("🚨 Critical error detected - stopping execution")
                        results["error"] = result.get("error", "Critical error")
                        results["success"] = False
                        break
                    
                round_num += 1
                
                if round_num > 1000:  # Safety break
                    print("🚨 Safety limit reached (1000 rounds)")
                    results["error"] = "Safety limit reached"
                    results["success"] = False
                    break
        else:
            # Execute specific number of rounds
            for round_num in range(1, rounds + 1):
                print(f"\n🔍 Checking round {round_num:03d}...")
                status = self.check_round_status(player1_string, player2_string, round_num)
                
                if status["error"]:
                    print(f"❌ Error in {status['game_dir']}: {status['error']}")
                    results["rounds_failed"] += 1
                    continue
                
                if not status["needs_execution"]:
                    print(f"✅ Round {round_num:03d} already completed ({status['status']}) - skipping")
                    results["rounds_skipped"] += 1
                    continue
                
                print(f"🎮 Executing round {round_num:03d}...")
                
                if status["exists"] and status["has_latest"] and status["status"] == "ongoing":
                    result = self.resume_existing_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns, use_majority_vote)
                else:
                    result = self.run_single_round(player1_name, player2_name, player1_model, player2_model, round_num, max_turns, use_majority_vote)
                
                results["total_rounds_executed"] += 1
                results["round_results"].append({
                    "round": round_num,
                    "action": "executed", 
                    "result": result,
                    "path": status["game_dir"]
                })
                
                if result["success"]:
                    results["rounds_completed"] += 1
                else:
                    results["rounds_failed"] += 1
        
        return results

    def resume_existing_round(self, player1_name: str, player2_name: str, 
                             player1_model: str, player2_model: str, round_num: int, 
                             max_turns: int = 200, use_majority_vote: bool = False) -> Dict[str, Any]:
        """Resume an existing round with optional majority voting.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            player1_model: Model for player 1
            player2_model: Model for player 2
            round_num: Round number
            max_turns: Maximum turns per game
            use_majority_vote: Whether to use majority voting
            
        Returns:
            Dictionary with game results
        """
        # Create players
        player1 = self._create_player(player1_name, player1_model, use_majority_vote)
        player2 = self._create_player(player2_name, player2_model, use_majority_vote)
        
        # Load existing game state
        game = self.persistent_manager.load_game_state(
            player1.player_string, player2.player_string, round_num
        )
        
        # Set game context
        player1.set_game_context(game, 0)
        player2.set_game_context(game, 1)
        
        # Resume the game using existing logic
        return self._execute_game_loop(game, player1, player2, max_turns, round_num)

    def run_ai_vs_ai_game(self, player1_name: str = "AI Player 1", player2_name: str = "AI Player 2",
                          max_turns: int = 100, player1_model: Optional[str] = None, 
                          player2_model: Optional[str] = None, rounds: Optional[int] = None,
                          use_majority_vote: bool = False, num_voters: int = 3) -> Dict[str, Any]:
        """Run AI vs AI game(s) with optional majority voting support.
        
        Args:
            player1_name: Name for player 1
            player2_name: Name for player 2
            max_turns: Maximum number of turns before forcing end
            player1_model: Model for player 1 (defaults to self.model)
            player2_model: Model for player 2 (defaults to self.model)
            rounds: Number of rounds to execute (None = find first available)
            use_majority_vote: Whether to use majority voting
            
        Returns:
            Dictionary with game results
        """
        # Use provided models or default to self.model
        if player1_model is None:
            player1_model = self.model
        if player2_model is None:
            player2_model = self.model
            
        # Use modified multiple rounds logic with majority vote support
        results = self.execute_multiple_rounds(
            player1_name, player2_name, player1_model, player2_model, max_turns, rounds, use_majority_vote, num_voters or self.num_voters
        )
        
        # For compatibility with existing CLI, adapt results format for single round mode
        if rounds is None and results["round_results"]:
            # Return the first executed round's result for single-round compatibility
            for round_result in results["round_results"]:
                if round_result["action"] == "executed":
                    single_result = round_result["result"]
                    # Add save_path for CLI compatibility
                    if "save_path" not in single_result:
                        single_result["save_path"] = round_result["path"]
                    return single_result
            
            # If no rounds were executed, return summary
            return {
                "success": results["success"],
                "error": results.get("error", "No rounds needed execution"),
                "rounds_skipped": results["rounds_skipped"],
                "save_path": f"{results['player1_string']}/{results['player2_string']}/"
            }
        
        # For multi-round mode, return full results
        return results


def run_single_game(game_manager, player1_name: str, player2_name: str, 
                   max_turns: int, player1_model: str, player2_model: str, verbose: bool = False, 
                   rounds: Optional[int] = None, use_majority_vote: bool = False) -> Dict[str, Any]:
    """Run a single AI vs AI game.
    
    Args:
        game_manager: OllamaGameManager instance
        player1_name: Name for player 1
        player2_name: Name for player 2
        max_turns: Maximum turns per game
        player1_model: Model for player 1
        player2_model: Model for player 2
        verbose: Whether to print detailed progress
        rounds: Number of rounds to execute (None = find first available)
        use_majority_vote: Whether to use majority voting
        
    Returns:
        Dictionary with game results
    """
    if verbose:
        # players, max turns, rounds
        print(f"🎮 Starting game: {player1_name} vs {player2_name}")
        print(f"⏳ Max turns: {max_turns}")
        print(f"🔄 Rounds: {rounds if rounds is not None else 'All available'}")

    start_time = time.time()
    
    # Use MajorityVoteGameManager method if it's available, otherwise fallback
    if hasattr(game_manager, 'run_ai_vs_ai_game') and hasattr(game_manager, 'num_voters'):
        # MajorityVoteGameManager
        result = game_manager.run_ai_vs_ai_game(
            player1_name=player1_name,
            player2_name=player2_name,
            max_turns=max_turns,
            player1_model=player1_model,
            player2_model=player2_model,
            rounds=rounds,
            use_majority_vote=use_majority_vote
        )
    else:
        # Regular OllamaGameManager
        result = game_manager.run_ai_vs_ai_game(
            player1_name=player1_name,
            player2_name=player2_name,
            max_turns=max_turns,
            player1_model=player1_model,
            player2_model=player2_model,
            rounds=rounds
        )
    
    end_time = time.time()
    result["duration"] = end_time - start_time
    
    return result


def run_tournament(game_manager, player1_name: str, player2_name: str, player1_model: str, player2_model: str,
                  num_games: int, max_turns: int, verbose: bool = False, quiet: bool = False, 
                  use_majority_vote: bool = False) -> Dict[str, Any]:
    """Run a tournament of multiple games.
    
    Args:
        game_manager: OllamaGameManager instance
        player1_name: Name for player 1
        player2_name: Name for player 2
        player1_model: Model for player 1
        player2_model: Model for player 2
        num_games: Number of games to play
        max_turns: Maximum turns per game
        verbose: Whether to print detailed progress
        quiet: Whether to minimize output
        
    Returns:
        Dictionary with tournament statistics
    """
    if not quiet:
        print(f"🏆 Starting tournament: {num_games} games")
        print(f"🤖 Players: {player1_name} vs {player2_name}")
    
    results = []
    player1_wins = 0
    player2_wins = 0
    total_turns = 0
    total_duration = 0.0
    errors = 0
    
    for game_num in range(1, num_games + 1):
        if not quiet:
            print(f"\n--- Game {game_num}/{num_games} ---")
        
        result = run_single_game(
            game_manager, player1_name, player2_name, max_turns, player1_model, player2_model, verbose, None, use_majority_vote  # Always None for tournament mode
        )
        
        results.append(result)
        total_duration += result.get("duration", 0)
        
        if result["success"]:
            winner = result["winner"]
            turns = result["turns"]
            total_turns += turns
            
            if winner == 0:  # Player 1 wins
                player1_wins += 1
                winner_name = player1_name
            else:  # Player 2 wins
                player2_wins += 1
                winner_name = player2_name
            
            if not quiet:
                print(f"🎉 Winner: {winner_name} ({turns} turns, {result['duration']:.1f}s)")
        else:
            errors += 1
            if not quiet:
                print(f"❌ Game failed: {result['error']}")
    
    # Calculate statistics
    completed_games = num_games - errors
    avg_turns = total_turns / completed_games if completed_games > 0 else 0
    avg_duration = total_duration / num_games
    
    tournament_stats = {
        "num_games": num_games,
        "completed_games": completed_games,
        "errors": errors,
        "player1_wins": player1_wins,
        "player2_wins": player2_wins,
        "player1_win_rate": player1_wins / completed_games if completed_games > 0 else 0,
        "player2_win_rate": player2_wins / completed_games if completed_games > 0 else 0,
        "avg_turns": avg_turns,
        "avg_duration": avg_duration,
        "total_duration": total_duration,
        "all_results": results
    }
    
    return tournament_stats


def print_tournament_summary(stats: Dict[str, Any], player1_name: str, player2_name: str, 
                           player1_model: str, player2_model: str):
    """Print tournament summary statistics.
    
    Args:
        stats: Tournament statistics dictionary
        player1_name: Name of player 1
        player2_name: Name of player 2
        player1_model: Model used for player 1
        player2_model: Model used for player 2
    """
    print("\n" + "=" * 60)
    print("🏆 TOURNAMENT RESULTS")
    print("=" * 60)
    print(f"📊 Games: {stats['completed_games']}/{stats['num_games']} completed")
    if stats['errors'] > 0:
        print(f"⚠️ Errors: {stats['errors']}")
    
    print(f"\n🤖 Player Performance:")
    print(f"  {player1_name} ({player1_model}): {stats['player1_wins']} wins ({stats['player1_win_rate']:.1%})")
    print(f"  {player2_name} ({player2_model}): {stats['player2_wins']} wins ({stats['player2_win_rate']:.1%})")
    
    if stats['player1_wins'] > stats['player2_wins']:
        winner = f"{player1_name} ({player1_model})"
    elif stats['player2_wins'] > stats['player1_wins']:
        winner = f"{player2_name} ({player2_model})"
    else:
        winner = "TIE"
    
    print(f"\n🎉 Overall Winner: {winner}")
    
    print(f"\n📈 Statistics:")
    print(f"  Average game length: {stats['avg_turns']:.1f} turns")
    print(f"  Average game duration: {stats['avg_duration']:.1f} seconds")
    print(f"  Total tournament time: {stats['total_duration']:.1f} seconds")


def main():
    """Main entry point for AI battle script."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Determine models for each player
    player1_model = args.player1_model or args.model
    player2_model = args.player2_model or args.model
    
    print("🐟 Aquawar AI vs AI Battle System")
    print("=" * 50)
    
    # Validate models
    if not validate_models(player1_model, player2_model, args.verbose):
        return 1
    
    # Validate majority vote arguments
    if not validate_majority_vote_args(args):
        return 1

    
    # Initialize game manager (with majority vote support if enabled)
    if args.majority_vote:
        if not args.quiet:
            print(f"🗳️  Majority vote mode enabled with {args.num_voters} voters")
        game_manager = MajorityVoteGameManager(
            save_dir=args.save_dir, 
            model=player1_model, 
            debug=args.debug, 
            max_tries=args.max_tries,
            num_voters=args.num_voters
        )
    else:
        game_manager = OllamaGameManager(
            save_dir=args.save_dir, 
            model=player1_model, 
            debug=args.debug, 
            max_tries=args.max_tries
        )
    
    try:
        if args.tournament:
            # Tournament mode
            if args.verbose:
                print(f"🏆 Running tournament: {args.tournament} games")
                print(f"🤖 Players: {args.player1_name} vs {args.player2_name}")
                print(f"🧠 Models: {player1_model} vs {player2_model}")
                print(f"🎯 Objective: Play until one player loses all fish")
                print("\n🚀 Starting tournament...")
            stats = run_tournament(
                game_manager, args.player1_name, args.player2_name, player1_model, player2_model,
                args.tournament, args.max_turns, args.verbose, args.quiet
            )
            
            if not args.quiet:
                print_tournament_summary(stats, args.player1_name, args.player2_name, 
                                       player1_model, player2_model)
            
            # Return non-zero if there were errors
            return 1 if stats['errors'] > 0 else 0
        else:
            # Single game mode
            if not args.quiet:
                print(f"🤖 Players: {args.player1_name} vs {args.player2_name}")
                print(f"🧠 Models: {player1_model} vs {player2_model}")
                print("🎯 Objective: Play until one player loses all fish")
                print("\n🚀 Starting game...")
            
            result = run_single_game(
                game_manager, args.player1_name, args.player2_name,
                args.max_turns, player1_model, player2_model, args.verbose, args.rounds,
                use_majority_vote=args.majority_vote
            )
            
            # Print results
            print("\n" + "=" * 50)
            print("🏆 GAME RESULTS")
            print("=" * 50)
            
            if result["success"]:
                winner_name = args.player1_name if result["winner"] == 0 else args.player2_name
                winner_model = player1_model if result["winner"] == 0 else player2_model
                
                print(f"🎉 Winner: {winner_name} ({winner_model})")
                print(f"📊 Total turns: {result['turns']}")
                print(f"⏱️ Duration: {result['duration']:.1f} seconds")
                print(f"💾 Game saved to: {result['save_path']}")
                
                if args.verbose:
                    print(f"📝 Full save directory: {Path(args.save_dir) / result['save_path']}")
                
                print("\n✅ Battle completed successfully!")
                return 0
            else:
                print(f"❌ Game failed: {result['error']}")
                print(f"📊 Turns completed: {result.get('turns', 0)}")
                print(f"⏱️ Duration: {result['duration']:.1f} seconds")
                if 'save_path' in result:
                    print(f"💾 Partial save at: {result['save_path']}")
                print("\n❌ Battle failed!")
                return 1
                
    except KeyboardInterrupt:
        print("\n⚠️ Battle interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())