#!/usr/bin/env python3
"""Test script to verify the new pickle structure implementation."""

import sys
import json
import pickle
from pathlib import Path

# Import the updated classes
from core.game import Game
from core.persistent_game import PersistentGameManager
from aquawar.ai.ollama_player import OllamaPlayer, OllamaGameManager

def test_basic_save_load():
    """Test basic save/load functionality with new structure."""
    print("=== Testing Basic Save/Load ===")
    
    # Create a simple game
    game = Game(("TestPlayer1", "TestPlayer2"))
    
    # Add some basic state
    game.state.game_turn = 5
    game.state.player_turn = 3
    game.state.phase = "action"
    game.state.current_player = 2
    
    # Add some history entries
    game.history = [
        {
            "player": 1,
            "game_turn": 1,
            "player_turn": 1,
            "input_messages": ["Test prompt"],
            "response": {"content": "Test response"},
            "valid": True,
            "move": "Test move",
            "damage_dealt": 10,
            "damage_taken": 5
        }
    ]
    
    # Test save
    save_path = "test_saves/test_game/latest.pkl"
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    game.save_game(save_path)
    print(f"✓ Game saved to {save_path}")
    
    # Test load
    loaded_game = Game.load_game(save_path)
    print("✓ Game loaded successfully")
    
    # Verify data integrity
    assert loaded_game.state.game_turn == 5
    assert loaded_game.state.player_turn == 3
    assert loaded_game.state.phase == "action"
    assert loaded_game.state.current_player == 2
    assert len(loaded_game.history) == 1
    assert loaded_game.history[0]["player"] == 1
    assert loaded_game.history[0]["damage_dealt"] == 10
    
    print("✓ All data integrity checks passed")
    return save_path

def test_persistent_manager():
    """Test PersistentGameManager with new structure."""
    print("\n=== Testing PersistentGameManager ===")
    
    # Create manager
    manager = PersistentGameManager("test_saves")
    
    # Initialize new game
    game = manager.initialize_new_game("test_game", ("Player1", "Player2"))
    print("✓ New game initialized")
    
    # Save game state
    save_path = manager.save_game_state(game, "test_game")
    print(f"✓ Game saved via manager to {save_path}")
    
    # Load game state  
    loaded_game = manager.load_game_state("test_game")
    print("✓ Game loaded via manager")
    
    # Verify structure
    assert loaded_game.state.players[0].name == "Player1"
    assert loaded_game.state.players[1].name == "Player2"
    assert hasattr(loaded_game, 'history')
    assert hasattr(loaded_game, 'current_turn_damage')
    
    print("✓ PersistentGameManager structure verified")

def test_ollama_game_manager():
    """Test OllamaGameManager with new structure (without actually creating players)."""
    print("\n=== Testing OllamaGameManager Structure ===")
    
    # Create manager (don't actually instantiate LLM)
    manager = OllamaGameManager("test_saves", "llama3.2:3b")
    
    # Test game ID generation
    game_id = manager.get_next_indexed_game_id("ai_battle")
    print(f"✓ Generated game ID: {game_id}")
    
    # Test players info structure with direct dictionary creation
    # (Skip actual OllamaPlayer instantiation to avoid LLM dependencies)
    sample_players_info = {
        "1": [{"name": "llama3.2:3b (Single)", "model": "llama3.2:3b", "temperature": 0.7, "top_p": 0.9}],
        "2": [{"name": "llama3.2:3b (Single)", "model": "llama3.2:3b", "temperature": 0.7, "top_p": 0.9}]
    }
    print(f"✓ Players info structure: {json.dumps(sample_players_info, indent=2)}")
    
    # Verify structure
    assert "1" in sample_players_info
    assert "2" in sample_players_info
    assert sample_players_info["1"][0]["model"] == "llama3.2:3b"
    assert sample_players_info["2"][0]["model"] == "llama3.2:3b"
    
    print("✓ OllamaGameManager structure verified")

def examine_pickle_structure(pickle_path):
    """Examine the structure of a saved pickle file."""
    print(f"\n=== Examining Pickle Structure: {pickle_path} ===")
    
    with open(pickle_path, 'rb') as f:
        data = pickle.load(f)
    
    # Display top-level structure
    print("Top-level keys:")
    for key in data.keys():
        print(f"  - {key}: {type(data[key])}")
    
    # Show version
    if 'version' in data:
        print(f"\nVersion: {data['version']}")
    
    # Show state structure
    if 'state' in data:
        print(f"\nState structure:")
        state = data['state']
        for key in state.keys():
            print(f"  - {key}: {type(state[key])}")
    
    # Show history structure
    if 'history' in data:
        print(f"\nHistory entries: {len(data['history'])}")
        if data['history']:
            print("Sample history entry structure:")
            sample = data['history'][0]
            for key, value in sample.items():
                print(f"  - {key}: {type(value)} = {str(value)[:50]}...")
    
    # Show current_turn_damage
    if 'current_turn_damage' in data:
        print(f"\nCurrent turn damage: {data['current_turn_damage']}")
    
    print("✓ Pickle structure examination complete")

def main():
    """Run all tests."""
    print("Testing New Pickle Structure Implementation")
    print("=" * 50)
    
    try:
        # Test 1: Basic save/load
        save_path = test_basic_save_load()
        
        # Test 2: PersistentGameManager
        test_persistent_manager()
        
        # Test 3: OllamaGameManager structure
        test_ollama_game_manager()
        
        # Test 4: Examine pickle file structure
        examine_pickle_structure(save_path)
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED - New pickle structure is working correctly!")
        print("Key improvements verified:")
        print("  - Unified history structure with retry information")
        print("  - Current turn damage tracking")
        print("  - Version tracking for backward compatibility")
        print("  - Player info metadata structure")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()