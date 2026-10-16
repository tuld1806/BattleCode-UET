"""Unit and integration tests for the Bot Starter Kit and Local Arena CLI."""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from engine.game import GameState, GOALS, create_initial_board
from engine.sandbox import validate_bot_file


STARTER_KIT_DIR = Path(__file__).resolve().parent.parent / "starter_kit"
BOT_TEMPLATE_PATH = STARTER_KIT_DIR / "bot_template.py"
HEURISTIC_BOT_PATH = STARTER_KIT_DIR / "heuristic_bot.py"
LOCAL_ARENA_PATH = STARTER_KIT_DIR / "local_arena.py"
README_PATH = STARTER_KIT_DIR / "README.md"


class TestBotSandboxValidation:
    """Ensure bot templates pass the AST security sandbox validator."""

    def test_bot_template_passes_sandbox(self) -> None:
        """bot_template.py must pass validate_bot_file without security errors."""
        is_valid, error = validate_bot_file(BOT_TEMPLATE_PATH)
        assert is_valid, f"bot_template.py failed validation: {error}"
        assert error is None

    def test_heuristic_bot_passes_sandbox(self) -> None:
        """heuristic_bot.py must pass validate_bot_file without security errors."""
        is_valid, error = validate_bot_file(HEURISTIC_BOT_PATH)
        assert is_valid, f"heuristic_bot.py failed validation: {error}"
        assert error is None


class TestBotBehavior:
    """Verify standard bot behaviors and decision making."""

    def test_bot_template_valid_move_p1(self) -> None:
        """bot_template must return a valid legal move for Player 1 from initial board."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.bot_template import get_move as template_move

        board = create_initial_board()
        state = GameState(board=board, turn=1)
        valid_moves = state.get_valid_moves(1)

        move = template_move(board, 1, [])
        assert move in valid_moves, f"Move {move} not in legal moves {valid_moves}"

    def test_bot_template_valid_move_p2(self) -> None:
        """bot_template must return a valid legal move for Player 2 from initial board."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.bot_template import get_move as template_move

        board = create_initial_board()
        state = GameState(board=board, turn=2)
        valid_moves = state.get_valid_moves(2)

        move = template_move(board, 2, [])
        assert move in valid_moves, f"Move {move} not in legal moves {valid_moves}"

    def test_heuristic_bot_prioritizes_goal_p1(self) -> None:
        """heuristic_bot must immediately choose the goal square when within reach."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.heuristic_bot import get_move as heuristic_move

        board = [[None for _ in range(9)] for _ in range(9)]
        # Player 1 has a Rock at (7, 8), adjacent to goal (8, 8)
        board[7][8] = {"type": "R", "player": 1}
        # Player 2 has a piece elsewhere
        board[0][0] = {"type": "S", "player": 2}

        move = heuristic_move(board, 1, [])
        assert move == ((7, 8), (8, 8)), f"Expected move to goal (8, 8), got {move}"

    def test_heuristic_bot_prioritizes_goal_p2(self) -> None:
        """heuristic_bot as Player 2 must immediately choose (0, 0) goal when within reach."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.heuristic_bot import get_move as heuristic_move

        board = [[None for _ in range(9)] for _ in range(9)]
        # Player 2 has a Scissors at (1, 1), adjacent to goal (0, 0)
        board[1][1] = {"type": "S", "player": 2}
        # Player 1 has a piece elsewhere
        board[8][8] = {"type": "R", "player": 1}

        move = heuristic_move(board, 2, [])
        assert move == ((1, 1), (0, 0)), f"Expected move to goal (0, 0), got {move}"

    def test_heuristic_bot_prioritizes_wipeout_capture(self) -> None:
        """heuristic_bot should take a capture that wipes out opponent piece type."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.heuristic_bot import get_move as heuristic_move

        board = [[None for _ in range(9)] for _ in range(9)]
        # P1 has Rock at (4, 4)
        board[4][4] = {"type": "R", "player": 1}
        # P2 has only ONE Scissors left at (4, 5) (Rock beats Scissors)
        board[4][5] = {"type": "S", "player": 2}
        # P2 also has Paper pieces elsewhere
        board[7][7] = {"type": "P", "player": 2}

        move = heuristic_move(board, 1, [])
        assert move == ((4, 4), (4, 5)), f"Expected wipeout capture of last Scissors, got {move}"

    def test_heuristic_bot_avoids_walking_into_enemy_threat(self) -> None:
        """heuristic_bot should avoid moves that step into an immediate enemy capture."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.heuristic_bot import get_move as heuristic_move

        board = [[None for _ in range(9)] for _ in range(9)]
        # P1 has Rock at (4, 4)
        board[4][4] = {"type": "R", "player": 1}
        # P2 has Paper at (5, 6) which threatens (4, 5) and (5, 5)
        board[5][6] = {"type": "P", "player": 2}

        move = heuristic_move(board, 1, [])
        # From (4, 4), destinations (4, 5), (5, 5) are 1 step from Paper at (5, 6)
        # The bot should choose a safe destination away from Paper
        assert move[1] not in {(4, 5), (5, 5)}, f"Bot stepped into threatened square: {move}"


class TestLocalArena:
    """Verify local arena engine execution and CLI tool."""

    def test_local_arena_load_bot(self) -> None:
        """local_arena.load_bot should load and return get_move function."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.local_arena import load_bot

        bot_fn = load_bot(BOT_TEMPLATE_PATH)
        assert callable(bot_fn)

    def test_local_arena_load_bot_invalid_path(self) -> None:
        """load_bot should raise FileNotFoundError or ValueError for missing file."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.local_arena import load_bot

        with pytest.raises((FileNotFoundError, ValueError)):
            load_bot(STARTER_KIT_DIR / "non_existent_bot.py")

    def test_local_arena_play_match(self) -> None:
        """play_match should execute a game between two bots and return results."""
        sys.path.insert(0, str(STARTER_KIT_DIR.parent))
        from starter_kit.bot_template import get_move as bot1
        from starter_kit.heuristic_bot import get_move as bot2
        from starter_kit.local_arena import play_match

        result = play_match(bot1, bot2, max_turns=30)
        assert "winner" in result
        assert result["winner"] in (1, 2, None)
        assert "win_reason" in result
        assert result["win_reason"] in ("goal", "wipeout", "max_turns", "invalid_move", "error")
        assert "turns" in result
        assert result["turns"] > 0
        assert "moves" in result

    def test_local_arena_cli_execution(self) -> None:
        """Executing local_arena.py via CLI should run rounds and exit with code 0."""
        cmd = [
            sys.executable,
            str(LOCAL_ARENA_PATH),
            str(BOT_TEMPLATE_PATH),
            str(HEURISTIC_BOT_PATH),
            "--rounds",
            "2",
            "--max-turns",
            "20",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, f"CLI exited with {proc.returncode}. Stderr: {proc.stderr}"
        assert "Round 1" in proc.stdout
        assert "TOURNAMENT RESULTS SUMMARY" in proc.stdout.upper()


class TestDocumentation:
    """Verify documentation quality and presence."""

    def test_readme_exists_and_contains_instructions(self) -> None:
        """README.md must exist and contain clear guide on rules, coordinates, and arena."""
        assert README_PATH.is_file(), "README.md does not exist"
        content = README_PATH.read_text(encoding="utf-8")
        assert "get_move" in content
        assert "local_arena.py" in content
        assert "Rock" in content or "RPS" in content
