"""Rusher Benchmark Boss Bot (Level 2).

Strategy:
1. Immediate Winning Moves:
   - Move directly onto target goal square (8, 8) for Player 1 or (0, 0) for Player 2.
   - Execute a wipeout capture eliminating the last piece of any opponent piece type.
2. Chebyshev Distance Minimization:
   - Aggressively advances friendly pieces towards the opponent's goal.
   - Strictly prioritizes safe moves that do not step into immediate enemy retaliation.
   - Breaks ties by preferring captures and moves closest to the goal.
"""

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


def is_threatened_after_move(
    board: list[list[dict[str, Any] | None]],
    from_pos: tuple[int, int],
    to_pos: tuple[int, int],
    piece_type: str,
    opponent: int,
) -> bool:
    """Check if moving to to_pos leaves the piece adjacent to an opponent that beats it."""
    tr, tc = to_pos
    for dr, dc in DIRECTIONS:
        nr, nc = tr + dr, tc + dc
        if 0 <= nr < 9 and 0 <= nc < 9:
            if (nr, nc) == from_pos:
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
    """Determine the next move for the Level 2 Rusher bot."""
    legal_moves = get_valid_moves(board, my_player)
    if not legal_moves:
        return ((0, 0), (0, 0))

    target_goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))
    target_r, target_c = target_goal
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

    # Priority 3: Rank moves based on Chebyshev distance to goal and safety
    scored_moves: list[tuple[float, tuple[tuple[int, int], tuple[int, int]]]] = []

    for move in legal_moves:
        from_pos, to_pos = move
        fr, fc = from_pos
        tr, tc = to_pos
        piece = board[fr][fc]
        piece_type = piece.get("type", "") if piece else ""

        d_before = max(abs(fr - target_r), abs(fc - target_c))
        d_after = max(abs(tr - target_r), abs(tc - target_c))
        safe = not is_threatened_after_move(board, from_pos, to_pos, piece_type, opp_player)
        is_capture = board[tr][tc] is not None

        # Higher score is better
        score = 0.0
        if safe:
            score += 1000.0
        else:
            score -= 1000.0

        # Strong bonus for reducing distance
        score += (d_before - d_after) * 80.0
        # Closeness bonus
        score += (8.0 - d_after) * 20.0
        # Capture bonus
        if is_capture:
            score += 40.0

        scored_moves.append((score, move))

    scored_moves.sort(key=lambda item: item[0], reverse=True)
    return scored_moves[0][1]
