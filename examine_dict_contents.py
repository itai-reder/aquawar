#!/usr/bin/env python3
"""Examine the contents of saved game dictionaries."""

import pickle
import json
from pathlib import Path

def examine_dict_contents(filepath):
    """Examine the contents of a saved game dictionary."""
    try:
        with open(filepath, 'rb') as f:
            game_data = pickle.load(f)
        
        print(f"📁 File: {filepath.name}")
        print(f"📊 Type: {type(game_data)}")
        
        if isinstance(game_data, dict):
            print(f"🗝️  Keys: {list(game_data.keys())}")
            
            # Look for history in various possible locations
            if 'history' in game_data:
                history = game_data['history']
                print(f"📜 Direct history entries: {len(history)}")
                
                if len(history) > 0:
                    print("\n🔍 SAMPLE HISTORY ENTRIES:")
                    for i, entry in enumerate(history[:2]):  # Show first 2
                        print(f"  [{i}] Entry keys: {list(entry.keys()) if isinstance(entry, dict) else 'Not dict'}")
                        if isinstance(entry, dict):
                            player = entry.get('player', 'MISSING')
                            game_turn = entry.get('game_turn', 'MISSING')
                            valid = entry.get('valid', 'MISSING')
                            move = str(entry.get('move', 'MISSING'))[:40]
                            
                            print(f"      Player: {player}, Turn: {game_turn}, Valid: {valid}")
                            print(f"      Move: {move}")
                            
                            # Check for our unified function fields
                            attempt = entry.get('attempt', 'NOT_PRESENT')
                            max_attempts = entry.get('max_attempts', 'NOT_PRESENT')
                            error_details = 'error_details' in entry
                            
                            print(f"      Attempt: {attempt}, Max: {max_attempts}, ErrorDetails: {error_details}")
                            
                    if len(history) > 2:
                        print(f"  ... and {len(history) - 2} more entries")
            
            # Check if game state contains a nested game object  
            elif 'game' in game_data:
                game_obj = game_data['game']
                print(f"📊 Nested game type: {type(game_obj)}")
                if hasattr(game_obj, 'history'):
                    history = game_obj.history
                    print(f"📜 Nested game history entries: {len(history)}")
                    
                    if len(history) > 0:
                        print("\n🔍 NESTED GAME HISTORY ENTRIES:")
                        for i, entry in enumerate(history[:2]):
                            print(f"  [{i}] Entry keys: {list(entry.keys()) if isinstance(entry, dict) else 'Not dict'}")
                            if isinstance(entry, dict):
                                player = entry.get('player', 'MISSING')
                                game_turn = entry.get('game_turn', 'MISSING')
                                valid = entry.get('valid', 'MISSING')
                                
                                print(f"      Player: {player}, Turn: {game_turn}, Valid: {valid}")
                                
                                # Check unified function fields
                                attempt = entry.get('attempt', 'NOT_PRESENT')
                                max_attempts = entry.get('max_attempts', 'NOT_PRESENT')
                                error_details = 'error_details' in entry
                                
                                print(f"      Attempt: {attempt}, Max: {max_attempts}, ErrorDetails: {error_details}")
                                
                        if len(history) > 2:
                            print(f"  ... and {len(history) - 2} more entries")
            
            else:
                print("❌ No 'history' or 'game' key found")
                # Show some sample data structure
                print("\n🔍 SAMPLE DATA STRUCTURE:")
                for key in list(game_data.keys())[:5]:
                    value = game_data[key]
                    if isinstance(value, (str, int, float, bool)):
                        print(f"  {key}: {value}")
                    else:
                        print(f"  {key}: {type(value).__name__} (length: {len(value) if hasattr(value, '__len__') else 'N/A'})")
        
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error examining {filepath.name}: {e}")
        print("-" * 60)

def main():
    """Examine key saved game files for history data."""
    
    base_path = Path('/home/itai/git/aquawar/saves/llama3.2_3b_single/llama3.1_8b_single/round_001')
    
    files_to_check = [
        'latest.pkl',
        'turn_005.pkl',
        'turn_015.pkl'
    ]
    
    print("🔍 SAVED GAME DICTIONARY EXAMINATION")
    print("=" * 60)
    
    for filename in files_to_check:
        filepath = base_path / filename
        if filepath.exists():
            examine_dict_contents(filepath)
        else:
            print(f"❌ File not found: {filename}")
            print("-" * 60)

if __name__ == '__main__':
    main()