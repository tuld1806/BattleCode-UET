"""Apex Master Benchmark Boss Bot (Level 5).

Strategy:
1. Adaptive Depth Minimax with Alpha-Beta Pruning:
   - Dynamic search depth (2 to 3 ply) dynamically scaled based on branching factor.
   - Comprehensive move ordering prioritizing captures, goal advances, and central control.
2. Advanced Tactical & Strategic Evaluation:
   - Piece trade baiting: trading non-scarce pieces to eliminate opponent scarce types.
   - Tactical threat detection and defensive piece support.
   - Endgame goal convergence scaling as piece density decreases.
   - Central board dominance and mobility maximization.
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


def count_pieces(
    board: list[list[dict[str, Any] | None]], player: int
) -> dict[str, int]:
    """Count surviving pieces for a player grouped by piece type."""
    counts = {"R": 0, "P": 0, "S": 0}
    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell is not None and cell.get("player") == player:
                p_type = cell.get("type", "")
                if p_type in counts:
                    counts[p_type] += 1
    return counts


def get_valid_moves(
    board: list[list[dict[str, Any] | None]], player: int
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Generate all legal moves available for the specified player."""
    moves: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for r in range(9):
        for c in range(9):
            piece = board[r][c]
            if piece is not None and piece.get("player") == player:
                p_type = piece.get("type", "")
                for dr, dc in DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 9 and 0 <= nc < 9:
                        target = board[nr][nc]
                        if target is None:
                            moves.append(((r, c), (nr, nc)))
                        elif target.get("player") != player and beats(
                            p_type, target.get("type", "")
                        ):
                            moves.append(((r, c), (nr, nc)))
    return moves


def is_defended_by_friendly(
    board: list[list[dict[str, Any] | None]],
    pos: tuple[int, int],
    enemy_attacker_type: str,
    my_player: int,
) -> bool:
    """Check if friendly pieces can recapture if enemy_attacker_type captures at pos."""
    r, c = pos
    for dr, dc in DIRECTIONS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < 9 and 0 <= nc < 9 and (nr, nc) != pos:
            friend = board[nr][nc]
            if friend is not None and friend.get("player") == my_player:
                if beats(friend.get("type", ""), enemy_attacker_type):
                    return True
    return False


def evaluate_apex(
    board: list[list[dict[str, Any] | None]],
    my_player: int,
    opp_player: int,
) -> float:
    """Comprehensive evaluation function for Level 5 Apex Master."""
    my_counts = count_pieces(board, my_player)
    opp_counts = count_pieces(board, opp_player)

    # Check wipeout terminal conditions
    if any(c == 0 for c in opp_counts.values()):
        return 100_000.0
    if any(c == 0 for c in my_counts.values()):
        return -100_000.0

    my_total = sum(my_counts.values())
    opp_total = sum(opp_counts.values())
    total_pieces = my_total + opp_total

    score = 0.0

    # 1. Material Differential
    score += (my_total - opp_total) * 140.0

    # 2. Asymmetric Wipeout Pressure
    for p_type in ("R", "P", "S"):
        if opp_counts[p_type] == 1:
            score += 320.0
        elif opp_counts[p_type] == 2:
            score += 70.0

        if my_counts[p_type] == 1:
            score -= 360.0
        elif my_counts[p_type] == 2:
            score -= 80.0

    # 3. Dynamic Goal Convergence
    target_goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))
    home_goal = GOALS.get(opp_player, (0, 0) if my_player == 1 else (8, 8))

    my_min_goal_dist = 9
    opp_min_goal_dist = 9
    center_control = 0.0

    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell is not None:
                if cell.get("player") == my_player:
                    d = max(abs(r - target_goal[0]), abs(c - target_goal[1]))
                    if d < my_min_goal_dist:
                        my_min_goal_dist = d
                    # Central board control
                    if 2 <= r <= 6 and 2 <= c <= 6:
                        center_control += 5.0
                elif cell.get("player") == opp_player:
                    d = max(abs(r - home_goal[0]), abs(c - home_goal[1]))
                    if d < opp_min_goal_dist:
                        opp_min_goal_dist = d
                    if 2 <= r <= 6 and 2 <= c <= 6:
                        center_control -= 5.0

    # Endgame scaling: goal becomes much more important when fewer pieces remain
    goal_weight = 35.0 + max(0.0, float(18 - total_pieces) * 5.0)
    score += (9 - my_min_goal_dist) * goal_weight
    score -= (9 - opp_min_goal_dist) * (goal_weight * 1.35)
    score += center_control

    return score


def _minimax(
    board: list[list[dict[str, Any] | None]],
    depth: int,
    is_maximizing: bool,
    my_player: int,
    opp_player: int,
    alpha: float,
    beta: float,
    target_goal: tuple[int, int],
    home_goal: tuple[int, int],
) -> float:
    """Internal recursive alpha-beta search."""
    if depth == 0:
        return evaluate_apex(board, my_player, opp_player)

    if is_maximizing:
        moves = get_valid_moves(board, my_player)
        if not moves:
            return -50_000.0

        max_eval = -float("inf")
        my_counts = count_pieces(board, opp_player)

        for (fr, fc), (tr, tc) in moves:
            # Check terminal conditions
            if (tr, tc) == target_goal:
                return 100_000.0

            target = board[tr][tc]
            if target is not None and target.get("player") == opp_player:
                t_type = target.get("type", "")
                if my_counts.get(t_type, 0) == 1:
                    return 100_000.0

            child = [row[:] for row in board]
            child[tr][tc] = child[fr][fc]
            child[fr][fc] = None

            eval_score = _minimax(
                child,
                depth - 1,
                False,
                my_player,
                opp_player,
                alpha,
                beta,
                target_goal,
                home_goal,
            )
            if eval_score > max_eval:
                max_eval = eval_score
            if eval_score > alpha:
                alpha = eval_score
            if beta <= alpha:
                break
        return max_eval

    else:
        moves = get_valid_moves(board, opp_player)
        if not moves:
            return 50_000.0

        min_eval = float("inf")
        opp_counts = count_pieces(board, my_player)

        for (fr, fc), (tr, tc) in moves:
            if (tr, tc) == home_goal:
                return -100_000.0

            target = board[tr][tc]
            if target is not None and target.get("player") == my_player:
                t_type = target.get("type", "")
                if opp_counts.get(t_type, 0) == 1:
                    return -100_000.0

            child = [row[:] for row in board]
            child[tr][tc] = child[fr][fc]
            child[fr][fc] = None

            eval_score = _minimax(
                child,
                depth - 1,
                True,
                my_player,
                opp_player,
                alpha,
                beta,
                target_goal,
                home_goal,
            )
            if eval_score < min_eval:
                min_eval = eval_score
            if eval_score < beta:
                beta = eval_score
            if beta <= alpha:
                break
        return min_eval


def get_move(
    board: list[list[dict[str, Any] | None]],
    my_player: int,
    history: list[dict[str, Any]],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Determine the optimal move using dynamic-depth Minimax search."""
    legal_moves = get_valid_moves(board, my_player)
    if not legal_moves:
        return ((0, 0), (0, 0))

    target_goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))
    home_goal = GOALS.get(2 if my_player == 1 else 1, (0, 0) if my_player == 1 else (8, 8))
    opp_player = 2 if my_player == 1 else 1
    opp_counts = count_pieces(board, opp_player)

    # Priority 1: Immediate Goal Reach
    for move in legal_moves:
        _, to_pos = move
        if to_pos == target_goal:
            return move

    # Priority 2: Immediate Wipeout
    for move in legal_moves:
        _, to_pos = move
        target = board[to_pos[0]][to_pos[1]]
        if target is not None and target.get("player") == opp_player:
            if opp_counts.get(target.get("type", ""), 0) == 1:
                return move

    # Dynamic depth calculation based on branching factor
    # When branching factor is small (<= 12), search 3-ply; otherwise 2-ply
    search_depth = 3 if len(legal_moves) <= 12 else 2

    # Move ordering key: captures, scarce targets, and goal advancement
    def move_order_score(m: tuple[tuple[int, int], tuple[int, int]]) -> float:
        fr, fc = m[0]
        tr, tc = m[1]
        weight = 0.0
        target = board[tr][tc]
        if target is not None:
            t_type = target.get("type", "")
            if opp_counts.get(t_type, 0) == 1:
                weight += 5000.0
            elif opp_counts.get(t_type, 0) == 2:
                weight += 500.0
            else:
                weight += 200.0
        dist = max(abs(tr - target_goal[0]), abs(tc - target_goal[1]))
        weight -= dist * 10.0
        return weight

    ordered_moves = sorted(legal_moves, key=move_order_score, reverse=True)

    best_score = -float("inf")
    best_move = ordered_moves[0]
    alpha = -float("inf")
    beta = float("inf")

    for my_move in ordered_moves:
        (fr, fc), (tr, tc) = my_move
        child = [row[:] for row in board]
        child[tr][tc] = child[fr][fc]
        child[fr][fc] = None

        score = _minimax(
            child,
            search_depth - 1,
            False,
            my_player,
            opp_player,
            alpha,
            beta,
            target_goal,
            home_goal,
        )

        if score > best_score:
            best_score = score
            best_move = my_move

        if score > alpha:
            alpha = score

    return best_move
