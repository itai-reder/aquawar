# Aquawar Persistent Game System - Usage Guide

The persistent game system allows you to play Aquawar with save/load functionality, enabling step-by-step gameplay with recovery at any point.

## Features

✅ **Turn-by-turn persistence** - Game state saved after every action
✅ **Historical saves** - Access any previous turn
✅ **Command-line interface** - Easy scriptable commands
✅ **Detailed prompts** - Full game rules and fish descriptions
✅ **Error recovery** - Load from any saved state

## Installation & Setup

```bash
cd /home/itai/git/aquawar
# No additional installation needed - uses existing codebase
```

## Basic Workflow

### 1. Initialize a New Game

```bash
python -m aquawar_game.persistent_game --game-id mygame --init --player1 "Alice" --player2 "Bob"
```

### 2. View Current Game State

```bash
python -m aquawar_game.persistent_game --game-id mygame --view-prompt
```

### 3. Select Teams (for each player)

```bash
# Player 1 selects team
python -m aquawar_game.persistent_game --game-id mygame --input-selection "[0,3,7,11]"

# Player 2 selects team  
python -m aquawar_game.persistent_game --game-id mygame --input-selection "[1,4,8,10]"

# If using Mimic Fish, specify what to copy
python -m aquawar_game.persistent_game --game-id mygame --input-selection "[0,3,7,11]" --mimic-choice "Archerfish"
```

### 4. Play Turns (Assertion + Action phases)

```bash
# View current turn prompt
python -m aquawar_game.persistent_game --game-id mygame --view-prompt

# Make assertion (or skip)
python -m aquawar_game.persistent_game --game-id mygame --input-assertion "ASSERT 2 Sea Wolf"
python -m aquawar_game.persistent_game --game-id mygame --input-assertion "SKIP"

# Take action
python -m aquawar_game.persistent_game --game-id mygame --input-action "ACT 1 NORMAL 2"
python -m aquawar_game.persistent_game --game-id mygame --input-action "ACT 0 ACTIVE 1"
```

### 5. Save Management

```bash
# List all available saves
python -m aquawar_game.persistent_game --game-id mygame --list-saves

# Load a specific turn
python -m aquawar_game.persistent_game --game-id mygame --load-turn 5
```

## File Structure

```
saves/
├── mygame_latest.pkl          # Most recent save
├── mygame_turn_000.pkl        # Turn 0 save
├── mygame_turn_001.pkl        # Turn 1 save
├── mygame_turn_002.pkl        # Turn 2 save
└── ...
```

## Example: Complete Game Session

```bash
# 1. Start new game
python -m aquawar_game.persistent_game --game-id demo --init

# 2. Check what we need to do
python -m aquawar_game.persistent_game --game-id demo --view-prompt
# Shows selection phase with fish roster

# 3. Player 1 selects team (indices 0,3,7,11 = Archerfish, Sunfish, Octopus, Mimic Fish)
python -m aquawar_game.persistent_game --game-id demo --input-selection "[0,3,7,11]" --mimic-choice "Electric Eel"

# 4. Player 2 selects team
python -m aquawar_game.persistent_game --game-id demo --input-selection "[1,4,8,10]"

# 5. Start playing turns
python -m aquawar_game.persistent_game --game-id demo --view-prompt
# Shows assertion phase

# 6. Player 1 makes assertion
python -m aquawar_game.persistent_game --game-id demo --input-assertion "ASSERT 2 Sea Wolf"

# 7. Player 1 takes action
python -m aquawar_game.persistent_game --game-id demo --input-action "ACT 0 NORMAL 1"

# 8. Continue alternating turns...
python -m aquawar_game.persistent_game --game-id demo --view-prompt
python -m aquawar_game.persistent_game --game-id demo --input-assertion "SKIP"
python -m aquawar_game.persistent_game --game-id demo --input-action "ACT 2 ACTIVE 0"

# 9. Check saves anytime
python -m aquawar_game.persistent_game --game-id demo --list-saves

# 10. Go back to previous turn if needed
python -m aquawar_game.persistent_game --game-id demo --load-turn 3
```

## Command Reference

| Command | Description |
|---------|-------------|
| `--init` | Initialize new game |
| `--view-prompt` | View current turn prompt |
| `--input-selection "[0,3,7,11]"` | Select team by fish indices |
| `--input-assertion "ASSERT 2 Fish Name"` | Make assertion |
| `--input-assertion "SKIP"` | Skip assertion |
| `--input-action "ACT fish_idx NORMAL target"` | Normal attack |
| `--input-action "ACT fish_idx ACTIVE [target]"` | Use active skill |
| `--list-saves` | List available saves |
| `--load-turn N` | Load specific turn |
| `--mimic-choice "Fish Name"` | Specify mimic target |

## Integration with AI/Scripting

This system is perfect for:
- **AI agents** - Each command returns structured output
- **Automated testing** - Replay scenarios from any save point
- **Game analysis** - Step through games turn by turn
- **Recovery** - Resume interrupted games
- **Debugging** - Reproduce specific game states

The persistent game system transforms Aquawar from a single-session game into a fully recoverable, scriptable experience!