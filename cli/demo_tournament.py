
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
from aquawar.ai.ollama_player import OllamaGameManager

if __name__ == "__main__":
    results = []
    for m1 in MODELS:
        for m2 in MODELS:
            if m1 == m2:
                continue
            print(f"\n=== {m1} (P1) vs {m2} (P2) ===")
            gm = OllamaGameManager(save_dir="demo_tournament_saves", model=m1, debug=False, max_tries=3)
            result = run_single_game(
                gm,
                player1_name=m1,
                player2_name=m2,
                max_turns=200,
                player1_model=m1,
                player2_model=m2,
                verbose=True,
                rounds=1
            )
            results.append({"player1": m1, "player2": m2, "result": result})
            print(f"Result: {result}\n")