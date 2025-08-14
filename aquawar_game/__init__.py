"""Aquawar game engine.

This package exposes :class:`Game` as the main entry point and can be used by
LLM agents to play the game in a stateless manner.  See ``demo.py`` for an
interactive example.
"""

from .game import Game, FISH_NAMES
from .fish import create_fish, Fish

__all__ = ["Game", "FISH_NAMES", "create_fish", "Fish"]
