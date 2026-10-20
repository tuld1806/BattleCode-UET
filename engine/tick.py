"""Shared simultaneous-tick contract for JSON-command game plugins."""

import copy
import math
from engine.base import GameEngine


def finite(value):
    """Reject booleans and non-finite numbers at the bot trust boundary."""
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


class TickEngine(GameEngine):
    """Collect both teams' commands before advancing a deterministic simulation."""

    bot_interface = "json_state"
    timeout_ms = 50
    time_bank_ms = 2000
    memory_limit_mb = 256

    def apply_action(self, state, player_id, action):
        if self.check_winner(state)[1] or player_id != state["turn"]:
            raise ValueError("Game has ended or this team cannot submit now")
        if not self.is_action_valid(state, player_id, action):
            raise ValueError("Invalid command payload")
        result = copy.deepcopy(state)
        result["pending"][str(player_id)] = copy.deepcopy(action)
        if len(result["pending"]) == 2:
            self.resolve_tick(result, result["pending"])
            result["pending"] = {}
            result["tick"] += 1
            result["move_no"] = result["tick"] + 1
            result["turn"] = 1
        else:
            result["turn"] = 2
        return result

    def check_winner(self, state):
        alive = {team: any(e["team"] == team and e["type"] == self.base_type and e["hp"] > 0
                           for e in state[self.entity_key]) for team in (1, 2)}
        if not all(alive.values()):
            return (1 if alive[1] else 2 if alive[2] else None), ("base_destroyed" if any(alive.values()) else "draw")
        if state["tick"] >= self.get_max_turns():
            scores = [self.score_for_tiebreak(state, team) for team in (1, 2)]
            return (1 if scores[0] > scores[1] else 2 if scores[1] > scores[0] else None), "max_ticks"
        return None, ""

    def get_max_turns(self):
        return self.max_ticks

    def initial_metadata(self, player1_id, player2_id):
        return {"tick": 0, "move_no": 1, "turn": 1, "pending": {}, "seed": self.seed,
                "player1_id": player1_id, "player2_id": player2_id, "events": [], "next_id": 100}

    def resolve_tick(self, state, actions):
        raise NotImplementedError
