#!/usr/bin/env python3
"""Demonstration of how easy it is to work with the new pickle structure."""

import pickle
import json
from pathlib import Path

def demonstrate_pickle_analysis():
    """Show how easy it is to analyze games with the new pickle structure."""
    
    # Find a real AI battle save file
    save_files = list(Path("saves").glob("**/latest.pkl"))
    if not save_files:
        print("No save files found to demonstrate with")
        return
        
    pickle_file = save_files[0]
    print(f"Analyzing game: {pickle_file}")
    print("=" * 60)
    
    # Load the pickle file
    with open(pickle_file, 'rb') as f:
        game_data = pickle.load(f)
    
    # Extract key information
    version = game_data.get('version', 'Unknown')
    state = game_data['state']
    history = game_data.get('history', [])
    current_damage = game_data.get('current_turn_damage', {})
    
    # Game overview
    print(f"📊 GAME ANALYSIS (Save format v{version})")
    print(f"   Game Turn: {state['game_turn']}")
    print(f"   Player Turn: {state['player_turn']}")  
    print(f"   Current Phase: {state['phase']}")
    print(f"   Current Player: {state['current_player']}")
    print(f"   Total History Entries: {len(history)}")
    
    # Player status
    print(f"\n👥 PLAYER STATUS:")
    for i, player in enumerate(state['players']):
        if player.get('team'):
            living = sum(1 for f in player['team']['fish'] if f['hp'] > 0)
            total_hp = sum(f['hp'] for f in player['team']['fish'] if f['hp'] > 0)
            print(f"   {player['name']}: {living}/4 fish alive ({total_hp} HP)")
        else:
            print(f"   {player['name']}: No team selected yet")
    
    # Current turn damage
    if any(current_damage.values()):
        print(f"\n💥 CURRENT TURN DAMAGE:")
        print(f"   Dealt: {current_damage['dealt']}")
        print(f"   Taken: {current_damage['taken']}")
    
    # History analysis with new unified structure  
    if history:
        print(f"\n📋 RECENT MOVES (Last 3):")
        recent = history[-3:]
        for entry in recent:
            player_name = state['players'][entry['player'] - 1]['name']
            status = "✅ Valid" if entry['valid'] else "❌ Invalid"
            move = entry['move'][:50] + "..." if len(entry['move']) > 50 else entry['move']
            dmg_info = f" (dealt {entry['damage_dealt']}, took {entry['damage_taken']})" if entry.get('damage_dealt', 0) > 0 or entry.get('damage_taken', 0) > 0 else ""
            print(f"   Turn {entry['game_turn']}: {player_name} - {status}")
            print(f"      Move: {move}{dmg_info}")
    
    # Retry analysis (show failed attempts) 
    failed_moves = [entry for entry in history if not entry['valid']]
    if failed_moves:
        print(f"\n⚠️  FAILED ATTEMPTS: {len(failed_moves)} total")
        for entry in failed_moves[-2:]:  # Show last 2 failures
            player_name = state['players'][entry['player'] - 1]['name']
            print(f"   Turn {entry['game_turn']}: {player_name} - {entry['move'][:60]}...")
    
    # Response metadata analysis (show LLM model info)
    model_info = {}
    for entry in history:
        if entry.get('response', {}).get('response_metadata'):
            model = entry['response']['response_metadata'].get('model', 'unknown')
            model_info[model] = model_info.get(model, 0) + 1
    
    if model_info:
        print(f"\n🤖 MODELS USED:")
        for model, count in model_info.items():
            print(f"   {model}: {count} requests")
    
    print("\n" + "=" * 60)
    print("✨ This rich analysis is possible thanks to the new unified pickle structure!")
    print("   - Version tracking ensures compatibility")  
    print("   - Unified history captures all attempts (valid + failed)")
    print("   - Damage tracking per turn enables detailed analysis")
    print("   - Complete LLM response metadata for debugging")

if __name__ == "__main__":
    demonstrate_pickle_analysis()