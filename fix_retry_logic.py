#!/usr/bin/env python3
"""
Fix for the missing max_tries retry logic in assertions and actions.
This patch adds proper retry handling to the OllamaGameManager.
"""

def get_fixed_game_loop():
    """Return the fixed game loop code with proper retry logic."""
    return '''
            # Main game loop
            game_turn = 0
            while game_turn < max_turns:
                game_turn += 1
                current_player_idx = game.state.current_player - 1  # Convert 1/2 to 0/1
                current_player = players[current_player_idx]
                
                print(f"\\nGame Turn {game_turn}: {current_player.name}'s turn (Player Turn {game.state.player_turn})")
                print(f"Phase: {game.state.phase}")
                
                # Check for round over
                winner = game.round_over()
                if winner is not None:
                    winner_name = game.state.players[winner].name
                    print(f"\\n🎉 Game Over! {winner_name} wins!")
                    
                    # Update evaluation: game completed
                    game._update_evaluation_game_status("completed")
                    
                    self.persistent_manager.save_game_state(game, final_game_id, players_info)
                    
                    return {
                        "success": True,
                        "winner": winner,
                        "winner_name": winner_name,
                        "turns": game_turn,
                        "game_id": final_game_id
                    }
                
                # Execute turn with retry logic
                success = False
                for attempt in range(max_tries):
                    action = None
                    if game.state.phase == "assertion":
                        action = current_player.make_assertion()
                        print(f"Assertion (attempt {attempt + 1}): {action.message}")
                        
                    elif game.state.phase == "action":
                        action = current_player.make_action()
                        print(f"Action (attempt {attempt + 1}): {action.message}")
                    
                    if action and action.success:
                        success = True
                        break
                    else:
                        print(f"❌ Turn failed: {action.message if action else 'No action returned'}")
                        if attempt < max_tries - 1:
                            print(f"Retrying... ({attempt + 2}/{max_tries})")
                        
                if not success:
                    print(f"❌ Turn failed after {max_tries} attempts. Terminating game.")
                    game._update_evaluation_game_status("error")
                    self.persistent_manager.save_game_state(game, final_game_id, players_info)
                    return {
                        "success": False,
                        "error": f"Turn failed after {max_tries} attempts",
                        "turns": game_turn,
                        "game_id": final_game_id
                    }
                
                # Save after each turn
                self.persistent_manager.save_game_state(game, final_game_id, players_info)
                
                # Display current team status
                self._display_team_status(game)
'''

if __name__ == "__main__":
    print("This script contains the fix for the retry logic issue.")
    print("The fixed code needs to be manually applied to aquawar/ai/ollama_player.py")
    print("\\nThe issue: max_tries retry logic was only implemented for team selection,")
    print("but not for assertions and actions. This caused games to hang when")
    print("actions failed, because the game loop continued without completing the turn.")
