
MODELS = [
    "qwq:32b",
    "gpt-oss:20b", 
    "qwen3:14b",
    "mistral-nemo:12b",
    "llama3.1:8b"
]

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.ai_battle import run_single_game
from aquawar.ai.ollama_player import OllamaGameManager, OllamaPlayer
from aquawar.ai.ollama_majority import MajorityPlayer
import argparse

def run_battle_configuration(model1, model2, config_type, port1=11434, port2=11434, rounds=1):
    """Run a specific battle configuration between two models.
    
    Args:
        model1: Model name for player 1
        model2: Model name for player 2
        config_type: Type of battle configuration
        port1: Ollama server port for player 1
        port2: Ollama server port for player 2
        rounds: Number of rounds to play
    """
    print(f"\n=== {config_type}: {model1} vs {model2} ===")
    
    # Create players based on configuration type
    if config_type == "Single vs Majority(3)":
        player1 = OllamaPlayer(f"{model1}_single", model=model1, debug=False)
        player2 = MajorityPlayer(f"{model2}_M3", model=model2, debug=False, num_agents=3)
    elif config_type == "Single vs Majority(5)": 
        player1 = OllamaPlayer(f"{model1}_single", model=model1, debug=False)
        player2 = MajorityPlayer(f"{model2}_M5", model=model2, debug=False, num_agents=5)
    elif config_type == "Majority(3) vs Majority(5)":
        player1 = MajorityPlayer(f"{model1}_M3", model=model1, debug=False, num_agents=3)
        player2 = MajorityPlayer(f"{model2}_M5", model=model2, debug=False, num_agents=5)
    else:
        raise ValueError(f"Unknown configuration type: {config_type}")
    
    # Create game manager
    gm = OllamaGameManager(save_dir="demo_tournament_saves", model=model1, debug=False, max_tries=3)
    
    # Run the game
    result = run_single_game(
        gm,
        player1,
        player2, 
        max_turns=200,
        verbose=True,
        rounds=rounds
    )
    
    return {"player1": model1, "player2": model2, "config": config_type, "result": result}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a demo tournament between models with different configurations.")
    parser.add_argument("--port1", type=int, default=11434, help="Ollama server port for player 1")
    parser.add_argument("--port2", type=int, default=11434, help="Ollama server port for player 2")
    parser.add_argument("--rounds", type=int, default=1, help="Number of rounds to play")
    args = parser.parse_args()
    
    # Battle configurations to test
    configurations = [
        "Single vs Majority(3)",
        "Single vs Majority(5)", 
        "Majority(3) vs Majority(5)"
    ]
    
    results = []
    
    # Run battles for each configuration and model pair
    for config in configurations:
        print(f"\n{'='*60}")
        print(f"RUNNING CONFIGURATION: {config}")
        print(f"{'='*60}")
        
        for m1 in MODELS:
            for m2 in MODELS:
                if m1 == m2:
                    continue
                    
                try:
                    result = run_battle_configuration(
                        m1, m2, config, 
                        port1=args.port1, 
                        port2=args.port2, 
                        rounds=args.rounds
                    )
                    results.append(result)
                    print(f"Result: {result['result']}\n")
                except Exception as e:
                    print(f"❌ Error in {config} {m1} vs {m2}: {e}")
                    results.append({
                        "player1": m1, 
                        "player2": m2, 
                        "config": config, 
                        "result": {"success": False, "error": str(e)}
                    })
    
    # Print summary
    print(f"\n{'='*60}")
    print("TOURNAMENT SUMMARY")
    print(f"{'='*60}")
    
    for config in configurations:
        config_results = [r for r in results if r["config"] == config]
        successful = [r for r in config_results if r["result"].get("success", False)]
        
        print(f"\n{config}:")
        print(f"  Total battles: {len(config_results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(config_results) - len(successful)}")
        
        if successful:
            print("  Sample results:")
            for result in successful[:3]:  # Show first 3 successful results
                winner_idx = result["result"].get("winner")
                if winner_idx is not None:
                    winner = result["player1"] if winner_idx == 0 else result["player2"]
                    turns = result["result"].get("turns", "unknown")
                    print(f"    {result['player1']} vs {result['player2']}: Winner {winner} ({turns} turns)")