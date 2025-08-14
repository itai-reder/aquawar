"""Interactive demo for the Aquawar engine.

Run ``python -m aquawar_game.demo`` to play a small two-player match from the
command line.  The interface mirrors the text prompts that LLM agents would
receive when controlling a player.
"""

from __future__ import annotations

import sys
from typing import List

from .game import Game, FISH_NAMES


def prompt_select(player: str) -> List[str]:
    print(f"{player}: choose 4 fish from the roster. Available: {', '.join(FISH_NAMES)}")
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
        sel = prompt_select(player.name)
        mimic = None
        if "Mimic Fish" in sel:
            mimic = input("Mimic Fish selected. Which fish to imitate? ")
        game.select_team(i, sel, mimic_choice=mimic)
        teams.append(sel)
        mimic_choices.append(mimic)

    current = 0
    while game.round_over() is None:
        print()
        print(game.prompt_for_player(current))
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
    print(f"Round finished! Winner: Player {winner+1}")


if __name__ == "__main__":
    main()

