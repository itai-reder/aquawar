# Aquawar

Aquawar is a turn-based strategy game designed for language-model agents. Players secretly assemble a squad of four fish with unique abilities and take turns asserting identities and attacking. The engine provides stateless prompts that fully describe the visible game state at each decision point so an LLM can reason about its next move without remembering previous turns.

## Features
- Full implementation of the twelve-fish roster, including passives, active skills, and assertion mechanics.
- Round-based match controller enforcing best-of-three rules and turn limits.
- Deterministic prompts for assertions and actions, suitable for LLM play.
- Command-line demo (`aquawar_game.demo`) that lets a human play against themselves or script the game for debugging.

## Installation
The project has no external dependencies beyond the Python standard library. Use Python 3.11+.

Clone the repository and install in editable mode if desired:
```bash
pip install -e .
```

## Running the Demo
Play through the interactive demo:
```bash
python -m aquawar_game.demo
```
Follow the prompts to pick fish, make assertions, and perform actions as if you were an LLM agent.

## Running Tests
The repository includes a small pytest suite:
```bash
pytest -q
```

## Further Reading
For a comprehensive rule set and fish descriptions, see [game_description.md](game_description.md).

