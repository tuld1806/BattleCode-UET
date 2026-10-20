"""Rulebook behavior, malformed-input boundaries and real subprocess integration."""

import copy
import json
import math
from pathlib import Path
import pytest
from games.cyber_grid.engine import CyberGridEngine
from games.stellar_armada.engine import StellarArmadaEngine
from engine.runner import run_match


def tick(engine, state, a=None, b=None):
    empty = {"commands": []} if engine.slug == "cyber-grid" else {"ship_commands": [], "build_commands": []}
    state = engine.apply_action(state, 1, a or empty)
    return engine.apply_action(state, 2, b or empty)


@pytest.mark.parametrize("cls", [CyberGridEngine, StellarArmadaEngine])
def test_seeded_simulation_and_input_immutability(cls):
    engine = cls(seed=42, max_ticks=3)
    a, b = engine.get_initial_state(101, 202), engine.get_initial_state(101, 202)
    original = copy.deepcopy(a)
    for _ in range(3):
        a, b = tick(engine, a), tick(engine, b)
        assert a == b
    assert original["tick"] == 0
    assert a["tick"] == 3
    assert engine.check_winner(a) == (None, "max_ticks")
    json.dumps(a, allow_nan=False)
    with pytest.raises(ValueError):
        tick(engine, a)


def test_grid_pending_commands_never_leak_or_advance_one_sided():
    e = CyberGridEngine()
    state = e.get_initial_state(1, 2)
    first = e.apply_action(state, 1, {"commands": [{"unit_id": 11, "action": "MOVE", "direction": "SOUTH"}]})
    assert first["tick"] == 0
    assert first["units"] == state["units"]
    view = e.get_player_view(first, 2)
    assert "pending" not in view and "resources" in view
    assert all(u["team"] == 2 for u in view["units"])
    view["units"][0]["hp"] = 0
    assert first["units"][-2]["hp"] > 0


def test_grid_same_destination_collision():
    e = CyberGridEngine()
    s = e.get_initial_state(1, 2)
    s["obstacles"] = []
    a, b = s["units"][1], s["units"][3]
    a.update(x=5, y=5)
    b.update(x=7, y=5)
    s = tick(e, s, {"commands": [{"unit_id": 11, "action": "MOVE", "direction": "EAST"}]},
             {"commands": [{"unit_id": 21, "action": "MOVE", "direction": "WEST"}]})
    assert [(s["units"][i]["x"], s["units"][i]["hp"]) for i in (1, 3)] == [(5, 40), (7, 40)]


def test_grid_simultaneous_kills_and_obstacle_occlusion():
    e = CyberGridEngine()
    s = e.get_initial_state(1, 2)
    a, b = s["units"][1], s["units"][3]
    a.update(type="BLASTER", hp=35, x=5, y=5)
    b.update(type="BLASTER", hp=35, x=7, y=5)
    actions = ({"commands": [{"unit_id": 11, "action": "ATTACK", "target_id": 21}]},
               {"commands": [{"unit_id": 21, "action": "ATTACK", "target_id": 11}]})
    s["obstacles"] = [(6, 5)]
    blocked = tick(e, s, *actions)
    assert len(blocked["units"]) == 4
    s["obstacles"] = []
    killed = tick(e, s, *actions)
    assert {u["type"] for u in killed["units"]} == {"CORE"}


def test_grid_capture_income_spawn_and_score():
    e = CyberGridEngine()
    s = e.get_initial_state(1, 2)
    s["obstacles"] = []
    s["nodes"][0].update(x=2, y=1)
    result = tick(e, s, {"commands": [{"unit_id": 10, "action": "SPAWN", "unit_type": "TOWER", "direction": "SOUTH"}]})
    assert result["resources"]["1"] == 15
    assert result["nodes"][0]["occupied_by_team"] == 1
    assert any(u["type"] == "TOWER" for u in result["units"])
    assert e.score_for_tiebreak(result, 1) == 451.5


@pytest.mark.parametrize("action", [None, [], {"commands": {}}, {"commands": [{"unit_id": True, "action": "WAIT"}]},
    {"commands": [{"unit_id": 21, "action": "WAIT"}]}, {"commands": [{"unit_id": 11, "action": "MOVE", "direction": "UP"}]}])
def test_grid_invalid_commands(action):
    e = CyberGridEngine()
    assert not e.is_action_valid(e.get_initial_state(1, 2), 1, action)


def test_stellar_thrust_drag_and_no_one_sided_physics():
    e = StellarArmadaEngine()
    s = e.get_initial_state(1, 2)
    action = {"ship_commands": [{"ship_id": "FIGHTER-1", "thrust": 15}]}
    pending = e.apply_action(s, 1, action)
    assert pending["ships"] == s["ships"]
    moved = e.apply_action(pending, 2, {"ship_commands": []})
    fighter = next(s for s in moved["ships"] if s["id"] == "FIGHTER-1")
    assert fighter["vx"] == pytest.approx(.75)
    assert fighter["x"] == pytest.approx(100.75)
    moved = tick(e, moved)
    assert next(s for s in moved["ships"] if s["id"] == "FIGHTER-1")["vx"] == pytest.approx(.735)


def test_stellar_mutual_laser_kills():
    e = StellarArmadaEngine()
    s = e.get_initial_state(1, 2)
    fighters = [s for s in s["ships"] if s["type"] == "FIGHTER"]
    for ship, x in zip(fighters, [400., 450.]):
        ship.update(x=x, hp=15)
    s = tick(e, s, {"ship_commands": [{"ship_id": "FIGHTER-1", "fire_weapon": True, "target_position": {"x": 450, "y": 470}}]},
             {"ship_commands": [{"ship_id": "FIGHTER-2", "fire_weapon": True, "target_position": {"x": 400, "y": 470}}]})
    assert all(s["type"] != "FIGHTER" for s in s["ships"])


def test_stellar_mining_capacity_deposit_build():
    e = StellarArmadaEngine()
    s = e.get_initial_state(1, 2)
    miner = next(ship for ship in s["ships"] if ship["id"] == "MINER-1")
    miner.update(x=300, y=500, ore=95)
    s = tick(e, s)
    miner = next(ship for ship in s["ships"] if ship["id"] == "MINER-1")
    assert miner["ore"] == 100 and s["asteroids"][0]["ore_remaining"] == 795
    miner.update(x=100, y=530)
    s = tick(e, s, {"build_commands": [{"builder_id": "FLAGSHIP-1", "build_type": "FIGHTER"}]})
    assert s["ore_reserves"]["1"] == 300  # Deposit 100, spend 100.
    assert len(s["ships"]) == 7


def test_stellar_torpedo_accelerates_and_intercepts():
    e = StellarArmadaEngine()
    s = e.get_initial_state(1, 2)
    s["ships"].append(e.ship("FRIGATE", "TORPEDO_FRIGATE", 1, 400, 470))
    enemy = next(ship for ship in s["ships"] if ship["id"] == "FIGHTER-2")
    enemy.update(x=430, y=470)
    s = tick(e, s, {"ship_commands": [{"ship_id": "FRIGATE", "fire_weapon": True, "target_position": {"x": 430, "y": 470}}]})
    assert s["torpedoes"][0]["x"] == pytest.approx(402.4)
    s = tick(e, s, b={"ship_commands": [{"ship_id": "FIGHTER-2", "fire_weapon": True, "target_position": {"x": 402.4, "y": 470}}]})
    assert not s["torpedoes"]
    assert any(event["type"] == "intercept" for event in s["events"])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "15", -1, 16])
def test_stellar_rejects_invalid_thrust(bad):
    e = StellarArmadaEngine()
    assert not e.is_action_valid(e.get_initial_state(1, 2), 1, {"ship_commands": [{"ship_id": "FIGHTER-1", "thrust": bad}]})


@pytest.mark.parametrize("cls,source", [(CyberGridEngine, "return {'commands': []}"),
                                        (StellarArmadaEngine, "return {'ship_commands': []}")])
def test_real_json_subprocess_match_and_replay(cls, source, tmp_path):
    bot = tmp_path / "bot.py"
    bot.write_text("def get_action(state):\n    " + source + "\n", encoding="utf-8")
    result = run_match(str(bot), str(bot), engine=cls(max_ticks=2))
    assert result["win_reason"] == "max_ticks", result
    assert result["total_ticks"] == 2 and len(result["frames"]) == 3
    assert "pending" not in result["frames"][-1]
    assert result["replay_version"] == 2
    json.dumps(result, allow_nan=False)


def test_real_json_bot_invalid_action_forfeits(tmp_path):
    bad, good = tmp_path / "bad.py", tmp_path / "good.py"
    bad.write_text("def get_action(state):\n    return {'commands': [{'unit_id': 21, 'action': 'WAIT'}]}\n")
    good.write_text("def get_action(state):\n    return {'commands': []}\n")
    result = run_match(str(bad), str(good), engine=CyberGridEngine(max_ticks=2))
    assert result["winner"] == 2 and result["win_reason"] == "invalid_move"


def test_registry_loads_both_builtin_games():
    from server.game_registry import GameRegistry
    registry = GameRegistry()
    assert registry.load_engine("cyber-grid").slug == "cyber-grid"
    assert registry.load_engine("stellar-armada").slug == "stellar-armada"


def test_worker_memory_ceiling_and_wall_watchdog(tmp_path):
    good, memory, spin = [tmp_path / name for name in ("idle.py", "memory.py", "spin.py")]
    good.write_text("def get_action(state):\n    return {'commands': []}\n")
    memory.write_text("def get_action(state):\n    data = bytearray(400 * 1024 * 1024)\n    return {'commands': []}\n")
    spin.write_text("def get_action(state):\n    while True:\n        pass\n")
    limited = run_match(str(memory), str(good), engine=CyberGridEngine(max_ticks=1))
    assert limited["winner"] == 2 and limited["win_reason"] == "error"
    timed = run_match(str(spin), str(good), engine=CyberGridEngine(max_ticks=1))
    assert timed["winner"] == 2 and timed["win_reason"] == "timeout"


def test_json_bot_rng_is_seeded_repeatably(tmp_path):
    bot = tmp_path / "random.py"
    bot.write_text("import random\ndef get_action(state):\n    return {'commands': [{'unit_id': state['team_id'] * 10 + 1, 'action': 'WAIT', 'sample': random.random()}]}\n")
    a = run_match(str(bot), str(bot), engine=CyberGridEngine(max_ticks=2, seed=17))
    b = run_match(str(bot), str(bot), engine=CyberGridEngine(max_ticks=2, seed=17))
    assert a["win_reason"] == b["win_reason"] == "max_ticks"
    assert [f.get("actions") for f in a["frames"]] == [f.get("actions") for f in b["frames"]]
