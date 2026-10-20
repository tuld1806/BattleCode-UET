"""Continuous-space fleet simulation with documented configurable balance defaults."""

import copy
import math
from collections import Counter
from engine.tick import TickEngine, finite


# HP, mass, maximum thrust, collision radius, ore build cost.
SHIPS = {"FLAGSHIP": (2000, 500., 10., 12., 0), "FIGHTER": (100, 20., 15., 4., 100),
         "MINER": (150, 50., 5., 6., 150), "TORPEDO_FRIGATE": (400, 150., 4., 8., 300)}


def distance(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


class StellarArmadaEngine(TickEngine):
    """Resolve thrust, bounded rotation, collisions, combat and ore economy per tick."""

    slug = "stellar-armada"
    entity_key = "ships"
    base_type = "FLAGSHIP"

    def __init__(self, seed=0, max_ticks=1200, collision_k=0.001, starting_ore=300, tick_seconds=0.1):
        if type(max_ticks) is not int or not 1 <= max_ticks <= 1200 or not finite(collision_k) or collision_k < 0 or not finite(tick_seconds) or tick_seconds <= 0 or type(starting_ore) is not int or starting_ore < 0:
            raise ValueError("Invalid simulation parameters")
        self.seed, self.max_ticks = seed, max_ticks
        self.collision_k, self.starting_ore, self.tick_seconds = collision_k, starting_ore, tick_seconds

    def ship(self, ident, kind, team, x, y):
        return dict(id=ident, type=kind, team=team, x=float(x), y=float(y), vx=0., vy=0.,
                    orientation=0. if team == 1 else math.pi, omega=0., hp=SHIPS[kind][0],
                    weapon_cooldown=0, ore=0)

    def get_initial_state(self, player1_id, player2_id):
        state = self.initial_metadata(player1_id, player2_id)
        state.update(ore_reserves={"1": self.starting_ore, "2": self.starting_ore}, ships=[],
                     torpedoes=[], asteroids=[dict(id="A-1", x=300., y=500., ore_remaining=800),
                                             dict(id="A-2", x=700., y=500., ore_remaining=800)])
        for team, x in [(1, 100), (2, 900)]:
            state["ships"].extend([self.ship(f"FLAGSHIP-{team}", "FLAGSHIP", team, x, 500),
                                   self.ship(f"MINER-{team}", "MINER", team, x, 530),
                                   self.ship(f"FIGHTER-{team}", "FIGHTER", team, x, 470)])
        return state

    def get_player_view(self, state, player_id):
        return copy.deepcopy(dict(tick=state["tick"], seed=state["seed"], team_id=player_id,
            time_left_ms=self.time_bank_ms, ore_reserves=state["ore_reserves"][str(player_id)],
            my_ships=[s for s in state["ships"] if s["team"] == player_id],
            enemy_ships=[{k: v for k, v in s.items() if k != "ore"} for s in state["ships"] if s["team"] != player_id],
            asteroids=state["asteroids"], torpedoes=state["torpedoes"]))

    def is_action_valid(self, state, player_id, action):
        if not isinstance(action, dict) or set(action) - {"ship_commands", "build_commands"} or not action:
            return False
        owned = {s["id"]: s for s in state["ships"] if s["team"] == player_id}
        for key in ("ship_commands", "build_commands"):
            commands = action.get(key, [])
            if not isinstance(commands, list) or len(commands) > len(owned):
                return False
            seen = set()
            for c in commands:
                if not isinstance(c, dict):
                    return False
                ident = c.get("ship_id" if key == "ship_commands" else "builder_id")
                if not isinstance(ident, str) or ident not in owned or ident in seen:
                    return False
                seen.add(ident)
                if key == "build_commands":
                    if owned[ident]["type"] != "FLAGSHIP" or c.get("build_type") not in ("MINER", "FIGHTER", "TORPEDO_FRIGATE"):
                        return False
                else:
                    if not finite(c.get("thrust", 0)) or not 0 <= c.get("thrust", 0) <= SHIPS[owned[ident]["type"]][2]:
                        return False
                    if "rotate_to" in c and not finite(c["rotate_to"]):
                        return False
                    if type(c.get("fire_weapon", False)) is not bool:
                        return False
                    if c.get("fire_weapon"):
                        pos = c.get("target_position")
                        if not isinstance(pos, dict) or not all(finite(pos.get(v)) and 0 <= pos[v] <= 1000 for v in ("x", "y")):
                            return False
        return True

    def resolve_tick(self, state, actions):
        commands = {c["ship_id"]: c for a in actions.values() for c in a.get("ship_commands", [])}
        ships, damage, events = state["ships"], Counter(), []
        for s in ships:
            cmd, stats = commands.get(s["id"], {}), SHIPS[s["type"]]
            target = cmd.get("rotate_to", s["orientation"])
            delta = (target - s["orientation"] + math.pi) % (2 * math.pi) - math.pi
            s["omega"] = max(-0.2, min(0.2, delta))
            s["orientation"] = (s["orientation"] + s["omega"]) % (2 * math.pi)
            thrust = cmd.get("thrust", 0)
            s["vx"] = s["vx"] * 0.98 + thrust * math.cos(s["orientation"]) / stats[1]
            s["vy"] = s["vy"] * 0.98 + thrust * math.sin(s["orientation"]) / stats[1]
            for axis in ("x", "y"):
                pos = s[axis] + s["v" + axis]
                s[axis] = max(0., min(1000., pos))
                if pos != s[axis]:
                    s["v" + axis] = 0.
            s["weapon_cooldown"] = max(0, s["weapon_cooldown"] - 1)
        for i, a in enumerate(ships):
            for b in ships[i + 1:]:
                if distance(a, b) < SHIPS[a["type"]][3] + SHIPS[b["type"]][3]:
                    speed2 = (a["vx"] - b["vx"]) ** 2 + (a["vy"] - b["vy"]) ** 2
                    damage[a["id"]] += self.collision_k * SHIPS[b["type"]][1] * speed2
                    damage[b["id"]] += self.collision_k * SHIPS[a["type"]][1] * speed2
                    events.append(dict(type="collision", ships=[a["id"], b["id"]]))
        for s in ships:
            cmd = commands.get(s["id"], {})
            if not cmd.get("fire_weapon") or s["weapon_cooldown"]:
                continue
            target = cmd["target_position"]
            if s["type"] == "FIGHTER" and distance(s, target) <= 80:
                candidates = [e for e in ships if e["team"] != s["team"] and distance(s, e) <= 80 and distance(e, target) <= SHIPS[e["type"]][3]]
                projectiles = [t for t in state["torpedoes"] if t["team"] != s["team"] and distance(s, t) <= 80 and distance(t, target) <= 4]
                if projectiles:
                    state["torpedoes"].remove(projectiles[0])
                    events.append(dict(type="intercept", ship_id=s["id"], torpedo_id=projectiles[0]["id"]))
                elif candidates:
                    victim = min(candidates, key=lambda e: (distance(e, target), e["id"]))
                    damage[victim["id"]] += 15
                    events.append(dict(type="laser", source=s["id"], target=victim["id"], damage=15))
            if s["type"] == "TORPEDO_FRIGATE" and distance(s, target) <= 300:
                angle = math.atan2(target["y"] - s["y"], target["x"] - s["x"])
                state["torpedoes"].append(dict(id=f"T-{state['next_id']}", team=s["team"], x=s["x"], y=s["y"], angle=angle, age=0, travelled=0.))
                state["next_id"] += 1
                s["weapon_cooldown"] = 10
        remaining = []
        for t in state["torpedoes"]:
            t["age"] += 1
            speed = 12. * min(1., t["age"] * self.tick_seconds / 0.5)
            old_x, old_y = t["x"], t["y"]
            dx, dy = speed * math.cos(t["angle"]), speed * math.sin(t["angle"])
            t["x"], t["y"] = old_x + dx, old_y + dy
            t["travelled"] += speed
            hits = []
            for s in ships:
                if s["team"] == t["team"]:
                    continue
                fraction = max(0., min(1., ((s["x"] - old_x) * dx + (s["y"] - old_y) * dy) / (speed * speed)))
                if math.hypot(s["x"] - old_x - fraction * dx, s["y"] - old_y - fraction * dy) <= SHIPS[s["type"]][3]:
                    hits.append((fraction, s["id"]))
            if hits:
                victim = min(hits)[1]
                damage[victim] += 80
                events.append(dict(type="torpedo_hit", target=victim, damage=80))
            elif t["travelled"] <= 300 and 0 <= t["x"] <= 1000 and 0 <= t["y"] <= 1000:
                remaining.append(t)
        state["torpedoes"] = remaining
        for s in ships:
            s["hp"] = max(0., s["hp"] - damage[s["id"]])
        state["ships"] = [s for s in ships if s["hp"] > 0]
        for s in state["ships"]:
            if s["type"] != "MINER":
                continue
            for asteroid in state["asteroids"]:
                if distance(s, asteroid) < 30:
                    amount = min(10, 100 - s["ore"], asteroid["ore_remaining"])
                    s["ore"] += amount
                    asteroid["ore_remaining"] -= amount
            if any(b["team"] == s["team"] and b["type"] == "FLAGSHIP" and distance(s, b) < 50 for b in state["ships"]):
                state["ore_reserves"][str(s["team"])] += s["ore"]
                s["ore"] = 0
        for team in (1, 2):
            for cmd in actions[str(team)].get("build_commands", []):
                base = next((s for s in state["ships"] if s["id"] == cmd["builder_id"]), None)
                kind, wallet = cmd["build_type"], str(team)
                if not base or state["ore_reserves"][wallet] < SHIPS[kind][4]:
                    continue
                positions = [(base["x"] + dx, base["y"] + dy) for dx, dy in ((0, 25), (25, 0), (0, -25), (-25, 0))]
                free = next(((x, y) for x, y in positions if 0 <= x <= 1000 and 0 <= y <= 1000 and
                             not any(distance(dict(x=x, y=y), s) < SHIPS[kind][3] + SHIPS[s["type"]][3] for s in state["ships"])), None)
                if free is None:
                    continue
                x, y = free
                state["ore_reserves"][wallet] -= SHIPS[kind][4]
                state["ships"].append(self.ship(f"S-{state['next_id']}", kind, team, x, y))
                state["next_id"] += 1
        state["events"] = events

    def score_for_tiebreak(self, state, player_id):
        return sum(s["hp"] for s in state["ships"] if s["team"] == player_id) + state["ore_reserves"][str(player_id)] / 10
