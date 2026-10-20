"""Deterministic simultaneous grid conquest; configurable defaults fill rulebook gaps."""

import copy
import random
from collections import Counter
from engine.tick import TickEngine


STATS = {"WORKER": (50, 5, 1, 5, 50), "PAWN": (120, 25, 1, 3, 100),
         "BLASTER": (80, 35, 3, 4, 150), "TOWER": (300, 40, 4, 4, 200)}
DIRECTIONS = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}


class CyberGridEngine(TickEngine):
    """Grid movement, simultaneous combat, visibility, spawning and node economy."""

    slug = "cyber-grid"
    entity_key = "units"
    base_type = "CORE"

    def __init__(self, map_size=32, seed=0, max_ticks=1000, core_hp=1000, starting_data=200):
        if type(map_size) is not int or not 32 <= map_size <= 64:
            raise ValueError("Map size must be an integer between 32 and 64")
        if type(max_ticks) is not int or not 1 <= max_ticks <= 1000 or type(core_hp) is not int or core_hp <= 0 or type(starting_data) is not int or starting_data < 0:
            raise ValueError("Invalid tick cap, core health or starting resources")
        self.map_size, self.seed, self.max_ticks = map_size, seed, max_ticks
        self.core_hp, self.starting_data = core_hp, starting_data

    def get_initial_state(self, player1_id, player2_id):
        n = self.map_size
        rng = random.Random(self.seed)
        state = self.initial_metadata(player1_id, player2_id)
        units = []
        for team, x, y in [(1, 1, 1), (2, n - 2, n - 2)]:
            units.extend([dict(id=team * 10, type="CORE", team=team, hp=self.core_hp, x=x, y=y),
                          dict(id=team * 10 + 1, type="WORKER", team=team, hp=50, x=x + (1 if team == 1 else -1), y=y)])
        nodes = [{"x": n // 4, "y": n // 4, "occupied_by_team": 0},
                 {"x": n - 1 - n // 4, "y": n - 1 - n // 4, "occupied_by_team": 0}]
        protected = {(u["x"] + dx, u["y"] + dy) for u in units for dx in range(-2, 3) for dy in range(-2, 3)}
        protected.update((p["x"], p["y"]) for p in nodes)
        obstacles = set()
        for _ in range(n * n // 30):
            x, y = rng.randrange(n), rng.randrange(n)
            for pos in [(x, y), (n - 1 - x, n - 1 - y)]:
                if pos not in protected:
                    obstacles.add(pos)
        state.update(map_size=n, units=units, nodes=nodes, obstacles=sorted(obstacles),
                     resources={"1": self.starting_data, "2": self.starting_data})
        return state

    def visible_cells(self, state, team):
        visible = set()
        for u in state["units"]:
            if u["team"] != team:
                continue
            radius = STATS[u["type"]][3] if u["type"] in STATS else 5
            for x in range(max(0, u["x"] - radius), min(self.map_size, u["x"] + radius + 1)):
                for y in range(max(0, u["y"] - radius), min(self.map_size, u["y"] + radius + 1)):
                    visible.add((x, y))
        return visible

    def get_player_view(self, state, player_id):
        visible = self.visible_cells(state, player_id)
        return copy.deepcopy({"tick": state["tick"], "seed": state["seed"], "team_id": player_id,
            "time_left_ms": self.time_bank_ms, "resources": state["resources"][str(player_id)],
            "map_size": self.map_size, "units": [u for u in state["units"] if (u["x"], u["y"]) in visible],
            "visible_nodes": [u for u in state["nodes"] if (u["x"], u["y"]) in visible],
            "obstacles": [p for p in state["obstacles"] if tuple(p) in visible], "visible_cells": sorted(visible)})

    def is_action_valid(self, state, player_id, action):
        if not isinstance(action, dict) or set(action) != {"commands"} or not isinstance(action["commands"], list):
            return False
        owned = {u["id"]: u for u in state["units"] if u["team"] == player_id}
        visible = {u["id"] for u in self.get_player_view(state, player_id)["units"]}
        seen = set()
        if len(action["commands"]) > 3 * len(owned):
            return False
        for cmd in action["commands"]:
            if not isinstance(cmd, dict) or type(cmd.get("unit_id")) is not int:
                return False
            uid, kind = cmd["unit_id"], cmd.get("action")
            if uid not in owned or kind not in ("MOVE", "ATTACK", "SPAWN", "WAIT"):
                return False
            if (uid, kind) in seen:
                return False
            seen.add((uid, kind))
            unit = owned[uid]
            if kind == "MOVE" and (unit["type"] in ("CORE", "TOWER") or not isinstance(cmd.get("direction"), str) or cmd["direction"] not in DIRECTIONS):
                return False
            if kind == "ATTACK" and (type(cmd.get("target_id")) is not int or cmd["target_id"] not in visible):
                return False
            if kind == "SPAWN" and (unit["type"] not in ("CORE", "WORKER") or not isinstance(cmd.get("unit_type"), str) or cmd["unit_type"] not in STATS or not isinstance(cmd.get("direction"), str) or cmd["direction"] not in DIRECTIONS):
                return False
        return True

    def clear_shot(self, state, a, b):
        # Sample the segment on grid cells; obstacles occlude ranged attacks.
        dx, dy = b["x"] - a["x"], b["y"] - a["y"]
        steps = max(abs(dx), abs(dy))
        blocked = {tuple(p) for p in state["obstacles"]}
        return all((round(a["x"] + dx * i / steps), round(a["y"] + dy * i / steps)) not in blocked for i in range(1, steps))

    def resolve_tick(self, state, actions):
        units = {u["id"]: u for u in state["units"]}
        commands = [c for team in (1, 2) for c in actions[str(team)]["commands"]]
        obstacles = {tuple(p) for p in state["obstacles"]}
        proposals = {uid: (u["x"], u["y"]) for uid, u in units.items()}
        events, damage = [], Counter()
        for c in commands:
            if c["action"] == "MOVE":
                u = units[c["unit_id"]]
                dx, dy = DIRECTIONS[c["direction"]]
                pos = (u["x"] + dx, u["y"] + dy)
                if all(0 <= v < self.map_size for v in pos) and pos not in obstacles:
                    proposals[u["id"]] = pos
        counts = Counter(proposals.values())
        # Rejected movements become occupied cells, so resolve blocking to a fixed point.
        blocked = {uid for uid, pos in proposals.items() if counts[pos] > 1}
        for uid in blocked:
            damage[uid] += 10
            events.append({"type": "collision", "unit_id": uid})
        changed = True
        while changed:
            changed = False
            occupied = {(units[uid]["x"], units[uid]["y"]) for uid in blocked}
            for uid, pos in proposals.items():
                if uid not in blocked and pos in occupied:
                    blocked.add(uid)
                    changed = True
        for uid, pos in proposals.items():
            if uid not in blocked:
                units[uid]["x"], units[uid]["y"] = pos
        for c in commands:
            u = units[c["unit_id"]]
            if c["action"] == "ATTACK":
                target = units.get(c["target_id"])
                stats = STATS.get(u["type"])
                if target and stats and target["team"] != u["team"] and max(abs(u["x"] - target["x"]), abs(u["y"] - target["y"])) <= stats[2] and self.clear_shot(state, u, target):
                    damage[target["id"]] += stats[1]
                    events.append({"type": "attack", "source": u["id"], "target": target["id"], "damage": stats[1]})
        for uid, amount in damage.items():
            units[uid]["hp"] -= amount
        state["units"] = [u for u in units.values() if u["hp"] > 0]
        occupied = {(u["x"], u["y"]) for u in state["units"]}
        for c in commands:
            if c["action"] != "SPAWN" or units[c["unit_id"]]["hp"] <= 0:
                continue
            u, kind = units[c["unit_id"]], c["unit_type"]
            dx, dy = DIRECTIONS[c["direction"]]
            pos, team = (u["x"] + dx, u["y"] + dy), str(u["team"])
            if pos in occupied or pos in obstacles or not all(0 <= v < self.map_size for v in pos) or state["resources"][team] < STATS[kind][4]:
                continue
            state["resources"][team] -= STATS[kind][4]
            state["units"].append(dict(id=state["next_id"], type=kind, hp=STATS[kind][0], team=u["team"], x=pos[0], y=pos[1]))
            state["next_id"] += 1
            occupied.add(pos)
        for node in state["nodes"]:
            for u in state["units"]:
                if u["type"] == "WORKER" and (u["x"], u["y"]) == (node["x"], node["y"]):
                    node["occupied_by_team"] = u["team"]
        for team in (1, 2):
            core_alive = any(u["type"] == "CORE" and u["team"] == team for u in state["units"])
            state["resources"][str(team)] += 10 * core_alive + 5 * sum(n["occupied_by_team"] == team for n in state["nodes"])
        state["events"] = events

    def score_for_tiebreak(self, state, player_id):
        return 100 * sum(n["occupied_by_team"] == player_id for n in state["nodes"]) + sum(u["hp"] for u in state["units"] if u["team"] == player_id and u["type"] != "CORE") + state["resources"][str(player_id)] / 10
