#!/usr/bin/env python3
"""
Script to examine the structure of turn pickle files from aquawar AI battles.
"""

import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List


def truncate_value(value: Any, max_length: int = 100) -> str:
    """Convert value to string and truncate if too long."""
    str_val = str(value)
    if len(str_val) > max_length:
        return str_val[:max_length] + "..."
    return str_val


def examine_dict_structure(data: Dict, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> None:
    """Recursively examine dictionary structure."""
    if current_depth >= max_depth:
        print(f"{prefix}[...] (max depth reached)")
        return
    
    for key, value in data.items():
        type_name = type(value).__name__
        
        if isinstance(value, dict):
            print(f"{prefix}{key}: {type_name} ({len(value)} keys)")
            if len(value) > 0:
                examine_dict_structure(value, prefix + "  ", max_depth, current_depth + 1)
        elif isinstance(value, (list, tuple)):
            print(f"{prefix}{key}: {type_name} (length: {len(value)})")
            if len(value) > 0:
                first_item = value[0]
                first_type = type(first_item).__name__
                print(f"{prefix}  [0]: {first_type} = {truncate_value(first_item, 50)}")
                if isinstance(first_item, dict) and current_depth < max_depth - 1:
                    examine_dict_structure(first_item, prefix + "    ", max_depth, current_depth + 2)
        else:
            sample_val = truncate_value(value, 80)
            print(f"{prefix}{key}: {type_name} = {sample_val}")


def examine_pickle_file(file_path: str) -> None:
    """Load and examine a pickle file structure."""
    path = Path(file_path)
    
    if not path.exists():
        print(f"Error: File {file_path} does not exist")
        return
    
    try:
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"=== Examining {file_path} ===")
        print(f"File size: {path.stat().st_size} bytes")
        print(f"Top-level type: {type(data).__name__}")
        print()
        
        if isinstance(data, dict):
            print("Top-level keys:")
            for key in data.keys():
                print(f"  - {key}")
            print()
            
            examine_dict_structure(data)
        else:
            print(f"Data is not a dictionary. Type: {type(data).__name__}")
            print(f"Value: {truncate_value(data)}")
            
    except Exception as e:
        print(f"Error loading pickle file: {e}")


def main():
    # Default file to examine
    default_file = "/home/itai/git/aquawar/saves/ai_battles/ai_battle_001/turn_001.pkl"
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = default_file
    
    examine_pickle_file(file_path)
    
    # Also examine a few more files to see if structure is consistent
    battle_dir = Path("/home/itai/git/aquawar/saves/ai_battles/ai_battle_001")
    if battle_dir.exists():
        print("\n" + "="*60)
        print("Examining additional files for structure consistency:")
        
        for turn_file in sorted(battle_dir.glob("turn_*.pkl"))[:3]:  # Check first 3 turn files
            if turn_file.name != "turn_001.pkl":  # Skip the one we already examined
                print(f"\n--- Quick check: {turn_file.name} ---")
                try:
                    with open(turn_file, 'rb') as f:
                        data = pickle.load(f)
                    if isinstance(data, dict):
                        print(f"Keys: {list(data.keys())}")
                        if 'state' in data:
                            state_keys = list(data['state'].keys()) if isinstance(data['state'], dict) else "Not a dict"
                            print(f"State keys: {state_keys}")
                    else:
                        print(f"Type: {type(data).__name__}")
                except Exception as e:
                    print(f"Error: {e}")


if __name__ == "__main__":
    main()