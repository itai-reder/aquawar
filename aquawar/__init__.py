"""Aquawar - Turn-based fish battle game."""

__version__ = "2.0.0"

from .game import Game, FISH_NAMES
from .config import GameConfig
from .persistent import PersistentGameManager

__all__ = ['Game', 'FISH_NAMES', 'GameConfig', 'PersistentGameManager']