#!/usr/bin/env python3
"""Test script for the persistent game functionality."""

import tempfile
import shutil
from pathlib import Path

def test_save_load_functionality():
    """Test the save/load functionality of the persistent game manager."""
    print("=== Testing Persistent Game Save/Load Functionality ===\n")
    
    # Create temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="aquawar_test_")
    print(f"Using test directory: {test_dir}")
    
    try:
        from core.persistent_game import PersistentGameManager
        from aquawar_game.game import Game
        
        # Test 1: Initialize new game
        print("\n1. Testing game initialization...")
        manager = PersistentGameManager(test_dir)
        game = manager.initialize_new_game("test_game", ("Alice", "Bob"))
        print(f"✓ Game initialized with players: {game.state.players[0].name} vs {game.state.players[1].name}")
        
        # Test 2: Save and load game
        print("\n2. Testing save/load...")
        save_path = manager.save_game_state(game, "test_game")
        print(f"✓ Game saved to: {save_path}")
        
        loaded_game = manager.load_game_state("test_game")
        print(f"✓ Game loaded successfully")
        print(f"  Players: {loaded_game.state.players[0].name} vs {loaded_game.state.players[1].name}")
        print(f"  Round: {loaded_game.state.round_no}, Turn: {loaded_game.state.turn_count}")
        
        # Test 3: Team selection and save
        print("\n3. Testing team selection and persistence...")
        team1 = ["Archerfish", "Pufferfish", "Electric Eel", "Sea Wolf"]
        loaded_game.select_team(0, team1)
        print(f"✓ Team selected for {loaded_game.state.players[0].name}: {team1}")
        
        save_path = manager.save_game_state(loaded_game, "test_game")
        print(f"✓ Game saved after team selection")
        
        # Load and verify team is preserved
        reloaded_game = manager.load_game_state("test_game")
        if reloaded_game.state.players[0].team is not None:
            fish_names = [f.name for f in reloaded_game.state.players[0].team.fish]
            print(f"✓ Team preserved after reload: {fish_names}")
        else:
            print("✗ Team not preserved after reload")
            
        # Test 4: Multiple turns and saves
        print("\n4. Testing multiple turn saves...")
        team2 = ["Sunfish", "Manta Ray", "Sea Turtle", "Octopus"]
        reloaded_game.select_team(1, team2)
        
        # Save multiple turns
        for turn in range(3):
            reloaded_game.state.turn_count = turn
            save_path = manager.save_game_state(reloaded_game, "test_game")
            print(f"✓ Saved turn {turn}")
        
        # Test 5: List saves
        print("\n5. Testing save listing...")
        saves = manager.list_saves("test_game")
        print(f"✓ Available saves: {saves}")
        
        # Test 6: Load specific turn
        print("\n6. Testing specific turn loading...")
        if saves:
            specific_game = manager.load_game_state("test_game", saves[0])
            print(f"✓ Loaded turn {saves[0]} successfully")
            print(f"  Turn count: {specific_game.state.turn_count}")
        
        # Test 7: Prompt generation
        print("\n7. Testing prompt generation...")
        prompt = manager.get_current_prompt(reloaded_game)
        print(f"✓ Generated prompt (length: {len(prompt)} chars)")
        if "ASSERTION PHASE" in prompt:
            print("✓ Correct phase detected: Assertion")
        elif "SELECTION PHASE" in prompt:
            print("✓ Correct phase detected: Selection")
        else:
            print("? Phase detection unclear")
            
        print("\n=== All Tests Passed! ===")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            shutil.rmtree(test_dir)
            print(f"\nCleaned up test directory: {test_dir}")
        except:
            pass


def test_cli_workflow():
    """Test a typical CLI workflow."""
    print("\n=== Testing CLI Workflow ===\n")
    
    test_dir = tempfile.mkdtemp(prefix="aquawar_cli_test_")
    
    try:
        import subprocess
        import sys
        
        # Test CLI commands
        base_cmd = [sys.executable, "-m", "aquawar_game.persistent_game", 
                   "--game-id", "cli_test", "--game-dir", test_dir]
        
        # 1. Initialize game
        print("1. Initializing game via CLI...")
        result = subprocess.run(base_cmd + ["--init"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Game initialization successful")
            print(f"  Output: {result.stdout.strip()}")
        else:
            print(f"✗ Game initialization failed: {result.stderr}")
            return False
        
        # 2. View prompt
        print("\n2. Viewing initial prompt...")
        result = subprocess.run(base_cmd + ["--view-prompt"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Prompt viewing successful")
            print(f"  Prompt contains selection phase: {'SELECTION PHASE' in result.stdout}")
        else:
            print(f"✗ Prompt viewing failed: {result.stderr}")
            return False
        
        # 3. Team selection
        print("\n3. Selecting team via CLI...")
        result = subprocess.run(base_cmd + ["--input-selection", "[0,1,2,3]"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Team selection successful")
            print(f"  Output: {result.stdout.strip()}")
        else:
            print(f"✗ Team selection failed: {result.stderr}")
            return False
        
        # 4. List saves
        print("\n4. Listing saves...")
        result = subprocess.run(base_cmd + ["--list-saves"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Save listing successful")
            print(f"  Output: {result.stdout.strip()}")
        else:
            print(f"✗ Save listing failed: {result.stderr}")
            return False
            
        print("\n=== CLI Workflow Tests Passed! ===")
        return True
        
    except subprocess.TimeoutExpired:
        print("✗ CLI command timed out")
        return False
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        return False
    finally:
        try:
            shutil.rmtree(test_dir)
        except:
            pass


if __name__ == "__main__":
    # Run basic save/load tests
    success1 = test_save_load_functionality()
    
    # Run CLI workflow tests  
    success2 = test_cli_workflow()
    
    if success1 and success2:
        print("\n🎉 All tests passed successfully!")
        exit(0)
    else:
        print("\n❌ Some tests failed")
        exit(1)