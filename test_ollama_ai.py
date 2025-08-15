#!/usr/bin/env python3
"""Test script for Ollama AI vs AI gameplay.

This script demonstrates version 1.2.0 with Ollama support, running
two llama3.2:3b players against each other until one loses all fish.
"""

import sys
import time
from pathlib import Path

# Add the aquawar_game module to path
sys.path.insert(0, str(Path(__file__).parent))

from aquawar_game.ollama_client import OllamaGameManager


def main():
    """Run AI vs AI test game."""
    print("🐟 Aquawar v1.2.0 - Ollama AI vs AI Demo")
    print("=" * 50)
    
    # Check if we have the required dependencies
    try:
        from langchain_ollama import ChatOllama
        from langchain_core.tools import tool
        print("✓ Langchain dependencies found")
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install: pip install langchain-ollama langchain-core")
        return 1
    
    # Test Ollama connection
    print("\n🔧 Testing Ollama connection...")
    try:
        test_llm = ChatOllama(model="llama3.2:3b", temperature=0)
        response = test_llm.invoke("Say 'Hello'")
        print("✓ Ollama llama3.2:3b model accessible")
    except Exception as e:
        print(f"❌ Ollama connection failed: {e}")
        print("Please ensure Ollama is running and llama3.2:3b model is installed:")
        print("  1. Start Ollama: ollama serve")
        print("  2. Pull model: ollama pull llama3.2:3b")
        return 1
    
    # Initialize game manager
    print("\n🎮 Initializing AI vs AI game...")
    game_manager = OllamaGameManager(save_dir="saves/ollama_test", model="llama3.2:3b")
    
    # Run the game
    game_id = "ai_vs_ai_demo"
    player1_name = "Aqua AI Alpha"
    player2_name = "Aqua AI Beta"
    
    print(f"🤖 Players: {player1_name} vs {player2_name}")
    print("🎯 Objective: Play until one player loses all fish")
    print("\n🚀 Starting game...")
    
    start_time = time.time()
    
    result = game_manager.run_ai_vs_ai_game(
        game_id=game_id,
        max_turns=200  # Prevent infinite games
    )
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\n" + "=" * 50)
    print("🏆 GAME RESULTS")
    print("=" * 50)
    
    if result["success"]:
        print(f"🎉 Winner: {result['winner_name']}")
        print(f"📊 Total turns: {result['turns']}")
        print(f"⏱️ Duration: {elapsed:.1f} seconds")
        print(f"💾 Game saved as: {result['game_id']}")
        
        # Load final game state to show final stats
        try:
            from aquawar_game.persistent_game import PersistentGameManager
            pm = PersistentGameManager("saves/ollama_test")
            final_game = pm.load_game_state(game_id)
            
            print("\n📈 Final Statistics:")
            for i, player in enumerate(final_game.state.players):
                if player.team:
                    living = len(player.team.living_fish())
                    total_hp = sum(f.hp for f in player.team.fish if f.is_alive())
                    damage_dealt = player.damage_dealt
                    print(f"  {player.name}: {living}/4 fish, {total_hp} HP, {damage_dealt} damage dealt")
            
            print(f"\n📝 Total history entries: {len(final_game.history)}")
            
        except Exception as e:
            print(f"⚠️ Could not load final stats: {e}")
        
        print("\n✅ Test completed successfully!")
        return 0
        
    else:
        print(f"❌ Game failed: {result['error']}")
        print(f"📊 Turns completed: {result.get('turns', 0)}")
        print(f"⏱️ Duration: {elapsed:.1f} seconds")
        
        print("\n❌ Test failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())