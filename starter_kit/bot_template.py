"""Starter Bot Template for 9x9 Rock-Paper-Scissors Chess.

This template provides a minimal working bot that generates legal moves.
You can use this as a starting point to develop your own custom strategies.

Game Rules Summary:
-------------------
1. Board Representation:
   - 9x9 matrix where row 0 is Rank 1 (Player 1 home rank) and row 8 is Rank 9 (Player 2 home rank).
   - Column 0 is File 'a' (leftmost) and column 8 is File 'i' (rightmost).
   - Coordinates are 0-indexed tuples: (row, col) from (0, 0) to (8, 8).

2. Pieces:
   - 'R': Rock
   - 'P': Paper
   - 'S': Scissors

3. Combat Rules (Rock-Paper-Scissors):
   - Rock ('R') beats Scissors ('S')
   - Scissors ('S') beats Paper ('P')
   - Paper ('P') beats Rock ('R')
   - Pieces cannot move to a square occupied by a friendly piece.
   - Pieces can move to an enemy square ONLY IF they defeat that enemy piece under RPS rules.
   - Moves to empty squares (None) are always legal if within 1 step.

4. Movement:
   - Any piece can move 1 step in any of the 8 directions (like a King in chess):
     up, down, left, right, and 4 diagonals.

5. Win Conditions:
   - Goal Reach: Player 1 wins by moving any piece onto (8, 8).
                 Player 2 wins by moving any piece onto (0, 0).
   - Wipeout: A player wins if ALL 3 pieces of ANY single opponent piece type are eliminated.
   - Turn Limit: If turn 200 is reached, the player with the highest surviving piece count wins.
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

# Home goal destination coordinates for each player
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


def get_valid_moves(
    board: list[list[dict[str, Any] | None]], my_player: int
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Find all legal moves available for the specified player on the current board.

    Args:
        board: 9x9 matrix representing the board.
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
                            # Destination square is empty
                            valid_moves.append(((r, c), (nr, nc)))
                        elif target.get("player") != my_player and beats(p_type, target.get("type", "")):
                            # Destination square has an enemy piece that our piece defeats
                            valid_moves.append(((r, c), (nr, nc)))

    return valid_moves


def get_move(
    board: list[list[dict[str, Any] | None]],
    my_player: int,
    history: list[dict[str, Any]],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Determine the next move for the bot.

    This function is called by the competition engine on every turn.

    Args:
        board: 9x9 matrix where each cell board[r][c] is either None (empty)
               or a dictionary: {'type': 'R' | 'P' | 'S', 'player': 1 | 2}.
        my_player: 1 (Player 1 - Red, starting at row 0) or
                   2 (Player 2 - Blue, starting at row 8).
        history: Chronological list of past moves. Each entry is a dict:
                 {'player': int, 'from': (r, c), 'to': (r, c), 'san': str, ...}

    Returns:
        A tuple ((from_row, from_col), (to_row, to_col)) specifying the chosen move.

    Raises:
        ValueError: If no legal moves are available.
    """
    valid_moves = get_valid_moves(board, my_player)
    if not valid_moves:
        raise ValueError("No legal moves available.")

    # Strategy:
    # 1. Check if any move immediately reaches the goal.
    goal = GOALS.get(my_player)
    for move in valid_moves:
        if move[1] == goal:
            return move

    # 2. Prefer moves advancing forward towards the opponent's side of the board.
    # Player 1 (starting at row 0) moves forward by increasing row index.
    # Player 2 (starting at row 8) moves forward by decreasing row index.
    forward_moves: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for move in valid_moves:
        from_pos, to_pos = move
        if my_player == 1 and to_pos[0] > from_pos[0]:
            forward_moves.append(move)
        elif my_player == 2 and to_pos[0] < from_pos[0]:
            forward_moves.append(move)

    if forward_moves:
        return random.choice(forward_moves)

    # 3. Fallback: Choose a random legal move
    return random.choice(valid_moves)
