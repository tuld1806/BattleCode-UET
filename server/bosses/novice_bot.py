"""Novice Benchmark Boss Bot (Level 1).

Strategy:
1. Immediate Winning Moves:
   - Move directly onto target goal square (8, 8) for Player 1 or (0, 0) for Player 2.
   - Execute a wipeout capture eliminating the last piece of any opponent piece type.
2. Favorable Captures:
   - Capture any enemy piece with RPS advantage.
3. Fallback:
   - Choose a random legal move.
"""

import random
from typing import Any

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

GOALS: dict[int, tuple[int, int]] = {
    1: (8, 8),
    2: (0, 0),
}


def beats(attacker: str, defender: str) -> bool:
    """Determine whether an attacking piece type defeats a defending piece type."""
    return (
        (attacker == "R" and defender == "S")
        or (attacker == "S" and defender == "P")
        or (attacker == "P" and defender == "R")
    )


def count_opponent_pieces(
    board: list[list[dict[str, Any] | None]], opponent: int
) -> dict[str, int]:
    """Count surviving pieces for the opponent grouped by piece type."""
    counts = {"R": 0, "P": 0, "S": 0}
    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell is not None and cell.get("player") == opponent:
                p_type = cell.get("type", "")
                if p_type in counts:
                    counts[p_type] += 1
    return counts


def get_valid_moves(
    board: list[list[dict[str, Any] | None]], my_player: int
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Generate all legal moves available for my_player."""
    moves: list[tuple[tuple[int, int], tuple[int, int]]] = []
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
                            moves.append(((r, c), (nr, nc)))
                        elif target.get("player") != my_player and beats(
                            p_type, target.get("type", "")
                        ):
                            moves.append(((r, c), (nr, nc)))
    return moves


def get_move(
    board: list[list[dict[str, Any] | None]],
    my_player: int,
    history: list[dict[str, Any]],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Determine the next move for the Level 1 Novice bot."""
    legal_moves = get_valid_moves(board, my_player)
    if not legal_moves:
        return ((0, 0), (0, 0))

    target_goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))
    opp_player = 2 if my_player == 1 else 1
    opp_counts = count_opponent_pieces(board, opp_player)

    # Priority 1: Immediate Goal Reach
    for move in legal_moves:
        _, to_pos = move
        if to_pos == target_goal:
            return move

    # Priority 2: Immediate Wipeout Capture
    for move in legal_moves:
        _, to_pos = move
        target_cell = board[to_pos[0]][to_pos[1]]
        if target_cell is not None and target_cell.get("player") == opp_player:
            target_type = target_cell.get("type", "")
            if opp_counts.get(target_type, 0) == 1:
                return move

    # Priority 3: Favorable Captures
    capture_moves: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for move in legal_moves:
        _, to_pos = move
        if board[to_pos[0]][to_pos[1]] is not None:
            capture_moves.append(move)

    if capture_moves:
        return random.choice(capture_moves)

    # Priority 4: Random legal move
    return random.choice(legal_moves)
