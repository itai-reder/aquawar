#!/usr/bin/env python3
"""Demonstration of Aquawar v1.2.0 with simulated AI players.

This script demonstrates the complete functionality by simulating AI decision-making
and running a full game until one player loses all fish.
"""

import sys
import time
import random
from pathlib import Path

# Add the aquawar_game module to path
sys.path.insert(0, str(Path(__file__).parent))

from aquawar_game.game import Game, FISH_NAMES
from aquawar_game.persistent_game import PersistentGameManager


class SimulatedAIPlayer:
    """Simulated AI player that makes strategic decisions."""
    
    def __init__(self, name: str):
        self.name = name
        self.game = None
        self.player_index = None
    
    def set_game_context(self, game: Game, player_index: int):
        self.game = game
        self.player_index = player_index
    
    def select_team(self, available_fish: list[str]) -> list[str]:
        """Select a strategic team composition."""
        # Avoid Mimic Fish for simplicity, select a balanced team
        non_mimic_fish = [f for f in available_fish if f != "Mimic Fish"]
        
        # Prefer certain fish combinations for strategy
        priority_fish = ["Great White Shark", "Hammerhead Shark", "Electric Eel", "Sea Turtle", 
                        "Octopus", "Archerfish", "Pufferfish", "Sea Wolf"]
        
        selected = []
        for fish in priority_fish:
            if fish in non_mimic_fish and len(selected) < 4:
                selected.append(fish)
        
        # Fill remaining slots if needed
        while len(selected) < 4:
            remaining = [f for f in non_mimic_fish if f not in selected]
            if remaining:
                selected.append(random.choice(remaining))
        
        return selected[:4]
    
    def make_assertion(self) -> tuple[bool, int, str]:
        """Make assertion decision. Returns (should_assert, enemy_index, fish_name)."""
        if not self.game or self.player_index is None:
            return False, 0, ""
        
        enemy_team = self.game.state.players[1 - self.player_index].team
        if not enemy_team:
            return False, 0, ""
        
        # Look for hidden enemies
        hidden_enemies = []
        for i, fish in enumerate(enemy_team.fish):
            if fish.is_alive() and not fish.revealed:
                hidden_enemies.append(i)
        
        if not hidden_enemies:
            return False, 0, ""
        
        # 30% chance to make an assertion
        if random.random() < 0.3:
            enemy_index = random.choice(hidden_enemies)
            # Make educated guess based on fish behavior patterns
            fish_name = random.choice(["Great White Shark", "Electric Eel", "Sea Turtle", "Archerfish"])
            return True, enemy_index, fish_name
        
        return False, 0, ""
    
    def make_action(self) -> tuple[str, int, int]:
        """Make action decision. Returns (action_type, fish_index, target_index)."""
        if not self.game or self.player_index is None:
            return "NORMAL", 0, 0
        
        my_team = self.game.state.players[self.player_index].team
        enemy_team = self.game.state.players[1 - self.player_index].team
        
        if not my_team or not enemy_team:
            return "NORMAL", 0, 0
        
        # Find living fish on my team
        living_fish = []
        for i, fish in enumerate(my_team.fish):
            if fish.is_alive():
                living_fish.append(i)
        
        if not living_fish:
            return "NORMAL", 0, 0
        
        # Find living enemies
        living_enemies = []
        for i, fish in enumerate(enemy_team.fish):
            if fish.is_alive():
                living_enemies.append(i)
        
        if not living_enemies:
            return "NORMAL", 0, 0
        
        # Choose action
        fish_index = random.choice(living_fish)
        target_index = random.choice(living_enemies)
        
        # 40% chance to use active skill, 60% normal attack
        action_type = "ACTIVE" if random.random() < 0.4 else "NORMAL"
        
        return action_type, fish_index, target_index


def run_simulated_ai_game(game_id: str, max_turns: int = 200) -> dict:
    """Run a complete simulated AI vs AI game."""
    
    # Initialize persistent manager
    manager = PersistentGameManager("saves/simulated_ai")
    
    # Create game
    game = manager.initialize_new_game(game_id, ("AI Alpha", "AI Beta"))
    
    # Create simulated AI players
    player1 = SimulatedAIPlayer("AI Alpha")
    player2 = SimulatedAIPlayer("AI Beta")
    
    player1.set_game_context(game, 0)
    player2.set_game_context(game, 1)
    
    players = [player1, player2]
    
    print(f"Starting simulated AI vs AI game: {player1.name} vs {player2.name}")
    
    # Team selection phase
    for i, player in enumerate(players):
        print(f"\n{player.name} selecting team...")
        available_fish = game.state.players[i].roster.copy()
        selected_team = player.select_team(available_fish)
        
        game.select_team(i, selected_team)
        game.add_history_entry(i, f"Team selection for {player.name}", f"Selected: {selected_team}", "valid")
        
        print(f"✓ Selected team: {selected_team}")
        manager.save_game_state(game, game_id)
    
    print("\nStarting battle phase...")
    
    # Main game loop
    turn_count = 0
    while turn_count < max_turns:
        turn_count += 1
        current_player_idx = game.state.turn_player
        current_player = players[current_player_idx]
        
        print(f"\nTurn {turn_count}: {current_player.name}'s turn (Phase: {game.state.phase})")
        
        # Check for round over
        winner = game.round_over()
        if winner is not None:
            winner_name = game.state.players[winner].name
            print(f"\n🎉 Game Over! {winner_name} wins!")
            
            manager.save_game_state(game, game_id)
            
            return {
                "success": True,
                "winner": winner,
                "winner_name": winner_name,
                "turns": turn_count,
                "game_id": game_id
            }
        
        # Execute turn based on phase
        if game.state.phase == "assertion":
            should_assert, enemy_index, fish_name = current_player.make_assertion()
            
            if should_assert:
                result = game.perform_assertion(current_player_idx, enemy_index, fish_name)
                print(f"Assertion: {current_player.name} asserts enemy {enemy_index} is {fish_name}")
                print(f"Result: {result}")
            else:
                result = game.skip_assertion(current_player_idx)
                print(f"Assertion: {current_player.name} skips assertion")
                
        elif game.state.phase == "action":
            action_type, fish_index, target_index = current_player.make_action()
            result = game.perform_action(current_player_idx, fish_index, action_type, target_index)
            print(f"Action: {current_player.name} fish {fish_index} {action_type.lower()} attacks target {target_index}")
            print(f"Result: {result}")
        
        # Save after each turn
        manager.save_game_state(game, game_id)
        
        # Display team status
        print("\n--- Team Status ---")
        for i, player_state in enumerate(game.state.players):
            if player_state.team:
                living = len(player_state.team.living_fish())
                total_hp = sum(f.hp for f in player_state.team.fish if f.is_alive())
                damage_dealt = player_state.damage_dealt
                print(f"{player_state.name}: {living}/4 fish alive, {total_hp} HP, {damage_dealt} damage dealt")
        print("-------------------")
    
    # Game exceeded max turns
    return {
        "success": False,
        "error": f"Game exceeded maximum turns ({max_turns})",
        "turns": turn_count,
        "game_id": game_id
    }


def main():
    """Run the simulated AI vs AI demonstration."""
    print("🐟 Aquawar v1.2.0 - Simulated AI vs AI Demo")
    print("=" * 50)
    print("This demonstrates the complete v1.2.0 functionality")
    print("with simulated AI decision-making.")
    
    game_id = "simulated_ai_demo"
    
    start_time = time.time()
    result = run_simulated_ai_game(game_id, max_turns=200)
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
        
        # Load final stats
        try:
            manager = PersistentGameManager("saves/simulated_ai")
            final_game = manager.load_game_state(game_id)
            
            print("\n📈 Final Statistics:")
            for i, player in enumerate(final_game.state.players):
                if player.team:
                    living = len(player.team.living_fish())
                    total_hp = sum(f.hp for f in player.team.fish if f.is_alive())
                    damage_dealt = player.damage_dealt
                    print(f"  {player.name}: {living}/4 fish, {total_hp} HP, {damage_dealt} damage dealt")
            
            print(f"\n📝 Total history entries: {len(final_game.history)}")
            print(f"🔧 Save format version: 1.2.0")
            
        except Exception as e:
            print(f"⚠️ Could not load final stats: {e}")
        
        print("\n✅ Aquawar v1.2.0 demonstration completed successfully!")
        print("\nThe system includes:")
        print("  ✓ Enhanced history tracking")
        print("  ✓ Damage tracking per player")
        print("  ✓ Validity monitoring for AI behavior")
        print("  ✓ Ollama/Langchain integration (demonstrated separately)")
        print("  ✓ Persistent game state with full recoverability")
        print("  ✓ Version 1.2.0 save format")
        
        return 0
        
    else:
        print(f"❌ Game failed: {result['error']}")
        print(f"📊 Turns completed: {result.get('turns', 0)}")
        print(f"⏱️ Duration: {elapsed:.1f} seconds")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())