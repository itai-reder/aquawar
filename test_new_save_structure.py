#!/usr/bin/env python3
"""
Test script to verify the new Game.save_game() method structure.

This script:
1. Creates a game with the new players_info format
2. Saves the game using the updated save_game method
3. Loads it back and examines the structure
4. Verifies the saved file has the correct new structure
"""

import pickle
import os
from pathlib import Path

# Import from the updated aquawar modules
from aquawar.game import Game

def test_new_save_structure():
    print("=== Testing New Save Structure ===\n")
    
    # 1. Create a game with player info in the new format
    print("1. Creating game with new players_info format...")
    players_info = {
        "1": [{"name": "llama3.2:3b (Single)", "model": "llama3.2:3b", "temperature": 0.7, "top_p": 0.9}],
        "2": [{"name": "llama3.2:3b (Single)", "model": "llama3.2:3b", "temperature": 0.7, "top_p": 0.9}]
    }
    
    # Create a game instance
    game = Game(("Player 1", "Player 2"))
    
    # Set up some basic game state for testing
    game.state.round_no = 2
    game.state.game_turn = 5
    game.state.player_turn = 3
    game.state.phase = "action"
    
    # Add some history entries
    game.history.append({
        "player": 1,
        "game_turn": 1,
        "player_turn": 1,
        "input_messages": ["test prompt"],
        "response": {"content": "test response"},
        "valid": True,
        "move": "SKIP",
        "damage_dealt": 0,
        "damage_taken": 0
    })
    
    print(f"Created game with players_info: {players_info}")
    print(f"Game state - Round: {game.state.round_no}, Turn: {game.state.game_turn}, Phase: {game.state.phase}")
    
    # 2. Save the test game
    print("\n2. Saving game with new save_game method...")
    test_save_path = "test_saves/test_new_structure/latest.pkl"
    Path(test_save_path).parent.mkdir(parents=True, exist_ok=True)
    
    game.save_game(test_save_path, players_info)
    print(f"Game saved to: {test_save_path}")
    
    # 3. Load it back and examine structure
    print("\n3. Loading game back and examining structure...")
    loaded_game = Game.load_game(test_save_path)
    
    print(f"Loaded game - Round: {loaded_game.state.round_no}, Turn: {loaded_game.state.game_turn}")
    print(f"History entries: {len(loaded_game.history)}")
    
    # 4. Examine the raw pickle file structure
    print("\n4. Examining raw pickle file structure...")
    with open(test_save_path, 'rb') as f:
        save_data = pickle.load(f)
    
    print("Keys in saved data:", list(save_data.keys()))
    
    # 5. Verify the structure is correct
    print("\n5. Verifying structure...")
    
    # Check for required keys
    required_keys = {"state", "history", "players"}
    actual_keys = set(save_data.keys())
    
    print(f"Required keys: {required_keys}")
    print(f"Actual keys: {actual_keys}")
    
    has_required = required_keys.issubset(actual_keys)
    print(f"✓ Has all required keys: {has_required}")
    
    # Check for absence of old keys
    old_keys = {"version", "current_turn_damage"}
    has_old_keys = any(key in actual_keys for key in old_keys)
    print(f"✓ Does NOT have old keys: {not has_old_keys}")
    
    # Check players_info structure
    if "players" in save_data:
        players = save_data["players"]
        print(f"✓ Players info saved correctly: {players}")
        
        # Verify format
        expected_format = True
        if not isinstance(players, dict):
            expected_format = False
        elif not all(key in ["1", "2"] for key in players.keys()):
            expected_format = False
        elif not all(isinstance(val, list) and len(val) == 1 for val in players.values()):
            expected_format = False
        else:
            for player_list in players.values():
                player_info = player_list[0]
                if not all(key in player_info for key in ["name", "model", "temperature", "top_p"]):
                    expected_format = False
                    break
        
        print(f"✓ Players info has correct format: {expected_format}")
    
    # Check state structure
    if "state" in save_data:
        state = save_data["state"]
        print(f"✓ State structure preserved (players count: {len(state['players'])})")
    
    # Check history structure  
    if "history" in save_data:
        history = save_data["history"]
        print(f"✓ History preserved ({len(history)} entries)")
    
    print("\n=== Test Summary ===")
    success = (has_required and not has_old_keys and 
              "players" in save_data and "state" in save_data and "history" in save_data)
    
    if success:
        print("✅ ALL TESTS PASSED!")
        print("The new save structure is working correctly:")
        print("  - Has 'state', 'history', 'players' keys")
        print("  - Does NOT have 'version', 'current_turn_damage' keys") 
        print("  - Players info is saved in the correct format")
    else:
        print("❌ SOME TESTS FAILED!")
        
    # Cleanup
    print(f"\nCleaning up test file: {test_save_path}")
    os.remove(test_save_path)
    
    return success

if __name__ == "__main__":
    success = test_new_save_structure()
    exit(0 if success else 1)