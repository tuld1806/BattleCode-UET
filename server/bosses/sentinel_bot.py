"""Sentinel Benchmark Boss Bot (Level 3).

Strategy:
1. Immediate Winning Moves:
   - Move directly onto target goal square (8, 8) for Player 1 or (0, 0) for Player 2.
   - Execute a wipeout capture eliminating the last piece of any opponent piece type.
2. Home Territory Defense:
   - Monitors the home goal perimeter ((0, 0) for Player 1, (8, 8) for Player 2).
   - Intercepts and eliminates enemy pieces encroaching on the home base.
3. Scarce Piece Type Hunting:
   - Identifies the opponent's piece type with the lowest surviving count.
   - Prioritizes hunting and eliminating pieces of that scarce type to force a wipeout win.
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

HOME_BASES: dict[int, tuple[int, int]] = {
    1: (0, 0),
    2: (8, 8),
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
    """Determine the next move for the Level 3 Sentinel bot."""
    legal_moves = get_valid_moves(board, my_player)
    if not legal_moves:
        return ((0, 0), (0, 0))

    target_goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))
    home_base = HOME_BASES.get(my_player, (0, 0) if my_player == 1 else (8, 8))
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

    # Determine opponent's scarce piece type (minimum surviving count > 0)
    active_types = {t: c for t, c in opp_counts.items() if c > 0}
    scarce_type: str | None = None
    if active_types:
        scarce_type = min(active_types.keys(), key=lambda t: active_types[t])

    # Locate positions of scarce enemy pieces and enemies near home base
    scarce_positions: list[tuple[int, int]] = []
    encroaching_enemies: list[tuple[int, int]] = []
    home_r, home_c = home_base

    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell is not None and cell.get("player") == opp_player:
                p_type = cell.get("type", "")
                if scarce_type and p_type == scarce_type:
                    scarce_positions.append((r, c))
                dist_to_home = max(abs(r - home_r), abs(c - home_c))
                if dist_to_home <= 3:
                    encroaching_enemies.append((r, c))

    scored_moves: list[tuple[float, tuple[tuple[int, int], tuple[int, int]]]] = []

    for move in legal_moves:
        from_pos, to_pos = move
        fr, fc = from_pos
        tr, tc = to_pos
        piece = board[fr][fc]
        piece_type = piece.get("type", "") if piece else ""

        safe = not is_threatened_after_move(board, from_pos, to_pos, piece_type, opp_player)
        target_cell = board[tr][tc]
        is_capture = target_cell is not None

        score = 0.0
        if safe:
            score += 500.0
        else:
            score -= 500.0

        # Tactical capture evaluations
        if is_capture and target_cell is not None:
            captured_type = target_cell.get("type", "")
            if captured_type == scarce_type:
                score += 800.0
            else:
                score += 300.0

        # Scarce target pursuit bonus (for pieces capable of capturing it)
        if scarce_type and beats(piece_type, scarce_type) and scarce_positions:
            min_dist_before = min(max(abs(fr - sr), abs(fc - sc)) for sr, sc in scarce_positions)
            min_dist_after = min(max(abs(tr - sr), abs(tc - sc)) for sr, sc in scarce_positions)
            if min_dist_after < min_dist_before:
                score += 150.0 * (min_dist_before - min_dist_after)

        # Home defense evaluation: intercept encroaching enemies
        if encroaching_enemies:
            min_encroach_before = min(max(abs(fr - er), abs(fc - ec)) for er, ec in encroaching_enemies)
            min_encroach_after = min(max(abs(tr - er), abs(tc - ec)) for er, ec in encroaching_enemies)
            if min_encroach_after < min_encroach_before:
                score += 200.0 * (min_encroach_before - min_encroach_after)

        # General advancement toward goal if no immediate threats
        d_goal_before = max(abs(fr - target_goal[0]), abs(fc - target_goal[1]))
        d_goal_after = max(abs(tr - target_goal[0]), abs(tc - target_goal[1]))
        score += (d_goal_before - d_goal_after) * 20.0

        scored_moves.append((score, move))

    scored_moves.sort(key=lambda item: item[0], reverse=True)
    return scored_moves[0][1]
