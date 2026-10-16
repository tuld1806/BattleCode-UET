"""Independent Boss Arena Simulation and System Verification Session.

Executes an isolated end-to-end round-robin benchmark tournament between all
five graduated benchmark boss bots from server/bosses/:
1. Level 1: Novice (novice_bot.py)
2. Level 2: Rusher (rusher_bot.py)
3. Level 3: Sentinel (sentinel_bot.py)
4. Level 4: Tactician (tactician_bot.py)
5. Level 5: Apex Master (apex_bot.py)

Validates:
- Subprocess isolation with strict 1.0s timeout per turn.
- Zero timeouts (win_reason != 'timeout').
- Zero runtime crashes / exceptions (win_reason != 'error').
- Zero illegal moves (win_reason != 'invalid_move').
- Replay artifact persistence and standardized JSON schema validation.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

# Ensure project root is present in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.runner import run_match, save_replay
from server.bosses import BOSS_REGISTRY, get_all_bosses


def validate_replay_schema(replay_data: dict[str, Any]) -> None:
    """Validate that the match replay matches the expected schema.

    Args:
        replay_data: Dictionary parsed from replay JSON file.

    Raises:
        ValueError: If any required key or format constraint is violated.
    """
    required_keys = [
        "match_id",
        "player1",
        "player2",
        "winner",
        "win_reason",
        "total_turns",
        "moves",
        "bot1_error",
        "bot2_error",
        "initial_board",
        "created_at",
    ]
    for key in required_keys:
        if key not in replay_data:
            raise ValueError(f"Missing required key in replay JSON: {key}")

    if not isinstance(replay_data["match_id"], str) or not replay_data["match_id"]:
        raise ValueError("Invalid match_id format in replay JSON")

    if not isinstance(replay_data["player1"], dict) or not isinstance(replay_data["player2"], dict):
        raise ValueError("Player metadata must be dictionaries in replay JSON")

    if replay_data["winner"] not in (1, 2, None):
        raise ValueError(f"Invalid winner value: {replay_data['winner']}")

    valid_reasons = {"goal", "wipeout", "max_turns", "timeout", "error", "invalid_move"}
    if replay_data["win_reason"] not in valid_reasons:
        raise ValueError(f"Invalid win_reason: {replay_data['win_reason']}")

    if not isinstance(replay_data["total_turns"], int) or replay_data["total_turns"] < 0:
        raise ValueError(f"Invalid total_turns value: {replay_data['total_turns']}")

    moves = replay_data["moves"]
    if not isinstance(moves, list) or len(moves) != replay_data["total_turns"]:
        raise ValueError("Moves list length does not match total_turns")

    for idx, move in enumerate(moves):
        move_keys = ["turn", "player", "from", "to", "piece", "captured", "san"]
        for mk in move_keys:
            if mk not in move:
                raise ValueError(f"Move #{idx} missing required field: {mk}")
        if move["player"] not in (1, 2):
            raise ValueError(f"Invalid player in move #{idx}: {move['player']}")

    initial_board = replay_data["initial_board"]
    if not isinstance(initial_board, list) or len(initial_board) != 9:
        raise ValueError("initial_board must be a 9-row matrix")
    for row in initial_board:
        if not isinstance(row, list) or len(row) != 9:
            raise ValueError("Every row in initial_board must contain 9 squares")


def run_simulation(max_turns_per_match: int = 60, timeout_per_turn: float = 1.0) -> int:
    """Execute round-robin simulation between all 5 graduated boss tiers.

    Args:
        max_turns_per_match: Turn limit for each match before draw/tiebreaker.
        timeout_per_turn: Per-turn subprocess execution timeout in seconds.

    Returns:
        0 on complete success, 1 if any failure occurs.
    """
    bosses = get_all_bosses()
    if len(bosses) != 5:
        print(f"Error: expected 5 boss bots in registry, found {len(bosses)}")
        return 1

    # Verify all boss files exist on disk
    for boss in bosses:
        bot_file = Path(boss["file_path"])
        if not bot_file.is_file():
            print(f"Error: boss script does not exist: {bot_file}")
            return 1

    # Generate 10 round-robin pairings across the 5 bosses
    pairings = list(itertools.combinations(bosses, 2))
    print("=" * 84)
    print("INDEPENDENT BOSS ARENA SIMULATION SESSION")
    print(f"Boss Tiers: {len(bosses)} | Total Matches: {len(pairings)} | Turn Timeout: {timeout_per_turn}s | Max Turns: {max_turns_per_match}")
    print("=" * 84)

    results_table: list[dict[str, Any]] = []
    temp_dir = tempfile.TemporaryDirectory()
    replays_dir = Path(temp_dir.name) / "replays"
    replays_dir.mkdir(parents=True, exist_ok=True)

    disallowed_win_reasons = {"timeout", "error", "invalid_move"}
    failure_count = 0

    try:
        match_idx = 1
        for boss1, boss2 in pairings:
            p1_name = f"L{boss1['level']} {boss1['name']}"
            p2_name = f"L{boss2['level']} {boss2['name']}"

            p1_meta = {
                "id": boss1["level"],
                "username": boss1["name"],
                "bot_name": boss1["name"],
                "level": boss1["level"],
            }
            p2_meta = {
                "id": boss2["level"],
                "username": boss2["name"],
                "bot_name": boss2["name"],
                "level": boss2["level"],
            }

            t0 = time.perf_counter()
            match_res = run_match(
                bot1_path=boss1["file_path"],
                bot2_path=boss2["file_path"],
                max_turns=max_turns_per_match,
                timeout_per_turn=timeout_per_turn,
                player1_info=p1_meta,
                player2_info=p2_meta,
            )
            elapsed = time.perf_counter() - t0

            winner_code = match_res.get("winner")
            win_reason = match_res.get("win_reason", "unknown")
            turns = match_res.get("total_turns", 0)

            if winner_code == 1:
                winner_str = p1_name
            elif winner_code == 2:
                winner_str = p2_name
            else:
                winner_str = "Draw"

            # Check for disallowed failure reasons
            has_error = False
            error_details = []
            if win_reason in disallowed_win_reasons:
                has_error = True
                error_details.append(f"Disallowed win reason: {win_reason}")

            if match_res.get("bot1_error"):
                has_error = True
                error_details.append(f"Bot 1 error: {match_res['bot1_error']}")

            if match_res.get("bot2_error"):
                has_error = True
                error_details.append(f"Bot 2 error: {match_res['bot2_error']}")

            # Save and validate replay schema
            replay_filename = f"sim_match_{match_idx:02d}_{boss1['slug']}_vs_{boss2['slug']}.json"
            replay_file = replays_dir / replay_filename
            try:
                save_replay(match_res, replay_file)
                with open(replay_file, "r", encoding="utf-8") as f:
                    loaded_replay = json.load(f)
                validate_replay_schema(loaded_replay)
                schema_valid = True
            except Exception as exc:
                has_error = True
                schema_valid = False
                error_details.append(f"Replay schema validation failed: {exc}")

            if has_error:
                failure_count += 1

            results_table.append(
                {
                    "idx": match_idx,
                    "p1": p1_name,
                    "p2": p2_name,
                    "winner": winner_str,
                    "reason": win_reason,
                    "turns": turns,
                    "elapsed": elapsed,
                    "passed": not has_error,
                    "errors": error_details,
                }
            )
            match_idx += 1

        # Render formatted terminal summary table
        print(f"{'#':<3} | {'Player 1 (White)':<20} | {'Player 2 (Black)':<20} | {'Winner':<20} | {'Reason':<10} | {'Turns':<5} | {'Time (s)':<8} | {'Status'}")
        print("-" * 115)
        for r in results_table:
            status_str = "PASS" if r["passed"] else "FAIL"
            print(
                f"{r['idx']:<3} | {r['p1']:<20} | {r['p2']:<20} | {r['winner']:<20} | {r['reason']:<10} | {r['turns']:<5} | {r['elapsed']:<8.2f} | {status_str}"
            )
            if r["errors"]:
                for err in r["errors"]:
                    print(f"    --> ERROR: {err}")

        print("=" * 115)
        total_matches = len(results_table)
        passed_matches = total_matches - failure_count

        print(f"Simulation Summary: {passed_matches}/{total_matches} matches passed successfully.")
        print(f"Zero Timeouts Confirmed: {all(r['reason'] != 'timeout' for r in results_table)}")
        print(f"Zero Process Crashes Confirmed: {all(r['reason'] != 'error' for r in results_table)}")
        print(f"Zero Illegal Moves Confirmed: {all(r['reason'] != 'invalid_move' for r in results_table)}")
        print(f"Replay Schemas Validated: {all(r['passed'] for r in results_table)}")

        if failure_count > 0:
            print(f"FAILURE: {failure_count} match(es) encountered disallowed conditions.")
            return 1

        print("ALL 10 MATCHES CONCLUDED CLEANLY. EXIT CODE 0.")
        return 0

    finally:
        temp_dir.cleanup()


if __name__ == "__main__":
    exit_code = run_simulation()
    sys.exit(exit_code)
