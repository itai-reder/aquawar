#!/usr/bin/env python3
"""Examine the structure of saved game files to find history entries."""

import pickle
import sys
from pathlib import Path

def examine_game_structure(filepath):
    """Examine the structure of a saved game file."""
    try:
        with open(filepath, 'rb') as f:
            game_state = pickle.load(f)
        
        print(f"📁 File: {filepath.name}")
        print(f"📊 Type: {type(game_state)}")
        
        # Check for history attribute
        if hasattr(game_state, 'history'):
            history = game_state.history
            print(f"📜 History entries: {len(history)}")
            
            if len(history) > 0:
                print("\n🔍 SAMPLE HISTORY ENTRIES:")
                for i, entry in enumerate(history[:3]):  # Show first 3
                    player = entry.get('player', 'MISSING')
                    game_turn = entry.get('game_turn', 'MISSING')
                    valid = entry.get('valid', 'MISSING')
                    move = str(entry.get('move', 'MISSING'))[:60]
                    
                    print(f"  [{i}] Player: {player}, Turn: {game_turn}, Valid: {valid}")
                    print(f"      Move: {move}")
                    
                    # Check for our unified function fields
                    attempt = entry.get('attempt', 'NOT_PRESENT')
                    max_attempts = entry.get('max_attempts', 'NOT_PRESENT')
                    error_details = 'error_details' in entry
                    
                    print(f"      Attempt: {attempt}, Max: {max_attempts}, ErrorDetails: {error_details}")
                    
                if len(history) > 3:
                    print(f"  ... and {len(history) - 3} more entries")
            
        else:
            print("❌ No 'history' attribute found")
        
        # Check other attributes
        print("\n🔍 AVAILABLE ATTRIBUTES:")
        for attr in sorted(dir(game_state)):
            if not attr.startswith('_'):
                try:
                    value = getattr(game_state, attr)
                    if callable(value):
                        print(f"  {attr}() - method")
                    else:
                        print(f"  {attr} - {type(value).__name__}")
                except:
                    print(f"  {attr} - (error accessing)")
        
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error examining {filepath.name}: {e}")
        print("-" * 60)

def main():
    """Examine key saved game files."""
    
    base_path = Path('/home/itai/git/aquawar/saves/llama3.2_3b_single/llama3.1_8b_single/round_001')
    
    # Check key files
    files_to_check = [
        'latest.pkl',      # Final state
        'turn_005.pkl',    # Mid-game state  
        'turn_010.pkl'     # Later state
    ]
    
    print("🔍 GAME FILE STRUCTURE EXAMINATION")
    print("=" * 60)
    
    for filename in files_to_check:
        filepath = base_path / filename
        if filepath.exists():
            examine_game_structure(filepath)
        else:
            print(f"❌ File not found: {filename}")
            print("-" * 60)

if __name__ == '__main__':
    main()