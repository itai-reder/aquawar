#!/usr/bin/env python3
"""
Aquawar Persistent Game CLI

A command-line interface for playing Aquawar with save/load functionality.

Usage Examples:

# Initialize a new game
python -m aquawar_game.cli --game-id mygame --init

# View current prompt  
python -m aquawar_game.cli --game-id mygame --view-prompt

# Select team (Player 1)
python -m aquawar_game.cli --game-id mygame --input-selection "[0,3,7,11]"

# Select team with Mimic Fish
python -m aquawar_game.cli --game-id mygame --input-selection "[0,3,7,11]" --mimic-choice "Archerfish"

# Make assertion
python -m aquawar_game.cli --game-id mygame --input-assertion "ASSERT 2 Sea Wolf"

# Skip assertion
python -m aquawar_game.cli --game-id mygame --input-assertion "SKIP"

# Take action
python -m aquawar_game.cli --game-id mygame --input-action "ACT 1 NORMAL 2"

# List available saves
python -m aquawar_game.cli --game-id mygame --list-saves

# Load specific turn
python -m aquawar_game.cli --game-id mygame --load-turn 5
"""

from aquawar_game.persistent_game import main

if __name__ == "__main__":
    main()