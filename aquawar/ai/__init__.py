"""AI player implementations for Aquawar."""

from .base_player import BasePlayer, GameAction
from .majority_player import MajorityVotePlayer

__all__ = ['BasePlayer', 'GameAction', 'MajorityVotePlayer']