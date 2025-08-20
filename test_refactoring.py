#!/usr/bin/env python3
"""
Simple test to verify the refactored OllamaPlayer functionality.
This test will check that the new methods exist and can be called.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aquawar.ai.ollama_player import OllamaPlayer
from aquawar.persistent import PersistentGameManager

def test_refactored_methods():
    print("Testing refactored OllamaPlayer methods...")
    
    # Create a test player
    player = OllamaPlayer("test_player", "llama3.2:3b", debug=True)
    
    # Check that new methods exist
    assert hasattr(player, 'make_move'), "make_move method missing"
    assert hasattr(player, 'save_turn_pickle'), "save_turn_pickle method missing"
    assert hasattr(player, 'end_game_turn'), "end_game_turn method missing"
    assert hasattr(player, 'set_game_manager'), "set_game_manager method missing"
    
    print("✓ All new methods exist")
    
    # Create a simple game manager to test set_game_manager
    game_manager = PersistentGameManager(
        save_dir="/tmp/test_saves",
        debug=True
    )
    
    player2 = OllamaPlayer("test_player2", "llama3.2:3b", debug=True)
    
    # Test set_game_manager
    player.set_game_manager(game_manager, player2)
    
    assert player.game_manager is game_manager, "Game manager not set correctly"
    assert player.opponent is player2, "Opponent not set correctly"
    
    print("✓ set_game_manager works correctly")
    print("✓ All refactoring tests passed!")

if __name__ == "__main__":
    test_refactored_methods()
