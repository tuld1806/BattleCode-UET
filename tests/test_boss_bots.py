"""Unit and integration tests for Server-Side Boss Benchmark Bots.

Tests the five graduated benchmark boss bots in server/bosses/:
Level 1: Novice (novice_bot.py)
Level 2: Rusher (rusher_bot.py)
Level 3: Sentinel (sentinel_bot.py)
Level 4: Tactician (tactician_bot.py)
Level 5: Apex Master (apex_bot.py)

Verifies:
1. AST sandbox compliance via engine.sandbox.validate_bot_file.
2. Legal move generation for Player 1 and Player 2.
3. Execution performance (< 0.5s per turn).
4. Specialized tactical behaviors per bot tier.
5. End-to-end match execution via engine.runner.run_match.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import time
from typing import Any
import pytest

from engine.game import GameState, GOALS, beats, create_initial_board
from engine.runner import run_match
from engine.sandbox import validate_bot_file


BOSSES_DIR = Path(__file__).resolve().parent.parent / "server" / "bosses"
NOVICE_PATH = BOSSES_DIR / "novice_bot.py"
RUSHER_PATH = BOSSES_DIR / "rusher_bot.py"
SENTINEL_PATH = BOSSES_DIR / "sentinel_bot.py"
TACTICIAN_PATH = BOSSES_DIR / "tactician_bot.py"
APEX_PATH = BOSSES_DIR / "apex_bot.py"

ALL_BOSS_PATHS = [
    NOVICE_PATH,
    RUSHER_PATH,
    SENTINEL_PATH,
    TACTICIAN_PATH,
    APEX_PATH,
]


def _load_bot_module(file_path: Path):
    """Dynamically load bot module from file path."""
    module_name = f"boss_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None, f"Could not create spec for {file_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBossRegistry:
    """Verify registry dictionary and metadata in server/bosses/__init__.py."""

    def test_registry_contains_all_five_bosses(self) -> None:
        from server.bosses import BOSS_REGISTRY

        assert len(BOSS_REGISTRY) == 5
        expected_slugs = {"novice", "rusher", "sentinel", "tactician", "apex"}
        assert set(BOSS_REGISTRY.keys()) == expected_slugs

        for slug, info in BOSS_REGISTRY.items():
            assert "slug" in info
            assert "level" in info
            assert "name" in info or "display_name" in info
            assert "description" in info
            assert "file_path" in info
            path = Path(info["file_path"])
            assert path.exists(), f"Boss file not found: {path}"


class TestBossSandboxValidation:
    """Ensure all five boss bots strictly pass AST sandbox validation."""

    @pytest.mark.parametrize("bot_path", ALL_BOSS_PATHS)
    def test_boss_passes_sandbox(self, bot_path: Path) -> None:
        assert bot_path.exists(), f"Bot file does not exist: {bot_path}"
        is_valid, error = validate_bot_file(bot_path)
        assert is_valid, f"{bot_path.name} failed AST sandbox validation: {error}"
        assert error is None


class TestBossLegalMovesAndPerformance:
    """Ensure all bots return valid legal moves within strict time bounds (< 0.5s)."""

    @pytest.mark.parametrize("bot_path", ALL_BOSS_PATHS)
    def test_initial_board_valid_moves(self, bot_path: Path) -> None:
        mod = _load_bot_module(bot_path)
        assert hasattr(mod, "get_move"), f"{bot_path.name} missing get_move entrypoint"

        initial_board = create_initial_board()
        state1 = GameState(board=initial_board, turn=1)
        legal_p1 = set(state1.get_valid_moves(1))

        # Test Player 1 move
        t0 = time.perf_counter()
        move_p1 = mod.get_move(initial_board, 1, [])
        dt_p1 = time.perf_counter() - t0

        assert move_p1 in legal_p1, f"{bot_path.name} generated illegal P1 move: {move_p1}"
        assert dt_p1 < 0.5, f"{bot_path.name} P1 move took {dt_p1:.3f}s (>= 0.5s limit)"

        # Test Player 2 move
        state2 = GameState(board=initial_board, turn=2)
        legal_p2 = set(state2.get_valid_moves(2))

        t0 = time.perf_counter()
        move_p2 = mod.get_move(initial_board, 2, [])
        dt_p2 = time.perf_counter() - t0

        assert move_p2 in legal_p2, f"{bot_path.name} generated illegal P2 move: {move_p2}"
        assert dt_p2 < 0.5, f"{bot_path.name} P2 move took {dt_p2:.3f}s (>= 0.5s limit)"


class TestBossSpecializedBehaviors:
    """Verify distinct tactical behaviors for each boss tier."""

    def test_novice_takes_winning_goal_move(self) -> None:
        mod = _load_bot_module(NOVICE_PATH)
        board = [[None for _ in range(9)] for _ in range(9)]
        board[7][7] = {"type": "R", "player": 1}
        board[0][0] = {"type": "S", "player": 2}

        move = mod.get_move(board, 1, [])
        assert move == ((7, 7), (8, 8)), f"Novice failed to take immediate goal win: {move}"

    def test_novice_takes_favorable_capture(self) -> None:
        mod = _load_bot_module(NOVICE_PATH)
        board = [[None for _ in range(9)] for _ in range(9)]
        # P1 has Rock at (4, 4), P2 has Scissors at (4, 5)
        board[4][4] = {"type": "R", "player": 1}
        board[4][5] = {"type": "S", "player": 2}

        move = mod.get_move(board, 1, [])
        assert move == ((4, 4), (4, 5)), f"Novice should capture enemy Scissors with Rock: {move}"

    def test_rusher_minimizes_chebyshev_distance_to_goal(self) -> None:
        mod = _load_bot_module(RUSHER_PATH)
        board = [[None for _ in range(9)] for _ in range(9)]
        # P1 has Rock at (3, 3)
        board[3][3] = {"type": "R", "player": 1}
        # Enemy is far away at (0, 0)
        board[0][0] = {"type": "S", "player": 2}

        move = mod.get_move(board, 1, [])
        # From (3, 3), moves to (4, 4) strictly reduces Chebyshev distance to (8, 8) from 5 to 4
        from_pos, to_pos = move
        assert from_pos == (3, 3)
        d_before = max(abs(3 - 8), abs(3 - 8))  # 5
        d_after = max(abs(to_pos[0] - 8), abs(to_pos[1] - 8))
        assert d_after < d_before, f"Rusher move {move} did not decrease Chebyshev distance to goal"

    def test_rusher_avoids_moving_into_direct_capture(self) -> None:
        mod = _load_bot_module(RUSHER_PATH)
        board = [[None for _ in range(9)] for _ in range(9)]
        # P1 has Rock at (4, 4)
        board[4][4] = {"type": "R", "player": 1}
        # Enemy Paper is at (5, 6), which would threaten (5, 5)
        board[5][6] = {"type": "P", "player": 2}

        move = mod.get_move(board, 1, [])
        from_pos, to_pos = move
        # Moving to (5, 5) would put Rock adjacent to Paper at (5, 6), allowing Paper to capture it
        assert to_pos != (5, 5), "Rusher should not walk into square threatened by enemy Paper when other paths exist"

    def test_sentinel_defends_home_base_and_targets_scarce_enemy(self) -> None:
        mod = _load_bot_module(SENTINEL_PATH)
        board = [[None for _ in range(9)] for _ in range(9)]
        # P1 Sentinel has Scissors at (1, 1) and Rock at (5, 5)
        board[1][1] = {"type": "S", "player": 1}
        board[5][5] = {"type": "R", "player": 1}
        # Opponent has 1 Scissors at (5, 6) and 3 Rocks elsewhere
        board[5][6] = {"type": "S", "player": 2}
        board[8][0] = {"type": "R", "player": 2}
        board[8][1] = {"type": "R", "player": 2}
        board[8][2] = {"type": "R", "player": 2}

        # The opponent's Scissors count is 1 (scarce! single kill leads to wipeout!).
        # Rock at (5, 5) beats Scissors at (5, 6).
        move = mod.get_move(board, 1, [])
        assert move == ((5, 5), (5, 6)), f"Sentinel should target scarce enemy piece for wipeout: {move}"

    def test_tactician_depth_search_avoids_blunder(self) -> None:
        mod = _load_bot_module(TACTICIAN_PATH)
        board = [[None for _ in range(9)] for _ in range(9)]
        # P1 Tactician has Rock at (4, 4)
        board[4][4] = {"type": "R", "player": 1}
        # P2 has Paper at (6, 5)
        board[6][5] = {"type": "P", "player": 2}

        move = mod.get_move(board, 1, [])
        from_pos, to_pos = move
        # If P1 moves to (5, 5), P2's Paper at (6, 5) can immediately capture it on next ply.
        assert to_pos != (5, 5), "Tactician 2-ply search must avoid moving into fatal trap"

    def test_apex_complex_tactical_scenario_performance(self) -> None:
        mod = _load_bot_module(APEX_PATH)
        board = create_initial_board()
        # Mid-game state with multiple pieces
        board[3][3] = {"type": "R", "player": 1}
        board[3][4] = {"type": "P", "player": 1}
        board[4][4] = {"type": "S", "player": 2}
        board[4][5] = {"type": "R", "player": 2}

        t0 = time.perf_counter()
        move = mod.get_move(board, 1, [])
        dt = time.perf_counter() - t0

        state = GameState(board=board, turn=1)
        assert move in state.get_valid_moves(1), f"Apex move {move} is illegal"
        assert dt < 0.5, f"Apex execution took {dt:.3f}s (>= 0.5s limit)"


class TestBossMatchSimulations:
    """Run full matches between pairs of boss bots via engine.runner.run_match."""

    def test_novice_vs_rusher_clean_match(self) -> None:
        result = run_match(
            bot1_path=str(NOVICE_PATH),
            bot2_path=str(RUSHER_PATH),
            max_turns=50,
            timeout_per_turn=1.0,
        )
        assert result["bot1_error"] is None, f"Novice crashed: {result['bot1_error']}"
        assert result["bot2_error"] is None, f"Rusher crashed: {result['bot2_error']}"
        assert result["win_reason"] in {"goal", "wipeout", "max_turns"}

    def test_tactician_vs_apex_clean_match(self) -> None:
        result = run_match(
            bot1_path=str(TACTICIAN_PATH),
            bot2_path=str(APEX_PATH),
            max_turns=30,
            timeout_per_turn=1.0,
        )
        assert result["bot1_error"] is None, f"Tactician crashed: {result['bot1_error']}"
        assert result["bot2_error"] is None, f"Apex crashed: {result['bot2_error']}"
        assert result["win_reason"] in {"goal", "wipeout", "max_turns"}
