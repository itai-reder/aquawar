"""AI player implementations for Aquawar."""

from .base_player import BasePlayer, GameAction
from .ollama_player import OllamaPlayer
# Note: MajorityVotePlayer can be imported directly when needed

__all__ = ['BasePlayer', 'GameAction', 'OllamaPlayer']