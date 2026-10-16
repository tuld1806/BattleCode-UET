"""Isolated Subprocess Match Runner and Replay Generator.

This module provides a secure, sandboxed execution environment for running 9x9
Rock-Paper-Scissors Chess matches between two Python bot files. Each bot is
executed in an isolated worker subprocess with strict turn timeout enforcement,
preventing infinite loops (e.g., while True) or deliberate delays (e.g., time.sleep)
from freezing the server.

Matches conclude via standard win conditions (goal reach, wipeout, max turns) or
forfeits (timeout, runtime crash / exception, illegal move). Replays are recorded
and can be exported as standardized JSON files for playback in the web visualizer.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from typing import Any
import uuid

from engine.game import GameState, create_initial_board


def _normalize_move(raw_move: Any) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Normalize raw move coordinates from bot output into standard coordinate tuples.

    Args:
        raw_move: Raw object returned by the bot.

    Returns:
        A tuple ((from_row, from_col), (to_row, to_col)) if valid, or None if malformed.
    """
    if not isinstance(raw_move, (list, tuple)) or len(raw_move) != 2:
        return None

    from_pos, to_pos = raw_move[0], raw_move[1]
    if not isinstance(from_pos, (list, tuple)) or len(from_pos) != 2:
        return None
    if not isinstance(to_pos, (list, tuple)) or len(to_pos) != 2:
        return None

    # Disallow booleans since bool is a subclass of int in Python
    if (
        isinstance(from_pos[0], bool)
        or isinstance(from_pos[1], bool)
        or isinstance(to_pos[0], bool)
        or isinstance(to_pos[1], bool)
    ):
        return None

    if not (
        isinstance(from_pos[0], int)
        and isinstance(from_pos[1], int)
        and isinstance(to_pos[0], int)
        and isinstance(to_pos[1], int)
    ):
        return None

    return ((from_pos[0], from_pos[1]), (to_pos[0], to_pos[1]))


def _run_worker(bot_path_str: str) -> None:
    """Entrypoint for the worker subprocess.

    Runs within a standalone child process. Diverts sys.stdout to sys.stderr so
    that any print() statements executed by user bot code will not corrupt the
    JSON communication channel on stdout.

    Args:
        bot_path_str: File path to the Python bot script to load and execute.
    """
    # Preserve original unbuffered stdout pipe specifically for IPC messages
    ipc_out = sys.stdout
    # Route all standard prints from user code to stderr to prevent protocol corruption
    sys.stdout = sys.stderr

    # Send initial heartbeat confirming worker process is up and running
    ipc_out.write(json.dumps({"status": "started"}) + "\n")
    ipc_out.flush()

    bot_path = Path(bot_path_str).resolve()
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    bot_dir = str(bot_path.parent)
    if bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)

    try:
        if not bot_path.is_file():
            raise FileNotFoundError(f"Bot script not found: {bot_path}")

        module_name = f"bot_subworker_{bot_path.stem}_{os.getpid()}"
        spec = importlib.util.spec_from_file_location(module_name, str(bot_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for: {bot_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        bot_fn = getattr(module, "get_move", None)
        if not callable(bot_fn):
            raise AttributeError(
                f"Bot file '{bot_path.name}' does not define a callable 'get_move' function."
            )

        # Notify parent orchestrator that the bot has loaded successfully
        ipc_out.write(json.dumps({"status": "ready"}) + "\n")
        ipc_out.flush()
    except Exception as exc:
        ipc_out.write(
            json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
            + "\n"
        )
        ipc_out.flush()
        return

    # Turn execution request loop: read turn inputs from stdin and respond on ipc_out
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if req.get("command") == "quit":
                break

            board = req["board"]
            my_player = req["my_player"]
            history = req["history"]

            # Invoke bot get_move function
            move = bot_fn(board, my_player, history)

            ipc_out.write(json.dumps({"status": "ok", "move": move}) + "\n")
            ipc_out.flush()
        except Exception as exc:
            ipc_out.write(
                json.dumps(
                    {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
                )
                + "\n"
            )
            ipc_out.flush()
            break


class BotProcess:
    """Manages lifecycle and turn execution of an isolated bot subprocess."""

    def __init__(self, bot_path: str | Path, timeout: float = 1.0) -> None:
        """Initialize BotProcess manager.

        Args:
            bot_path: Path to the bot file.
            timeout: Default per-turn timeout in seconds.
        """
        self.bot_path = Path(bot_path).resolve()
        self.timeout = timeout
        self.proc: subprocess.Popen[str] | None = None
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self.is_alive = False

    def start(self, startup_process_timeout: float = 5.0) -> tuple[bool, str | None, str | None]:
        """Spawn the worker process and wait for ready acknowledgment.

        Args:
            startup_process_timeout: Maximum seconds to wait for worker process launch.

        Returns:
            Tuple of (success, error_message, reason_string).
        """
        if not self.bot_path.is_file():
            return False, f"Bot file not found: {self.bot_path}", "error"

        repo_root = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{repo_root}{os.pathsep}{python_path}" if python_path else str(repo_root)
        )

        cmd = [
            sys.executable,
            "-u",
            "-m",
            "engine.runner",
            "--worker",
            str(self.bot_path),
        ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                cwd=str(repo_root),
                env=env,
            )
            self.is_alive = True
        except Exception as exc:
            return False, f"Failed to start bot subprocess: {exc}", "error"

        def _reader() -> None:
            assert self.proc is not None and self.proc.stdout is not None
            try:
                for line in iter(self.proc.stdout.readline, ""):
                    self._queue.put(line)
            except Exception:
                pass
            finally:
                self._queue.put(None)

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

        # Step 1: Wait for process launch signal
        try:
            line = self._queue.get(timeout=startup_process_timeout)
        except queue.Empty:
            self.kill()
            return (
                False,
                f"Worker launch timed out (> {startup_process_timeout:.1f}s)",
                "timeout",
            )

        if not line:
            self.kill()
            return False, "Bot process terminated unexpectedly on startup", "error"

        try:
            launch_data = json.loads(line.strip())
        except json.JSONDecodeError:
            self.kill()
            return False, f"Malformed startup response from worker: {line}", "error"

        if launch_data.get("status") != "started":
            self.kill()
            return False, launch_data.get("error", "Unexpected worker startup state"), "error"

        # Step 2: Wait for bot script import acknowledgment
        import_timeout = max(self.timeout, 3.0)
        try:
            line = self._queue.get(timeout=import_timeout)
        except queue.Empty:
            self.kill()
            return (
                False,
                f"Bot initialization timed out (> {import_timeout:.1f}s)",
                "timeout",
            )

        if not line:
            self.kill()
            return False, "Bot process terminated unexpectedly during initialization", "error"

        try:
            ready_data = json.loads(line.strip())
        except json.JSONDecodeError:
            self.kill()
            return False, f"Malformed initialization response from worker: {line}", "error"

        if ready_data.get("status") == "ready":
            return True, None, None
        else:
            self.kill()
            return False, ready_data.get("error", "Bot failed to initialize"), "error"

    def request_move(
        self,
        board: Any,
        my_player: int,
        history: Any,
        timeout: float,
    ) -> tuple[bool, Any, str | None, str | None]:
        """Request a move from the bot subprocess under a strict timeout.

        Args:
            board: 9x9 board matrix state.
            my_player: Active player number (1 or 2).
            history: List of previous move records.
            timeout: Maximum allowed execution time in seconds for this turn.

        Returns:
            Tuple of (success, move_result, error_message, win_reason).
            win_reason will be 'timeout' or 'error' on failure, or None on success.
        """
        if not self.is_alive or self.proc is None or self.proc.stdin is None:
            return False, None, "Bot process is not running", "error"

        payload = json.dumps(
            {
                "board": board,
                "my_player": my_player,
                "history": history,
            }
        )

        try:
            self.proc.stdin.write(payload + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self.kill()
            return False, None, f"Failed to send request to bot: {exc}", "error"

        try:
            line = self._queue.get(timeout=timeout)
        except queue.Empty:
            self.kill()
            return (
                False,
                None,
                f"Bot turn execution timed out (> {timeout:.1f}s)",
                "timeout",
            )

        if not line:
            self.kill()
            return (
                False,
                None,
                "Bot process terminated unexpectedly during turn",
                "error",
            )

        try:
            data = json.loads(line.strip())
        except json.JSONDecodeError:
            self.kill()
            return False, None, f"Malformed response from bot: {line}", "error"

        if data.get("status") == "ok":
            return True, data.get("move"), None, None
        else:
            self.kill()
            return False, None, data.get("error", "Bot crashed during turn"), "error"

    def kill(self) -> None:
        """Safely terminate the worker subprocess and release pipe handles."""
        self.is_alive = False
        if self.proc is not None:
            try:
                if self.proc.poll() is None:
                    self.proc.kill()
                    self.proc.wait(timeout=1.0)
            except Exception:
                pass
            finally:
                if self.proc.stdin:
                    try:
                        self.proc.stdin.close()
                    except Exception:
                        pass
                if self.proc.stdout:
                    try:
                        self.proc.stdout.close()
                    except Exception:
                        pass
                self.proc = None


def run_match(
    bot1_path: str,
    bot2_path: str,
    max_turns: int = 200,
    timeout_per_turn: float = 1.0,
    player1_info: dict[str, Any] | None = None,
    player2_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a complete 9x9 Rock-Paper-Scissors Chess match between two bot scripts.

    Runs both bots in isolated worker subprocesses, enforces per-turn timeout limits,
    tracks board states and move history, and records forfeit penalties if a bot
    times out, crashes, or produces an invalid move.

    Args:
        bot1_path: Path to Player 1 Python bot script.
        bot2_path: Path to Player 2 Python bot script.
        max_turns: Maximum half-turns before tiebreaker triggers (default: 200).
        timeout_per_turn: Maximum duration in seconds allowed for get_move (default: 1.0).
        player1_info: Optional metadata dictionary for Player 1.
        player2_info: Optional metadata dictionary for Player 2.

    Returns:
        Dictionary containing standardized match result and replay log:
            - match_id: Unique match identifier string.
            - player1: Metadata dictionary for Player 1.
            - player2: Metadata dictionary for Player 2.
            - winner: Winning player (1, 2, or None for draw).
            - win_reason: Reason string ('goal', 'wipeout', 'max_turns', 'timeout',
                          'error', 'invalid_move').
            - total_turns: Total number of moves executed.
            - moves: Chronological list of move record dictionaries.
            - bot1_error: Error message string for Player 1, or None.
            - bot2_error: Error message string for Player 2, or None.
            - initial_board: Initial 9x9 board configuration.
            - created_at: ISO-8601 timestamp string of match completion.
    """
    match_id = (
        str(player1_info.get("match_id"))
        if player1_info and "match_id" in player1_info
        else f"match_{uuid.uuid4().hex[:12]}"
    )

    p1_meta: dict[str, Any] = {
        "id": 1,
        "username": Path(bot1_path).stem,
        "bot_name": Path(bot1_path).stem,
        "bot_path": str(bot1_path),
    }
    if player1_info:
        p1_meta.update(copy.deepcopy(player1_info))

    p2_meta: dict[str, Any] = {
        "id": 2,
        "username": Path(bot2_path).stem,
        "bot_name": Path(bot2_path).stem,
        "bot_path": str(bot2_path),
    }
    if player2_info:
        p2_meta.update(copy.deepcopy(player2_info))

    initial_board = create_initial_board()
    game = GameState(board=initial_board, turn=1, move_no=1, max_turns=max_turns)

    bot1_error: str | None = None
    bot2_error: str | None = None
    winner: int | None = None
    win_reason: str = ""

    worker1: BotProcess | None = None
    worker2: BotProcess | None = None

    try:
        # Launch Worker 1
        worker1 = BotProcess(bot1_path, timeout=timeout_per_turn)
        ok1, err1, reason1 = worker1.start()
        if not ok1:
            winner = 2
            win_reason = reason1 or "error"
            bot1_error = err1
            return _format_match_result(
                match_id=match_id,
                p1_meta=p1_meta,
                p2_meta=p2_meta,
                winner=winner,
                win_reason=win_reason,
                game=game,
                bot1_error=bot1_error,
                bot2_error=bot2_error,
                initial_board=initial_board,
            )

        # Launch Worker 2
        worker2 = BotProcess(bot2_path, timeout=timeout_per_turn)
        ok2, err2, reason2 = worker2.start()
        if not ok2:
            winner = 1
            win_reason = reason2 or "error"
            bot2_error = err2
            return _format_match_result(
                match_id=match_id,
                p1_meta=p1_meta,
                p2_meta=p2_meta,
                winner=winner,
                win_reason=win_reason,
                game=game,
                bot1_error=bot1_error,
                bot2_error=bot2_error,
                initial_board=initial_board,
            )

        workers = {1: worker1, 2: worker2}

        # Main game simulation loop
        while not game.is_game_over:
            current_player = game.turn
            opponent = 2 if current_player == 1 else 1
            active_worker = workers[current_player]

            # Deepcopy board and history to prevent tampering
            board_snapshot = copy.deepcopy(game.board)
            history_snapshot = copy.deepcopy(game.history)

            ok, raw_move, err_msg, reason = active_worker.request_move(
                board=board_snapshot,
                my_player=current_player,
                history=history_snapshot,
                timeout=timeout_per_turn,
            )

            if not ok:
                winner = opponent
                win_reason = reason or "error"
                if current_player == 1:
                    bot1_error = err_msg
                else:
                    bot2_error = err_msg
                break

            # Validate move structure and game legality
            norm_move = _normalize_move(raw_move)
            valid_moves = game.get_valid_moves(current_player)

            if norm_move is None or norm_move not in valid_moves:
                winner = opponent
                win_reason = "invalid_move"
                illegal_msg = (
                    f"Player {current_player} submitted an illegal move: {raw_move}"
                )
                if current_player == 1:
                    bot1_error = illegal_msg
                else:
                    bot2_error = illegal_msg
                break

            # Apply move to board state
            game.apply_move(norm_move[0], norm_move[1])

            if game.is_game_over:
                winner = game.winner
                win_reason = game.win_reason or "max_turns"
                break

    finally:
        if worker1 is not None:
            worker1.kill()
        if worker2 is not None:
            worker2.kill()

    return _format_match_result(
        match_id=match_id,
        p1_meta=p1_meta,
        p2_meta=p2_meta,
        winner=winner,
        win_reason=win_reason,
        game=game,
        bot1_error=bot1_error,
        bot2_error=bot2_error,
        initial_board=initial_board,
    )


def _format_match_result(
    match_id: str,
    p1_meta: dict[str, Any],
    p2_meta: dict[str, Any],
    winner: int | None,
    win_reason: str,
    game: GameState,
    bot1_error: str | None,
    bot2_error: str | None,
    initial_board: list[list[dict[str, Any] | None]],
) -> dict[str, Any]:
    """Format match outcomes into a standardized dictionary.

    Args:
        match_id: Match identifier string.
        p1_meta: Metadata dictionary for Player 1.
        p2_meta: Metadata dictionary for Player 2.
        winner: Winning player (1, 2, or None).
        win_reason: Reason for conclusion.
        game: GameState instance.
        bot1_error: Player 1 error string.
        bot2_error: Player 2 error string.
        initial_board: 9x9 starting board matrix.

    Returns:
        Structured result dictionary.
    """
    # Standardize moves list with JSON-serializable list coordinates
    formatted_moves: list[dict[str, Any]] = []
    for m in game.history:
        formatted_moves.append(
            {
                "turn": m["turn"],
                "player": m["player"],
                "from": list(m["from"]),
                "to": list(m["to"]),
                "piece": m["piece"],
                "captured": m["captured"],
                "san": m["san"],
            }
        )

    return {
        "match_id": match_id,
        "player1": p1_meta,
        "player2": p2_meta,
        "winner": winner,
        "win_reason": win_reason,
        "total_turns": len(formatted_moves),
        "moves": formatted_moves,
        "bot1_error": bot1_error,
        "bot2_error": bot2_error,
        "initial_board": copy.deepcopy(initial_board),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_replay(match_result: dict[str, Any], filepath: str | Path) -> None:
    """Save match result and replay log to a JSON file.

    Args:
        match_result: Dictionary containing complete match outcome and move history.
        filepath: Target file path on disk (e.g., 'replays/match_101.json').
    """
    path = Path(filepath).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(match_result, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        _run_worker(sys.argv[2])
        sys.exit(0)
