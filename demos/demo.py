"""Interactive demo for the Aquawar engine.

Run ``python -m aquawar_game.demo`` to play a small two-player match from the
command line.  The interface mirrors the text prompts that LLM agents would
receive when controlling a player.
"""

from __future__ import annotations

import sys
from typing import List

from core.game import Game, FISH_NAMES


def prompt_select(game: Game, player_idx: int) -> List[str]:
    player = game.state.players[player_idx]
    print(game.prompt_for_selection(player_idx))
    
    selection_input = input("Enter your selection (e.g., [0, 3, 7, 11]): ")
    try:
        # Parse the list format
        selection_indices = eval(selection_input)
        if not isinstance(selection_indices, list) or len(selection_indices) != 4:
            raise ValueError("Must select exactly 4 fish")
        
        # Convert indices to fish names
        sel = []
        for idx in selection_indices:
            if not isinstance(idx, int) or idx < 0 or idx >= len(player.roster):
                raise ValueError(f"Invalid index: {idx}")
            sel.append(player.roster[idx])
        
        return sel
    except:
        print("Invalid selection format. Using old prompt method.")
        # Fallback to original method
        print(f"{player.name}: choose 4 fish from the roster. Available: {', '.join(FISH_NAMES)}")
        sel = []
        while len(sel) < 4:
            choice = input(f"Select fish #{len(sel)+1}: ")
            if choice not in FISH_NAMES:
                print("Unknown fish. Try again.")
                continue
            if choice in sel:
                print("Already chosen.")
                continue
            sel.append(choice)
        return sel


def main() -> None:
    game = Game(("Player 1", "Player 2"))
    teams = []
    mimic_choices = []
    for i, player in enumerate(game.state.players):
        sel = prompt_select(game, i)
        mimic = None
        if "Mimic Fish" in sel:
            print("Available fish to imitate:")
            fish_list = [name for name in FISH_NAMES if name != "Mimic Fish"]
            for idx, fish_name in enumerate(fish_list):
                print(f"  {idx}: {fish_name}")
            mimic_idx = input("Which fish to imitate (enter index)? ")
            try:
                mimic = fish_list[int(mimic_idx)]
            except (ValueError, IndexError):
                print("Invalid index, using Archerfish as default")
                mimic = "Archerfish"
        game.select_team(i, sel, mimic_choice=mimic)
        teams.append(sel)
        mimic_choices.append(mimic)

    current = 0
    while game.round_over() is None:
        print()
        print(game.prompt_for_assertion(current))
        cmd = input("Command: ")
        if cmd.upper().startswith("ASSERT"):
            _, idx, *guess_parts = cmd.split()
            guess = " ".join(guess_parts)
            msg = game.perform_assertion(current, int(idx), guess)
            print(msg)
        elif cmd.upper().startswith("SKIP"):
            pass
        else:
            print("Invalid command during assertion. Skipping assertion.")

        print()
        print(game.prompt_for_action(current))
        cmd = input("Action: ")
        parts = cmd.split()
        if len(parts) < 3:
            print("Invalid action command.")
            continue
        _, fish_idx, act = parts[:3]
        target = int(parts[3]) if len(parts) > 3 else None
        msg = game.perform_action(current, int(fish_idx), act.upper(), target)
        print(msg)
        current = 1 - current

    winner = game.round_over()
    if winner is not None:
        print(f"Round finished! Winner: Player {winner + 1}")
    else:
        print("Round finished! No winner determined.")


if __name__ == "__main__":
    main()

