"""Unit and integration tests for isolated subprocess match runner and replay generator."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from engine.runner import run_match, save_replay

STARTER_KIT_DIR = Path(__file__).resolve().parent.parent / "starter_kit"
BOT_TEMPLATE_PATH = str(STARTER_KIT_DIR / "bot_template.py")
HEURISTIC_BOT_PATH = str(STARTER_KIT_DIR / "heuristic_bot.py")


def test_runner_valid_match() -> None:
    """Verify standard match simulation runs properly between two valid bots."""
    res = run_match(
        BOT_TEMPLATE_PATH,
        HEURISTIC_BOT_PATH,
        max_turns=30,
        timeout_per_turn=1.0,
    )
    assert res["winner"] in (1, 2, None)
    assert res["win_reason"] in ("goal", "wipeout", "max_turns")
    assert len(res["moves"]) > 0
    assert res["total_turns"] == len(res["moves"])
    assert res["bot1_error"] is None
    assert res["bot2_error"] is None
    assert "match_id" in res
    assert "initial_board" in res
    assert res["player1"]["id"] == 1
    assert res["player2"]["id"] == 2


def test_runner_bot_timeout_player1(tmp_path: Path) -> None:
    """Verify that a Player 1 bot exceeding turn timeout forfeits with win_reason='timeout'."""
    slow_bot = tmp_path / "slow_bot_p1.py"
    slow_bot.write_text(
        """
import time

def get_move(board, my_player, history):
    time.sleep(2.0)
    return ((0, 0), (1, 0))
""",
        encoding="utf-8",
    )
    res = run_match(
        str(slow_bot),
        BOT_TEMPLATE_PATH,
        max_turns=10,
        timeout_per_turn=0.5,
    )
    assert res["winner"] == 2
    assert res["win_reason"] == "timeout"
    assert res["bot1_error"] is not None
    assert "timed out" in res["bot1_error"].lower() or "timeout" in res["bot1_error"].lower()
    assert res["bot2_error"] is None


def test_runner_bot_timeout_player2(tmp_path: Path) -> None:
    """Verify that a Player 2 bot exceeding turn timeout forfeits with win_reason='timeout'."""
    slow_bot = tmp_path / "slow_bot_p2.py"
    slow_bot.write_text(
        """
import time

def get_move(board, my_player, history):
    time.sleep(2.0)
    return ((8, 0), (7, 0))
""",
        encoding="utf-8",
    )
    res = run_match(
        BOT_TEMPLATE_PATH,
        str(slow_bot),
        max_turns=10,
        timeout_per_turn=0.5,
    )
    assert res["winner"] == 1
    assert res["win_reason"] == "timeout"
    assert res["bot2_error"] is not None
    assert "timed out" in res["bot2_error"].lower() or "timeout" in res["bot2_error"].lower()
    assert res["bot1_error"] is None


def test_runner_bot_infinite_loop(tmp_path: Path) -> None:
    """Verify that a bot stuck in an infinite loop is cleanly terminated on timeout."""
    loop_bot = tmp_path / "loop_bot.py"
    loop_bot.write_text(
        """
def get_move(board, my_player, history):
    while True:
        pass
""",
        encoding="utf-8",
    )
    res = run_match(
        str(loop_bot),
        BOT_TEMPLATE_PATH,
        max_turns=5,
        timeout_per_turn=0.5,
    )
    assert res["winner"] == 2
    assert res["win_reason"] == "timeout"
    assert res["bot1_error"] is not None


def test_runner_bot_crash_runtime_exception(tmp_path: Path) -> None:
    """Verify that a bot raising an unhandled exception loses with win_reason='error'."""
    crash_bot = tmp_path / "crash_bot.py"
    crash_bot.write_text(
        """
def get_move(board, my_player, history):
    raise ValueError("Intentional bot failure")
""",
        encoding="utf-8",
    )
    res = run_match(
        str(crash_bot),
        BOT_TEMPLATE_PATH,
        max_turns=10,
        timeout_per_turn=1.0,
    )
    assert res["winner"] == 2
    assert res["win_reason"] == "error"
    assert res["bot1_error"] is not None
    assert "ValueError" in res["bot1_error"]
    assert res["bot2_error"] is None


def test_runner_bot_syntax_error(tmp_path: Path) -> None:
    """Verify that a bot with syntax errors fails during loading with win_reason='error'."""
    bad_syntax_bot = tmp_path / "syntax_error_bot.py"
    bad_syntax_bot.write_text("def get_move(: invalid syntax", encoding="utf-8")
    res = run_match(
        str(bad_syntax_bot),
        BOT_TEMPLATE_PATH,
        max_turns=10,
        timeout_per_turn=1.0,
    )
    assert res["winner"] == 2
    assert res["win_reason"] == "error"
    assert res["bot1_error"] is not None


def test_runner_invalid_move_out_of_bounds(tmp_path: Path) -> None:
    """Verify that a bot returning out-of-bounds coordinates forfeits with 'invalid_move'."""
    bad_move_bot = tmp_path / "oob_bot.py"
    bad_move_bot.write_text(
        """
def get_move(board, my_player, history):
    return ((9, 9), (9, 9))
""",
        encoding="utf-8",
    )
    res = run_match(
        str(bad_move_bot),
        BOT_TEMPLATE_PATH,
        max_turns=10,
        timeout_per_turn=1.0,
    )
    assert res["winner"] == 2
    assert res["win_reason"] == "invalid_move"
    assert res["bot1_error"] is not None


def test_runner_invalid_move_garbage_payload(tmp_path: Path) -> None:
    """Verify that a bot returning non-move garbage forfeits with 'invalid_move'."""
    garbage_bot = tmp_path / "garbage_bot.py"
    garbage_bot.write_text(
        """
def get_move(board, my_player, history):
    return "totally_invalid_move"
""",
        encoding="utf-8",
    )
    res = run_match(
        str(garbage_bot),
        BOT_TEMPLATE_PATH,
        max_turns=10,
        timeout_per_turn=1.0,
    )
    assert res["winner"] == 2
    assert res["win_reason"] == "invalid_move"
    assert res["bot1_error"] is not None


def test_runner_invalid_move_friendly_destination(tmp_path: Path) -> None:
    """Verify that a bot trying to step on its own piece forfeits with 'invalid_move'."""
    friendly_fire_bot = tmp_path / "friendly_fire_bot.py"
    friendly_fire_bot.write_text(
        """
def get_move(board, my_player, history):
    # (0, 0) and (0, 1) are both player 1 pieces at start
    return ((0, 0), (0, 1))
""",
        encoding="utf-8",
    )
    res = run_match(
        str(friendly_fire_bot),
        BOT_TEMPLATE_PATH,
        max_turns=10,
        timeout_per_turn=1.0,
    )
    assert res["winner"] == 2
    assert res["win_reason"] == "invalid_move"
    assert res["bot1_error"] is not None


def test_runner_save_replay_creates_valid_json(tmp_path: Path) -> None:
    """Verify that save_replay produces a valid formatted JSON file."""
    res = run_match(
        BOT_TEMPLATE_PATH,
        HEURISTIC_BOT_PATH,
        max_turns=20,
        timeout_per_turn=1.0,
    )
    replay_path = tmp_path / "replays" / "match_test.json"
    save_replay(res, str(replay_path))

    assert replay_path.exists()
    assert replay_path.is_file()

    with open(replay_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["match_id"] == res["match_id"]
    assert data["winner"] == res["winner"]
    assert data["win_reason"] == res["win_reason"]
    assert data["total_turns"] == res["total_turns"]
    assert isinstance(data["moves"], list)
    assert len(data["moves"]) == res["total_turns"]
    assert "initial_board" in data
    assert "player1" in data
    assert "player2" in data


def test_runner_custom_player_info() -> None:
    """Verify that player1_info and player2_info metadata are preserved in match results."""
    p1_meta = {"id": 42, "username": "alice_champion", "bot_name": "DragonV1"}
    p2_meta = {"id": 99, "username": "bob_challenger", "bot_name": "TitanV2"}

    res = run_match(
        BOT_TEMPLATE_PATH,
        HEURISTIC_BOT_PATH,
        max_turns=10,
        player1_info=p1_meta,
        player2_info=p2_meta,
    )
    assert res["player1"]["id"] == 42
    assert res["player1"]["username"] == "alice_champion"
    assert res["player2"]["id"] == 99
    assert res["player2"]["username"] == "bob_challenger"


def test_runner_bot_with_print_statements(tmp_path: Path) -> None:
    """Verify that bot stdout print calls do not disrupt IPC JSON communication."""
    noisy_bot = tmp_path / "noisy_bot.py"
    noisy_bot.write_text(
        """
import random
from engine.game import DIRECTIONS, beats

def get_move(board, my_player, history):
    print("DEBUG: Thinking about next move...")
    print("DEBUG: stdout output that should not corrupt IPC!")
    valid_moves = []
    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell and cell["player"] == my_player:
                for dr, dc in DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 9 and 0 <= nc < 9:
                        tgt = board[nr][nc]
                        if tgt is None or (tgt["player"] != my_player and beats(cell["type"], tgt["type"])):
                            valid_moves.append(((r, c), (nr, nc)))
    return random.choice(valid_moves)
""",
        encoding="utf-8",
    )
    res = run_match(
        str(noisy_bot),
        BOT_TEMPLATE_PATH,
        max_turns=10,
        timeout_per_turn=1.0,
    )
    assert len(res["moves"]) > 0
    assert res["bot1_error"] is None
