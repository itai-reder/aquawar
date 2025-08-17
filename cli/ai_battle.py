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
    
    try:
        from langchain_ollama import ChatOllama
        
        models_to_test = set([player1_model, player2_model])
        
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


def run_single_game(game_manager, player1_name: str, player2_name: str, 
                   max_turns: int, player1_model: str, player2_model: str, verbose: bool = False, rounds: Optional[int] = None) -> Dict[str, Any]:
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
        
    Returns:
        Dictionary with game results
    """
    if verbose:
        # players, max turns, rounds
        print(f"🎮 Starting game: {player1_name} vs {player2_name}")
        print(f"⏳ Max turns: {max_turns}")
        print(f"🔄 Rounds: {rounds if rounds is not None else 'All available'}")

    start_time = time.time()
    
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
                  num_games: int, max_turns: int, verbose: bool = False, quiet: bool = False) -> Dict[str, Any]:
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
            game_manager, player1_name, player2_name, max_turns, player1_model, player2_model, verbose, None  # Always None for tournament mode
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
    
    # Import game manager (after validation to give better error messages)
    try:
        # For now, import from utils until we complete the reorganization
        from utils.ollama_client import OllamaGameManager
    except ImportError:
        # Fallback to new location if reorganization is complete
        try:
            from aquawar.ai.ollama_player import OllamaGameManager
        except ImportError as e:
            print(f"❌ Could not import OllamaGameManager: {e}")
            print("Make sure the reorganization is complete or run from project root")
            return 1
    
    # Initialize game manager 
    game_manager = OllamaGameManager(save_dir=args.save_dir, model=player1_model, debug=args.debug, max_tries=args.max_tries)
    
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
                args.max_turns, player1_model, player2_model, args.verbose, args.rounds
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