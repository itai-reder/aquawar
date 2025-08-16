#!/usr/bin/env python3
"""
Detailed examination of aquawar turn pickle files.
"""

import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List


def examine_player_structure(player_data: Dict) -> None:
    """Examine the structure of a player object."""
    print("  Player structure:")
    for key, value in player_data.items():
        type_name = type(value).__name__
        if key == 'roster':
            print(f"    {key}: {type_name} (length: {len(value)})")
            if len(value) > 0:
                print(f"      Fish names: {value[:5]}{'...' if len(value) > 5 else ''}")
        elif key == 'hand':
            print(f"    {key}: {type_name} (length: {len(value) if isinstance(value, list) else 'N/A'})")
            if isinstance(value, list) and len(value) > 0:
                first_fish = value[0]
                if isinstance(first_fish, dict):
                    print(f"      First fish keys: {list(first_fish.keys())}")
                else:
                    print(f"      First fish: {first_fish}")
        elif key == 'bench':
            print(f"    {key}: {type_name} (length: {len(value) if isinstance(value, list) else 'N/A'})")
        else:
            truncated = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
            print(f"    {key}: {type_name} = {truncated}")


def examine_history_entry(entry: Dict) -> None:
    """Examine a single history entry."""
    print("  History entry structure:")
    for key, value in entry.items():
        type_name = type(value).__name__
        if key == 'input_messages':
            print(f"    {key}: {type_name} (length: {len(value)})")
            if len(value) > 0:
                msg_preview = value[0][:100] + "..." if len(value[0]) > 100 else value[0]
                print(f"      First message preview: {repr(msg_preview)}")
        elif key == 'response':
            print(f"    {key}: {type_name} with keys: {list(value.keys()) if isinstance(value, dict) else 'N/A'}")
        else:
            truncated = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
            print(f"    {key}: {type_name} = {truncated}")


def detailed_examine(file_path: str) -> None:
    """Perform detailed examination of the pickle file."""
    try:
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"=== DETAILED EXAMINATION: {Path(file_path).name} ===\n")
        
        # Examine state
        if 'state' in data:
            print("STATE STRUCTURE:")
            state = data['state']
            
            # Players
            if 'players' in state:
                print(f"Players: {len(state['players'])} players")
                for i, player in enumerate(state['players']):
                    print(f"  Player {i}:")
                    examine_player_structure(player)
                    print()
            
            # Other state fields
            for key, value in state.items():
                if key != 'players':
                    print(f"{key}: {type(value).__name__} = {value}")
            print()
        
        # Examine history
        if 'history' in data:
            print("HISTORY STRUCTURE:")
            history = data['history']
            print(f"Number of history entries: {len(history)}")
            if len(history) > 0:
                print("First history entry:")
                examine_history_entry(history[0])
            print()
        
        # Other top-level fields
        print("OTHER FIELDS:")
        for key, value in data.items():
            if key not in ['state', 'history']:
                print(f"{key}: {type(value).__name__} = {value}")
        
    except Exception as e:
        print(f"Error: {e}")


def main():
    file_path = "/home/itai/git/aquawar/saves/ai_battles/ai_battle_001/turn_001.pkl"
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    detailed_examine(file_path)


if __name__ == "__main__":
    main()