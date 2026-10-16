"""Local Arena Simulator for 9x9 Rock-Paper-Scissors Chess.

This standalone CLI tool allows students and developers to test bots locally
without connecting to the tournament server. It loads two bot scripts, simulates
matches using engine.game.GameState, validates moves, and displays match statistics.

Usage:
    python starter_kit/local_arena.py <bot1_path> <bot2_path> [--rounds N] [--max-turns M] [--verbose] [--swap-sides]

Examples:
    python starter_kit/local_arena.py starter_kit/bot_template.py starter_kit/heuristic_bot.py
    python starter_kit/local_arena.py my_bot.py starter_kit/heuristic_bot.py --rounds 5 --max-turns 200
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import sys
import time
from pathlib import Path
from typing import Any, Callable

# Ensure repository root is on sys.path so the engine package can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.game import GameState, MAX_TURNS, TYPE_ICONS
from engine.sandbox import validate_bot_file


def load_bot(file_path: str | Path) -> Callable[..., tuple[tuple[int, int], tuple[int, int]]]:
    """Dynamically load and validate a bot script from disk.

    Args:
        file_path: Path to the Python bot file.

    Returns:
        The callable 'get_move' function defined in the bot file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file fails AST sandbox validation or lacks 'get_move'.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Bot file not found: {path}")

    # Validate against AST security rules
    is_valid, error = validate_bot_file(path)
    if not is_valid:
        raise ValueError(f"Bot failed sandbox validation: {error}")

    # Load module dynamically
    module_name = f"bot_{path.stem}_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Failed to create module spec for: {path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ValueError(f"Failed to execute bot module {path}: {exc}") from exc

    bot_fn = getattr(module, "get_move", None)
    if not callable(bot_fn):
        raise ValueError(f"Bot file '{path.name}' does not define a callable 'get_move' function.")

    return bot_fn


def play_match(
    bot1_fn: Callable[..., Any],
    bot2_fn: Callable[..., Any],
    max_turns: int = MAX_TURNS,
    verbose: bool = False,
    bot1_name: str = "Player 1",
    bot2_name: str = "Player 2",
) -> dict[str, Any]:
    """Simulate a single match between two bot functions.

    Args:
        bot1_fn: get_move callable for Player 1.
        bot2_fn: get_move callable for Player 2.
        max_turns: Maximum total half-moves allowed before tiebreaker.
        verbose: If True, print move-by-move actions.
        bot1_name: Label for Player 1 in output.
        bot2_name: Label for Player 2 in output.

    Returns:
        Dictionary containing match results:
            - winner: 1, 2, or None (draw)
            - win_reason: 'goal', 'wipeout', 'max_turns', 'invalid_move', 'error'
            - turns: Total moves played
            - moves: History of moves
            - error: Error message string if forfeited
            - p1_pieces: Final piece count for Player 1
            - p2_pieces: Final piece count for Player 2
    """
    game = GameState(max_turns=max_turns)
    bot_map = {1: (bot1_fn, bot1_name), 2: (bot2_fn, bot2_name)}

    while not game.is_game_over:
        current_turn = game.turn
        current_bot, current_name = bot_map[current_turn]
        opponent_turn = 2 if current_turn == 1 else 1

        # Deepcopy state to prevent bots from modifying engine data structures
        board_copy = copy.deepcopy(game.board)
        history_copy = copy.deepcopy(game.history)

        try:
            move = current_bot(board_copy, current_turn, history_copy)
        except Exception as exc:
            if verbose:
                print(f"  [!] {current_name} crashed with exception: {exc}")
            return {
                "winner": opponent_turn,
                "win_reason": "error",
                "error": f"{current_name} raised an unhandled exception: {exc}",
                "turns": game.move_no - 1,
                "moves": game.history,
                "p1_pieces": game.count_pieces(1),
                "p2_pieces": game.count_pieces(2),
            }

        # Validate move format and legality
        valid_moves = game.get_valid_moves(current_turn)
        if not (
            isinstance(move, tuple)
            and len(move) == 2
            and isinstance(move[0], tuple)
            and isinstance(move[1], tuple)
            and move in valid_moves
        ):
            if verbose:
                print(f"  [!] {current_name} played illegal move: {move}")
            return {
                "winner": opponent_turn,
                "win_reason": "invalid_move",
                "error": f"{current_name} submitted an illegal move: {move}",
                "turns": game.move_no - 1,
                "moves": game.history,
                "p1_pieces": game.count_pieces(1),
                "p2_pieces": game.count_pieces(2),
            }

        # Apply valid move
        from_pos, to_pos = move
        res = game.apply_move(from_pos, to_pos)

        if verbose:
            san = res.get("san", f"{from_pos}->{to_pos}")
            piece_icon = TYPE_ICONS.get(res.get("piece", ""), "")
            print(f"  Move {game.move_no - 1:3d} | {current_name:12s} | {piece_icon} {san}")

    return {
        "winner": game.winner,
        "win_reason": game.win_reason,
        "error": None,
        "turns": game.move_no - 1,
        "moves": game.history,
        "p1_pieces": game.count_pieces(1),
        "p2_pieces": game.count_pieces(2),
    }


def run_arena(
    bot1_path: str | Path,
    bot2_path: str | Path,
    rounds: int = 1,
    max_turns: int = MAX_TURNS,
    verbose: bool = False,
    swap_sides: bool = False,
) -> dict[str, Any]:
    """Execute a series of matches between two bot scripts and output summary statistics.

    Args:
        bot1_path: File path to Bot 1.
        bot2_path: File path to Bot 2.
        rounds: Number of rounds to simulate.
        max_turns: Maximum half-moves per round.
        verbose: Whether to print detailed move-by-move traces.
        swap_sides: Whether to alternate starting player on each round.

    Returns:
        Dictionary containing overall tournament statistics.
    """
    p1_path = Path(bot1_path)
    p2_path = Path(bot2_path)

    bot1_fn = load_bot(p1_path)
    bot2_fn = load_bot(p2_path)

    b1_label = p1_path.stem
    b2_label = p2_path.stem

    print("=" * 60)
    print("  LOCAL ARENA BATTLE SIMULATOR")
    print(f"  Bot 1: {b1_label} ({p1_path.name})")
    print(f"  Bot 2: {b2_label} ({p2_path.name})")
    print(f"  Rounds: {rounds} | Max Turns: {max_turns} | Swap Sides: {swap_sides}")
    print("=" * 60)

    b1_wins = 0
    b2_wins = 0
    draws = 0
    total_turns = 0
    round_details: list[dict[str, Any]] = []

    for round_num in range(1, rounds + 1):
        # Swap colors on even rounds if swap_sides is enabled
        swapped = swap_sides and (round_num % 2 == 0)
        if not swapped:
            first_fn, second_fn = bot1_fn, bot2_fn
            first_name, second_name = f"{b1_label} (P1)", f"{b2_label} (P2)"
        else:
            first_fn, second_fn = bot2_fn, bot1_fn
            first_name, second_name = f"{b2_label} (P1)", f"{b1_label} (P2)"

        print(f"\n--- Round {round_num}/{rounds} ---")
        if verbose:
            print(f"  Player 1: {first_name} vs Player 2: {second_name}")

        start_time = time.perf_counter()
        result = play_match(
            first_fn,
            second_fn,
            max_turns=max_turns,
            verbose=verbose,
            bot1_name=first_name,
            bot2_name=second_name,
        )
        elapsed = time.perf_counter() - start_time

        winner = result["winner"]
        reason = result["win_reason"]
        turns = result["turns"]
        total_turns += turns

        # Determine which bot actually won
        if winner == 1:
            round_winner = b2_label if swapped else b1_label
            if not swapped:
                b1_wins += 1
            else:
                b2_wins += 1
        elif winner == 2:
            round_winner = b1_label if swapped else b2_label
            if not swapped:
                b2_wins += 1
            else:
                b1_wins += 1
        else:
            round_winner = "Draw"
            draws += 1

        print(
            f"  Winner: {round_winner:<15s} | Reason: {reason:<12s} | "
            f"Turns: {turns:3d} | Time: {elapsed:.3f}s"
        )
        if result.get("error"):
            print(f"    Detail: {result['error']}")

        round_details.append({
            "round": round_num,
            "winner": round_winner,
            "reason": reason,
            "turns": turns,
            "elapsed": elapsed,
        })

    # Summary report
    avg_turns = total_turns / rounds if rounds > 0 else 0
    b1_pct = (b1_wins / rounds) * 100 if rounds > 0 else 0
    b2_pct = (b2_wins / rounds) * 100 if rounds > 0 else 0
    draw_pct = (draws / rounds) * 100 if rounds > 0 else 0

    print("\n" + "=" * 60)
    print("  TOURNAMENT RESULTS SUMMARY")
    print("=" * 60)
    print(f"  {b1_label:20s}: {b1_wins:3d} wins ({b1_pct:5.1f}%)")
    print(f"  {b2_label:20s}: {b2_wins:3d} wins ({b2_pct:5.1f}%)")
    print(f"  {'Draws':20s}: {draws:3d}      ({draw_pct:5.1f}%)")
    print(f"  {'Average Turns':20s}: {avg_turns:.1f}")
    print("=" * 60)

    return {
        "bot1": b1_label,
        "bot2": b2_label,
        "rounds": rounds,
        "bot1_wins": b1_wins,
        "bot2_wins": b2_wins,
        "draws": draws,
        "average_turns": avg_turns,
        "rounds_detail": round_details,
    }


def main() -> None:
    """CLI entrypoint for local arena."""
    parser = argparse.ArgumentParser(
        description="Run local simulations of 9x9 Rock-Paper-Scissors Chess matches between two bot files."
    )
    parser.add_argument("bot1", help="Path to Player 1 Python bot file (e.g. starter_kit/bot_template.py)")
    parser.add_argument("bot2", help="Path to Player 2 Python bot file (e.g. starter_kit/heuristic_bot.py)")
    parser.add_argument("-r", "--rounds", type=int, default=1, help="Number of rounds to play (default: 1)")
    parser.add_argument("-m", "--max-turns", type=int, default=MAX_TURNS, help=f"Max turns per round (default: {MAX_TURNS})")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print move-by-move details during match")
    parser.add_argument("--swap-sides", action="store_true", help="Alternate bot starting positions every round")

    args = parser.parse_args()

    try:
        run_arena(
            bot1_path=args.bot1,
            bot2_path=args.bot2,
            rounds=args.rounds,
            max_turns=args.max_turns,
            verbose=args.verbose,
            swap_sides=args.swap_sides,
        )
    except Exception as exc:
        print(f"Arena Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
