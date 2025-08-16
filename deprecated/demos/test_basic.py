import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import aquawar_game as ag
from aquawar_game.fish import MAX_HP


def test_game_setup_and_assertion():
    g = ag.Game(("A", "B"))
    g.select_team(0, ["Archerfish", "Pufferfish", "Sea Wolf", "Mimic Fish"], mimic_choice="Octopus")
    g.select_team(1, ["Clownfish", "Sea Turtle", "Great White Shark", "Manta Ray"])

    prompt = g.prompt_for_player(0)
    assert "Your team" in prompt
    msg = g.perform_assertion(0, 0, "Clownfish")
    assert "success" in msg
    enemy_hp = g.state.players[1].team.fish[0].hp
    assert enemy_hp == MAX_HP - 50

