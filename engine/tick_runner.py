"""JSON bot execution, CPU time banks and versioned full-state tick replays."""

import copy
from datetime import datetime, timezone
from pathlib import Path
import uuid
from engine.runner import BotProcess
from engine.sandbox import validate_bot_source


def run_tick_match(bot1_path, bot2_path, engine, player1_info=None, player2_info=None):
    """Execute both bot observations before resolving each simultaneous game tick."""
    state = engine.get_initial_state(1, 2)
    workers, bank, errors = {}, {1: float(engine.time_bank_ms), 2: float(engine.time_bank_ms)}, {}
    frames = []

    def snapshot():
        return copy.deepcopy({k: v for k, v in state.items() if k not in ("pending", "turn", "move_no")})

    frames.append(snapshot())
    winner, reason = None, ""
    try:
        for team, path in [(1, bot1_path), (2, bot2_path)]:
            valid, error = validate_bot_source(Path(path).read_text(encoding="utf-8"), entrypoint="get_action")
            if not valid:
                winner, reason, errors[team] = 3 - team, "invalid_bot", error
                break
            worker = BotProcess(path, timeout=2.05, protocol="json_state")
            workers[team] = worker
            ok, error, failure = worker.start()
            if not ok:
                winner, reason, errors[team] = 3 - team, failure, error
                break
        while not reason:
            winner, reason = engine.check_winner(state)
            if reason:
                break
            observations = {team: engine.get_player_view(state, team) for team in (1, 2)}
            commands = {}
            for team in (1, 2):
                observations[team]["time_left_ms"] = bank[team]
                ok, action, error, failure = workers[team].request_move(observations[team], team, [],
                    timeout=(engine.timeout_ms + bank[team]) / 1000 + 0.25)
                if not ok:
                    winner, reason, errors[team] = 3 - team, failure, error
                    break
                bank[team] -= max(0., workers[team].last_cpu_ms - engine.timeout_ms)
                if bank[team] < 0:
                    winner, reason, errors[team] = 3 - team, "timeout", "CPU time bank exhausted"
                    break
                try:
                    valid = engine.is_action_valid(state, team, action)
                except (TypeError, ValueError, KeyError):
                    valid = False
                if not valid:
                    winner, reason, errors[team] = 3 - team, "invalid_move", "Invalid JSON commands"
                    break
                commands[team] = action
            if reason:
                break
            for team in (1, 2):
                state = engine.apply_action(state, team, commands[team])
            frame = snapshot()
            frame["actions"] = commands
            frame["time_bank_ms"] = dict(bank)
            frames.append(frame)
    finally:
        for worker in workers.values():
            worker.kill()
    return dict(replay_version=2, game_slug=engine.slug, seed=engine.seed,
        match_id=(player1_info or {}).get("match_id", uuid.uuid4().hex),
        player1=player1_info or {"id": 1, "username": Path(bot1_path).stem},
        player2=player2_info or {"id": 2, "username": Path(bot2_path).stem},
        winner=winner, win_reason=reason, total_turns=state["tick"], total_ticks=state["tick"],
        moves=[], initial_board=[], frames=frames, bot1_error=errors.get(1), bot2_error=errors.get(2),
        limits={"cpu_ms_per_tick": engine.timeout_ms, "time_bank_ms": engine.time_bank_ms, "memory_limit_mb": engine.memory_limit_mb},
        created_at=datetime.now(timezone.utc).isoformat())
