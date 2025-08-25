# MODELS = [
#     "qwq:32b",
#     "gpt-oss:20b", 
#     "qwen3:14b",
#     "mistral-nemo:12b",
#     "llama3.1:8b"
# ]
MODELS = [
    "llama3.1:8b",
    "mistral-nemo:12b",
    "qwen3:14b",
    "gpt-oss:20b", 
]

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.ai_battle import run_single_game
from aquawar.ai.ollama_player import OllamaGameManager, OllamaPlayer
from aquawar.ai.ollama_majority import MajorityPlayer
import argparse

def create_player(name: str, model: str, player_type: str, opponent_type: str, debug: bool = False,
                  port: int = 11434):
    """Create a player based on type (single, majority_3, majority_5)."""
    host = f"http://localhost:{port}"
    if player_type == "single":
        max_tries = 3
        if opponent_type.startswith("majority"):
            # If opponent is majority, use the same max_tries
            max_tries = int(opponent_type.split("_")[1])
        return OllamaPlayer(name, model=model, debug=debug, max_tries=max_tries, host=host)
    elif player_type == "majority_3":
        return MajorityPlayer(name, model=model, debug=debug, max_tries=3, host=host)
    elif player_type == "majority_5":
        return MajorityPlayer(name, model=model, debug=debug, max_tries=5, host=host)
    else:
        raise ValueError(f"Unknown player type: {player_type}")

def run_battle_configuration(model1: str, model2: str, config1: str, config2: str, 
                           port1: int, port2: int, rounds: int, debug: bool = False):
    """Run a specific battle configuration between two models."""
    config_name = f"{config1}_vs_{config2}"
    player1_name = f"{model1}_{config1}"
    player2_name = f"{model2}_{config2}"
    
    print(f"\n=== {player1_name} vs {player2_name} ===")
    
    # Create players
    player1 = create_player(player1_name, model1, config1, config2, debug, port1)
    player2 = create_player(player2_name, model2, config2, config1, debug, port2)

    # Create game manager
    gm = OllamaGameManager(save_dir="tourney_saves", model=model1, debug=debug, max_tries=3)
    
    result = run_single_game(
        gm,
        player1,
        player2,
        max_turns=200,
        verbose=True,
        rounds=rounds
    )
    
    return {
        "player1": player1_name,
        "player2": player2_name,
        "config1": config1,
        "config2": config2,
        "model1": model1,
        "model2": model2,
        "result": result
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a comprehensive demo tournament between models.")
    parser.add_argument("--port1", type=int, default=11434, help="Ollama server port for player 1")
    parser.add_argument("--port2", type=int, default=11434, help="Ollama server port for player 2")
    parser.add_argument("--rounds", type=int, default=1, help="Number of rounds to play")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    results = []
    
    # Battle configurations to run
    battle_configs = [
        ("single", "single"),      # Single vs Single
        ("single", "majority_3"),  # Single vs Majority of 3
        ("single", "majority_5"),  # Single vs Majority of 5  
        ("majority_3", "majority_5") # Majority of 3 vs Majority of 5
    ]
    
    print("🏆 Starting comprehensive tournament with all battle configurations...")
    print(f"🤖 Models: {', '.join(MODELS)}")
    print(f"⚔️ Battle types: {', '.join([f'{c1} vs {c2}' for c1, c2 in battle_configs])}")
    print(f"🎯 Rounds per battle: {args.rounds}")
    
    for config1, config2 in battle_configs:
        print(f"\n" + "="*80)
        print(f"🔥 BATTLE CONFIGURATION: {config1.upper()} vs {config2.upper()}")
        print("="*80)
        
        config_results = []
        
        for m1 in MODELS:
            for m2 in MODELS:
                if m1 == m2 and config1 == config2:
                    continue  # Skip same model battles
                    
                try:
                    result = run_battle_configuration(
                        m1, m2, config1, config2, 
                        args.port1, args.port2, args.rounds, args.debug
                    )
                    config_results.append(result)
                    results.append(result)
                    print(f"Result: {result['result']}\n")
                except Exception as e:
                    print(f"❌ Error in battle {m1}({config1}) vs {m2}({config2}): {e}\n")
        
        # # Print summary for this configuration
        # print(f"\n📊 SUMMARY for {config1.upper()} vs {config2.upper()}:")
        # successful_battles = [r for r in config_results if r['result'].get('success', False)]
        # print(f"✅ Successful battles: {len(successful_battles)}/{len(config_results)}")
        
        # if successful_battles:
        #     # Count wins by model
        #     model_wins = {}
        #     for battle in successful_battles:
        #         winner_idx = battle['result']['winner'] 
        #         winner_model = battle['model1'] if winner_idx == 0 else battle['model2']
        #         model_wins[winner_model] = model_wins.get(winner_model, 0) + 1
            
        #     print("🏆 Win counts by model:")
        #     for model, wins in sorted(model_wins.items(), key=lambda x: x[1], reverse=True):
        #         print(f"  {model}: {wins} wins")
    
    # Final overall summary
    print(f"\n" + "="*80)
    print("🏆 FINAL TOURNAMENT SUMMARY")
    print("="*80)
    print(f"📊 Total battles: {len(results)}")
    successful_battles = [r for r in results if r['result'].get('success', False)]
    print(f"✅ Successful battles: {len(successful_battles)}")
    print(f"❌ Failed battles: {len(results) - len(successful_battles)}")
    
    if successful_battles:
        # Overall model performance
        overall_wins = {}
        for battle in successful_battles:
            winner_idx = battle['result']['winner']
            winner_model = battle['model1'] if winner_idx == 0 else battle['model2']
            overall_wins[winner_model] = overall_wins.get(winner_model, 0) + 1
        
        print("\n🏆 Overall model performance:")
        for model, wins in sorted(overall_wins.items(), key=lambda x: x[1], reverse=True):
            print(f"  {model}: {wins} total wins")
    
    print("\n✅ Tournament completed!")