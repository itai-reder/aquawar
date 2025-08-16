# Aquawar Repository Reorganization Plan

## Overview

Move from experimental `demos/` structure to production-ready package organization:
- Rename `core/` → `aquawar/` (main package)
- Extract AI logic from `utils/` → `aquawar/ai/`  
- Create `cli/` package for user-facing scripts
- Move deprecated files to `deprecated/` directory
- Preserve all working game logic and AI functionality

## Final File Structure and Logic Responsibilities

### Core Game Logic (Chronological Order)

#### `aquawar/__init__.py`
**Logic**: Package initialization, version info, main exports  
**Imports**: None (foundation module)

#### `aquawar/fish.py` 
**Logic**: Fish classes, abilities, combat mechanics, FISH_FACTORIES registry  
**Imports**: None (pure game mechanics)

#### `aquawar/game.py`
**Logic**: Core game engine, rules, state management, turn flow, win conditions  
**Imports**: `aquawar/fish.py` (for Fish classes and FISH_NAMES)

#### `aquawar/config.py`
**Logic**: Configuration dataclasses, JSON serialization, preset configs  
**Imports**: None (pure configuration management)

#### `aquawar/persistent.py` (renamed from `core/persistent_game.py`)
**Logic**: Save/load operations, CLI argument parsing, input validation  
**Imports**: `aquawar/game.py`, `aquawar/config.py`

### AI System

#### `aquawar/ai/__init__.py`
**Logic**: AI package initialization, common AI exports  
**Imports**: None

#### `aquawar/ai/base_player.py` (NEW)
**Logic**: Abstract AI player interface, GameAction dataclass, common utilities  
**Imports**: `aquawar/game.py` (for game context)

#### `aquawar/ai/ollama_player.py` (extracted from `utils/ollama_client.py`)
**Logic**: Ollama LLM integration, tool calling, retry logic, game management  
**Imports**: `aquawar/game.py`, `aquawar/persistent.py`, `aquawar/config.py`, `aquawar/ai/base_player.py`

### Command Line Interface

#### `cli/__init__.py`
**Logic**: CLI package initialization  
**Imports**: None

#### `cli/game_manager.py` (enhanced from `core/persistent_game.py` CLI)
**Logic**: Interactive game management, manual play, analysis tools  
**Imports**: `aquawar/persistent.py`, `aquawar/game.py`, `aquawar/config.py`

#### `cli/ai_battle.py` (production version of `demos/test_ollama_ai.py`)
**Logic**: AI vs AI orchestration, tournament mode, model validation, reporting  
**Imports**: `aquawar/ai/ollama_player.py`, `aquawar/config.py`, `aquawar/persistent.py`

## Files Being Moved to Deprecated

### Logic Preserved Elsewhere:
- **`demos/test_ollama_ai.py`** → Logic moved to `cli/ai_battle.py`
- **`demos/demo.py`** → Logic superseded by `cli/game_manager.py`
- **`demos/cli.py`** → Logic merged into `cli/game_manager.py`
- **`demos/demo_v1_2_0.py`** → Deprecated version, superseded
- **`demos/test_basic.py`** → Basic testing superseded by AI battle system
- **`demos/test_persistent.py`** → Testing superseded by CLI tools
- **`utils/ollama_client.py`** → Moved to `aquawar/ai/ollama_player.py`
- **Root `test_*.py` files** → Moved to `deprecated/` for safety
- **`notebook.ipynb`** → Development artifact moved to `deprecated/`

### Files Preserved As-Is:
- **`docs/`** → Documentation unchanged
- **`saves/`** → Game save data unchanged  
- **`.gitignore`** → No reorganization needed

## Implementation Plan

### Phase 1: Create New Structure (Parallel to Existing)
```bash
# Create new directory structure
mkdir -p aquawar/ai
mkdir -p cli
mkdir -p deprecated/demos
mkdir -p deprecated/utils
mkdir -p tests
```

### Phase 2: Move Core Package
```bash
# Rename core/ to aquawar/
mv core/ aquawar/
# Rename persistent_game.py for consistency
mv aquawar/persistent_game.py aquawar/persistent.py
```

### Phase 3: Extract and Create AI Package
**Create `aquawar/ai/base_player.py`** (NEW)
- Extract `GameAction` dataclass from `utils/ollama_client.py`
- Create abstract base class for AI players
- Define standard interface methods

**Create `aquawar/ai/ollama_player.py`** (EXTRACT from `utils/ollama_client.py`)
- Move `OllamaPlayer` class
- Move `OllamaGameManager` class  
- Move all tool definitions and LLM integration logic
- Update imports to use `aquawar.*` instead of `core.*`

### Phase 4: Create CLI Package
**Create `cli/ai_battle.py`** (BASED ON `demos/test_ollama_ai.py`)
- Copy main orchestration logic from `demos/test_ollama_ai.py`
- Enhance with command-line argument parsing
- Add tournament mode functionality
- Update imports to use new package structure
- Add comprehensive error handling and reporting

**Create `cli/game_manager.py`** (BASED ON `aquawar/persistent.py` CLI)
- Extract CLI functionality from `aquawar/persistent.py` main()
- Enhance with better UX and additional commands
- Keep persistent.py as pure library code
- Add game analysis and management features

### Phase 5: Move Deprecated Files
```bash
# Move experimental/deprecated demos
mv demos/ deprecated/

# Move utils after extracting AI logic
mv utils/ deprecated/

# Move root test files  
mv test_*.py deprecated/

# Move any other deprecated files
mv notebook.ipynb deprecated/
```

### Phase 6: Update All Imports
**Files requiring import updates:**
- `aquawar/persistent.py` - Update `from core.game` → `from aquawar.game`
- `aquawar/game.py` - Update `from core.fish` → `from aquawar.fish`  
- All new files in `cli/` and `aquawar/ai/`
- Any remaining files that reference old structure

### Phase 7: Create Package Entry Points
**Create `aquawar/__init__.py`**
```python
"""Aquawar - Turn-based fish battle game."""

__version__ = "2.0.0"

from .game import Game
from .fish import FISH_NAMES
from .config import GameConfig
from .persistent import PersistentGameManager

__all__ = ['Game', 'FISH_NAMES', 'GameConfig', 'PersistentGameManager']
```

**Create entry points for CLI tools:**
- Option A: Add to `setup.py`/`pyproject.toml` 
- Option B: Create simple launcher scripts

### Phase 8: Verification and Testing
1. **Import Testing**: Verify all imports work correctly
2. **Functionality Testing**: Run AI battles to ensure nothing broke
3. **Save Compatibility**: Ensure existing saves still load
4. **CLI Testing**: Verify all command-line interfaces work

## Migration Safety Checks

**Before each phase:**
1. Commit current state
2. Verify no circular imports  
3. Test that existing functionality still works
4. Check that saves directory structure is preserved

**After completion:**
1. Run full AI vs AI battle to verify end-to-end functionality
2. Test loading existing saves
3. Verify all CLI commands work
4. Check that no critical logic was lost in deprecated files

## Final Directory Structure
```
aquawar/
├── aquawar/
│   ├── __init__.py              # Package exports
│   ├── fish.py                  # Same (no imports)
│   ├── game.py                  # Same (imports: aquawar.fish)
│   ├── config.py                # Same (no imports) 
│   ├── persistent.py            # Renamed (imports: aquawar.game, aquawar.config)
│   └── ai/
│       ├── __init__.py          # AI package exports
│       ├── base_player.py       # NEW (imports: aquawar.game)
│       └── ollama_player.py     # EXTRACTED (imports: aquawar.game, aquawar.persistent, aquawar.config, .base_player)
├── cli/
│   ├── __init__.py              # CLI package
│   ├── game_manager.py          # NEW (imports: aquawar.persistent, aquawar.game, aquawar.config)
│   └── ai_battle.py             # NEW (imports: aquawar.ai.ollama_player, aquawar.config, aquawar.persistent)
├── deprecated/
│   ├── demos/                   # All old demos
│   ├── utils/                   # Old utils directory
│   ├── test_*.py                # Root test files
│   └── notebook.ipynb          # Development notebook
├── saves/                       # Game save data (unchanged)
├── docs/                        # Documentation (unchanged)
└── tests/                       # Future unit tests
```