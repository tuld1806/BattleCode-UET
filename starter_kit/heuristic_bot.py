"""Heuristic Bot for 9x9 Rock-Paper-Scissors Chess.

This bot implements a multi-tiered heuristic evaluation strategy:
1. Priority 1 (Winning Move):
   - Move directly onto opponent goal square: (8, 8) for Player 1, (0, 0) for Player 2.
   - Execute a wipeout capture that eliminates the last surviving piece of any opponent piece type.
2. Priority 2 (Favorable Capture):
   - Capture enemy pieces with RPS advantage.
   - Bonus for safe captures where the capturing piece cannot be immediately retaliated upon.
   - Bonus for capturing piece types where opponent has fewer pieces left (approaching wipeout).
3. Priority 3 (Safe Advancement Towards Goal):
   - Advance towards the opponent goal without stepping into range of an enemy piece that beats our piece.
   - Evade attackers if a friendly piece is currently threatened.
4. Fallback:
   - Select the legal move that minimizes risk / danger.
"""

import random
from typing import Any

# 8 directions for king-like movement: (row_delta, col_delta)
DIRECTIONS: list[tuple[int, int]] = [
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
]

# Destination goal coordinates for each player
GOALS: dict[int, tuple[int, int]] = {
    1: (8, 8),
    2: (0, 0),
}


def beats(attacker: str, defender: str) -> bool:
    """Determine whether an attacking piece type defeats a defending piece type.

    Args:
        attacker: Piece type string ('R', 'P', or 'S').
        defender: Piece type string ('R', 'P', or 'S').

    Returns:
        True if attacker wins under Rock-Paper-Scissors rules, False otherwise.
    """
    return (
        (attacker == "R" and defender == "S")
        or (attacker == "S" and defender == "P")
        or (attacker == "P" and defender == "R")
    )


def count_pieces_by_type(
    board: list[list[dict[str, Any] | None]], player: int
) -> dict[str, int]:
    """Count surviving pieces for a player grouped by piece type ('R', 'P', 'S').

    Args:
        board: 9x9 board matrix.
        player: Player identifier (1 or 2).

    Returns:
        Dictionary mapping piece type ('R', 'P', 'S') to remaining piece count.
    """
    counts = {"R": 0, "P": 0, "S": 0}
    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell is not None and cell.get("player") == player:
                piece_type = cell.get("type", "")
                if piece_type in counts:
                    counts[piece_type] += 1
    return counts


def is_threatened_at(
    board: list[list[dict[str, Any] | None]],
    pos: tuple[int, int],
    piece_type: str,
    opponent: int,
) -> bool:
    """Check if a square currently contains or is adjacent to an enemy that beats piece_type.

    Args:
        board: 9x9 board matrix.
        pos: Square coordinate (row, col) to inspect.
        piece_type: Piece type string ('R', 'P', or 'S').
        opponent: Opponent player identifier (1 or 2).

    Returns:
        True if an adjacent opponent piece can capture this piece, False otherwise.
    """
    r, c = pos
    for dr, dc in DIRECTIONS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < 9 and 0 <= nc < 9:
            enemy = board[nr][nc]
            if enemy is not None and enemy.get("player") == opponent:
                enemy_type = enemy.get("type", "")
                if beats(enemy_type, piece_type):
                    return True
    return False


def is_threatened_after_move(
    board: list[list[dict[str, Any] | None]],
    from_pos: tuple[int, int],
    to_pos: tuple[int, int],
    piece_type: str,
    opponent: int,
) -> bool:
    """Check if moving a piece onto to_pos leaves it vulnerable to an immediate enemy capture.

    Args:
        board: 9x9 board matrix.
        from_pos: Current position of the moving piece.
        to_pos: Destination position of the moving piece.
        piece_type: Moving piece type ('R', 'P', or 'S').
        opponent: Opponent player identifier (1 or 2).

    Returns:
        True if an enemy piece adjacent to to_pos can capture piece_type next turn.
    """
    tr, tc = to_pos
    for dr, dc in DIRECTIONS:
        nr, nc = tr + dr, tc + dc
        if 0 <= nr < 9 and 0 <= nc < 9:
            # Ignore the square being vacated or the destination square
            if (nr, nc) == to_pos or (nr, nc) == from_pos:
                continue
            enemy = board[nr][nc]
            if enemy is not None and enemy.get("player") == opponent:
                enemy_type = enemy.get("type", "")
                if beats(enemy_type, piece_type):
                    return True
    return False


def get_valid_moves(
    board: list[list[dict[str, Any] | None]], my_player: int
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Find all legal moves available for the specified player on the current board.

    Args:
        board: 9x9 board matrix.
        my_player: Integer player identifier (1 or 2).

    Returns:
        List of ((from_row, from_col), (to_row, to_col)) representing legal moves.
    """
    valid_moves: list[tuple[tuple[int, int], tuple[int, int]]] = []

    for r in range(9):
        for c in range(9):
            piece = board[r][c]
            if piece is not None and piece.get("player") == my_player:
                p_type = piece.get("type", "")
                for dr, dc in DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 9 and 0 <= nc < 9:
                        target = board[nr][nc]
                        if target is None:
                            valid_moves.append(((r, c), (nr, nc)))
                        elif target.get("player") != my_player and beats(p_type, target.get("type", "")):
                            valid_moves.append(((r, c), (nr, nc)))

    return valid_moves


def score_move(
    board: list[list[dict[str, Any] | None]],
    move: tuple[tuple[int, int], tuple[int, int]],
    my_player: int,
    opponent: int,
    opponent_counts: dict[str, int],
    goal: tuple[int, int],
) -> float:
    """Evaluate and assign a heuristic quality score to a candidate move.

    Args:
        board: 9x9 board matrix.
        move: Candidate move ((from_row, from_col), (to_row, to_col)).
        my_player: Our player identifier (1 or 2).
        opponent: Opponent player identifier (1 or 2).
        opponent_counts: Dictionary of opponent surviving piece counts by type.
        goal: Target goal coordinate (row, col) for our player.

    Returns:
        Numeric score representing move desirability (higher is better).
    """
    from_pos, to_pos = move
    fr, fc = from_pos
    tr, tc = to_pos

    moving_piece = board[fr][fc]
    if moving_piece is None:
        return -100_000.0

    piece_type = moving_piece.get("type", "")
    target_cell = board[tr][tc]

    # Priority 1A: Winning move by reaching opponent's goal square
    if to_pos == goal:
        return 1_000_000.0

    # Priority 1B: Wipeout capture eliminating the last surviving piece of an enemy type
    if target_cell is not None:
        target_type = target_cell.get("type", "")
        if opponent_counts.get(target_type, 0) == 1:
            return 900_000.0

    # Distance metrics to goal
    curr_chebyshev = max(abs(fr - goal[0]), abs(fc - goal[1]))
    new_chebyshev = max(abs(tr - goal[0]), abs(tc - goal[1]))
    chebyshev_improvement = curr_chebyshev - new_chebyshev

    curr_manhattan = abs(fr - goal[0]) + abs(fc - goal[1])
    new_manhattan = abs(tr - goal[0]) + abs(tc - goal[1])
    manhattan_improvement = curr_manhattan - new_manhattan

    is_dest_threatened = is_threatened_after_move(board, from_pos, to_pos, piece_type, opponent)
    is_currently_threatened = is_threatened_at(board, from_pos, piece_type, opponent)

    # Priority 2: Favorable captures
    if target_cell is not None:
        target_type = target_cell.get("type", "")
        score = 10_000.0

        # Bonus if opponent has only 2 pieces left of this type (pressure towards wipeout)
        if opponent_counts.get(target_type, 0) == 2:
            score += 3_000.0

        # Safe capture bonus vs trading penalty
        if not is_dest_threatened:
            score += 2_000.0
        else:
            score -= 1_500.0

        score += chebyshev_improvement * 50.0
        return score

    # Priority 3: Non-capture moves
    if not is_dest_threatened:
        # Move is safe from enemy retaliation
        score = 1_000.0
        score += chebyshev_improvement * 100.0
        score += manhattan_improvement * 20.0

        # Bonus for escaping a currently threatened square
        if is_currently_threatened:
            score += 500.0
    else:
        # Move places piece directly in harm's way
        score = -5_000.0
        score += chebyshev_improvement * 50.0
        score += manhattan_improvement * 10.0

    return score


def get_move(
    board: list[list[dict[str, Any] | None]],
    my_player: int,
    history: list[dict[str, Any]],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Select the best move using heuristic evaluation.

    Args:
        board: 9x9 matrix representing current board state.
        my_player: 1 (Player 1) or 2 (Player 2).
        history: Chronological list of previous moves in the match.

    Returns:
        Tuple ((from_row, from_col), (to_row, to_col)) representing the chosen move.

    Raises:
        ValueError: If no legal moves are available.
    """
    valid_moves = get_valid_moves(board, my_player)
    if not valid_moves:
        raise ValueError("No legal moves available.")

    opponent = 2 if my_player == 1 else 1
    opponent_counts = count_pieces_by_type(board, opponent)
    goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))

    # Score each available candidate move
    scored_moves: list[tuple[float, tuple[tuple[int, int], tuple[int, int]]]] = []
    for move in valid_moves:
        score = score_move(board, move, my_player, opponent, opponent_counts, goal)
        scored_moves.append((score, move))

    # Sort descending by heuristic score
    scored_moves.sort(key=lambda item: item[0], reverse=True)

    # Pick randomly among moves tied with the top score for slight unpredictability
    best_score = scored_moves[0][0]
    best_candidates = [move for score, move in scored_moves if score == best_score]

    return random.choice(best_candidates)
