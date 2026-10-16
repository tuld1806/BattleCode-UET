"""Domain 3 Deep Testing: Subprocess Match Runner timeout enforcement, crash traps, and exploit isolation."""

import os
import tempfile
import pytest
from engine.runner import run_match


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_runner_terminates_infinite_loop_at_timeout(temp_dir):
    """Verify that a bot trapped in an infinite while loop is terminated cleanly at 1.0s."""
    loop_bot = os.path.join(temp_dir, "loop_bot.py")
    with open(loop_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    while True:
        pass
""")

    normal_bot = os.path.join(temp_dir, "normal_bot.py")
    with open(normal_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
""")

    result = run_match(
        loop_bot,
        normal_bot,
        timeout_per_turn=0.5,
    )

    assert result["winner"] == 2
    assert result["win_reason"] == "timeout"
    assert "timed out" in result["bot1_error"].lower()


def test_runner_catches_system_exit_safely(temp_dir):
    """Verify that a bot attempting to invoke SystemExit forfeits with error."""
    exit_bot = os.path.join(temp_dir, "exit_bot.py")
    with open(exit_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    raise SystemExit(42)
""")

    normal_bot = os.path.join(temp_dir, "normal_bot.py")
    with open(normal_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
""")

    result = run_match(
        exit_bot,
        normal_bot,
        timeout_per_turn=0.5,
    )

    assert result["winner"] == 2
    assert result["win_reason"] in ("error", "invalid_move")


def test_runner_malformed_move_types_rejected(temp_dir):
    """Verify that bots returning non-tuples, strings, or floats forfeit cleanly."""
    bad_bots = [
        ("return_none.py", "return None"),
        ("return_str.py", "return 'a1-a2'"),
        ("return_single.py", "return ((0, 0),)"),
        ("return_triple.py", "return ((0, 0), (1, 1), (2, 2))"),
        ("return_floats.py", "return ((0.5, 0.0), (1.0, 1.0))"),
    ]

    normal_bot = os.path.join(temp_dir, "normal_bot.py")
    with open(normal_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
""")

    for filename, code_snippet in bad_bots:
        bad_bot_path = os.path.join(temp_dir, filename)
        with open(bad_bot_path, "w") as f:
            f.write(f"""
def get_move(board, my_player, history):
    {code_snippet}
""")

        result = run_match(
            bad_bot_path,
            normal_bot,
            timeout_per_turn=0.5,
        )

        assert result["winner"] == 2
        assert result["win_reason"] in ("invalid_move", "error")


def test_runner_board_mutation_isolation(temp_dir):
    """Verify that a malicious bot modifying input board elements does not affect the engine."""
    mutator_bot = os.path.join(temp_dir, "mutator_bot.py")
    with open(mutator_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    # Attempt to wipe all board squares
    for r in range(9):
        for c in range(9):
            board[r][c] = None
    return ((0, 0), (1, 0))
""")

    normal_bot = os.path.join(temp_dir, "normal_bot.py")
    with open(normal_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    return ((8, 0), (7, 0))
""")

    result = run_match(
        mutator_bot,
        normal_bot,
        timeout_per_turn=0.5,
    )

    # Move from (0, 0) to (1, 0) must succeed on the authoritative board
    assert result["total_turns"] >= 1
    first_move = result["moves"][0]
    assert first_move["player"] == 1
    assert first_move["from"] == [0, 0]
    assert first_move["to"] == [1, 0]


def test_runner_catches_memory_explosion(temp_dir):
    """Verify that a bot attempting excessive memory allocation is safely terminated via timeout or error."""
    mem_bot = os.path.join(temp_dir, "mem_bot.py")
    with open(mem_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    # Attempt huge memory consumption
    chunks = []
    for _ in range(1000):
        chunks.append(bytearray(20_000_000))
    return ((0, 0), (1, 0))
""")

    normal_bot = os.path.join(temp_dir, "normal_bot.py")
    with open(normal_bot, "w") as f:
        f.write("""
def get_move(board, my_player, history):
    return ((8, 0), (7, 0))
""")

    result = run_match(
        mem_bot,
        normal_bot,
        timeout_per_turn=0.5,
    )

    assert result["winner"] == 2
    assert result["win_reason"] in ("timeout", "error", "invalid_move")

