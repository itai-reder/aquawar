# Copilot Instructions for Aquawar

## Project Overview
Aquawar is a turn-based strategy game for language-model agents (LLMs or humans). Players assemble squads of fish with unique abilities and take turns making assertions and attacks. The engine is designed for stateless LLM play: every prompt fully describes the visible state, so agents do not need memory of previous turns.

## Architecture & Key Components
- `aquawar/`: Core game logic (`fish.py`, `game.py`, `persistent.py`)
- `aquawar/ai/`: AI agent base classes and Ollama LLM integration
- `cli/ai_battle.py`: Main entry for AI vs AI matches and tournaments
- `utils/`: Scripts for debugging, examining, and analyzing save files
- `docs/`: Game rules, persistent game guide, and README

### Data Flow
- The engine advances game state and generates stateless prompts for agents
- AI agents (see `ollama_player.py`) receive prompts and return actions
- All actions, errors, and history are saved turn-by-turn in `saves/`

## Developer Workflows
- **Run AI vs AI matches:** `python cli/ai_battle.py [options]`
- **Run demo (human/AI):** `python -m aquawar_game.demo`
- **Persistent CLI game:** See `docs/PERSISTENT_GAME_GUIDE.md` for step-by-step commands
- **Run tests:** `pytest -q`
- **Debug saves:** Use `utils/examine_pkl.py` or `utils/detailed_pickle_exam.py`

## Conventions & Patterns
- All agent decisions are stateless; prompts fully describe the visible state
- Fish and skill logic is centralized in `aquawar/fish.py` and follows the rules in `docs/game_description.md`
- Game rules and round logic are in `aquawar/game.py`
- AI agents inherit from `base_player.py` and are managed by `OllamaGameManager`
- Save files are organized by model and game ID in `saves/`
- Error handling and persistence are strict: every turn is saved, errors are logged, and failed games are never marked as completed

## Integration & Dependencies
- Ollama LLMs via `langchain_ollama` (see `ollama_player.py`)
- No non-stdlib dependencies except for optional LLM/AI features
- All prompts and actions are deterministic for reproducibility

## Examples
- Run a 10-game tournament between two models:
  ```bash
  python cli/ai_battle.py --player1-model llama3.2:3b --player2-model gpt-oss:20b --tournament 10
  ```
- Debug a saved game:
  ```bash
  python utils/examine_pkl.py --dir saves/llama3.2_3b_single/llama3.1_8b_single/round_001 --files latest.pkl
  ```
- Step through a persistent game (see `docs/PERSISTENT_GAME_GUIDE.md` for full workflow)

## References
- Game rules: `docs/game_description.md`
- Persistent game: `docs/PERSISTENT_GAME_GUIDE.md`
- Core logic: `aquawar/game.py`, `aquawar/fish.py`, `aquawar/ai/ollama_player.py`

---
For new agents or features, follow the stateless prompt/response pattern and keep all game logic in the engine, not the agent.
