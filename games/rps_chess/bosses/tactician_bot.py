"""Tactician Benchmark Boss Bot (Level 4).

Strategy:
1. Minimax Search with Alpha-Beta Pruning (2-ply full-width search).
2. Ply 1 (Max): Evaluates all candidate moves available to the bot.
3. Ply 2 (Min): Explores all legal opponent counter-responses to anticipate traps,
   counter-attacks, and immediate blunders.
4. Comprehensive Board Evaluation:
   - Terminal wipeout and goal reach states (+/- 100,000).
   - Material balance and RPS piece count differentials.
   - Vulnerability penalties for piece types with only 1 surviving piece.
   - Goal proximity differential (minimizing our distance to goal while intercepting enemy).
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


def evaluate_board(
    board: list[list[dict[str, Any] | None]],
    my_player: int,
    opp_player: int,
) -> float:
    """Compute static heuristic evaluation score from the perspective of my_player."""
    my_counts = count_pieces(board, my_player)
    opp_counts = count_pieces(board, opp_player)

    my_total = sum(my_counts.values())
    opp_total = sum(opp_counts.values())

    # Check wipeout terminal conditions
    if any(count == 0 for count in opp_counts.values()):
        return 100_000.0
    if any(count == 0 for count in my_counts.values()):
        return -100_000.0

    target_goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))
    home_goal = GOALS.get(opp_player, (0, 0) if my_player == 1 else (8, 8))

    score = 0.0

    # Material differential
    score += (my_total - opp_total) * 120.0

    # Wipeout risk and opportunity
    for p_type in ("R", "P", "S"):
        if opp_counts[p_type] == 1:
            score += 180.0
        elif opp_counts[p_type] == 2:
            score += 40.0

        if my_counts[p_type] == 1:
            score -= 220.0
        elif my_counts[p_type] == 2:
            score -= 50.0

    # Goal proximity differential
    my_min_dist = 9
    opp_min_dist = 9
    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell is not None:
                if cell.get("player") == my_player:
                    d = max(abs(r - target_goal[0]), abs(c - target_goal[1]))
                    if d < my_min_dist:
                        my_min_dist = d
                elif cell.get("player") == opp_player:
                    d = max(abs(r - home_goal[0]), abs(c - home_goal[1]))
                    if d < opp_min_dist:
                        opp_min_dist = d

    score += (9 - my_min_dist) * 30.0
    score -= (9 - opp_min_dist) * 45.0

    return score


def get_move(
    board: list[list[dict[str, Any] | None]],
    my_player: int,
    history: list[dict[str, Any]],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Determine the next move using 2-ply Minimax search with Alpha-Beta pruning."""
    legal_moves = get_valid_moves(board, my_player)
    if not legal_moves:
        return ((0, 0), (0, 0))

    target_goal = GOALS.get(my_player, (8, 8) if my_player == 1 else (0, 0))
    home_goal = GOALS.get(2 if my_player == 1 else 1, (0, 0) if my_player == 1 else (8, 8))
    opp_player = 2 if my_player == 1 else 1

    # Immediate win check at root
    for move in legal_moves:
        _, to_pos = move
        if to_pos == target_goal:
            return move

    # Order moves to improve alpha-beta pruning: captures first, then goal advances
    def move_order_key(m: tuple[tuple[int, int], tuple[int, int]]) -> float:
        fr, fc = m[0]
        tr, tc = m[1]
        weight = 0.0
        if board[tr][tc] is not None:
            weight += 100.0
        dist = max(abs(tr - target_goal[0]), abs(tc - target_goal[1]))
        weight -= dist * 5.0
        return weight

    ordered_moves = sorted(legal_moves, key=move_order_key, reverse=True)

    best_score = -float("inf")
    best_move = ordered_moves[0]
    alpha = -float("inf")
    beta = float("inf")

    opp_counts_root = count_pieces(board, opp_player)

    for my_move in ordered_moves:
        (fr, fc), (tr, tc) = my_move

        # Check for immediate wipeout at root
        target_cell = board[tr][tc]
        if target_cell is not None and target_cell.get("player") == opp_player:
            c_type = target_cell.get("type", "")
            if opp_counts_root.get(c_type, 0) == 1:
                return my_move

        # Apply our move (Ply 1)
        child_board = [row[:] for row in board]
        child_board[tr][tc] = child_board[fr][fc]
        child_board[fr][fc] = None

        # Ply 2 (Opponent minimizes)
        opp_moves = get_valid_moves(child_board, opp_player)
        if not opp_moves:
            # Opponent has no moves
            score = 50_000.0
        else:
            min_score = float("inf")
            opp_counts_child = count_pieces(child_board, my_player)

            for opp_move in opp_moves:
                (ofr, ofc), (otr, otc) = opp_move
                if (otr, otc) == home_goal:
                    min_score = -100_000.0
                    break

                opp_target = child_board[otr][otc]
                if opp_target is not None and opp_target.get("player") == my_player:
                    ot_type = opp_target.get("type", "")
                    if opp_counts_child.get(ot_type, 0) == 1:
                        min_score = -100_000.0
                        break

                eval_board = [row[:] for row in child_board]
                eval_board[otr][otc] = eval_board[ofr][ofc]
                eval_board[ofr][ofc] = None

                score_eval = evaluate_board(eval_board, my_player, opp_player)
                if score_eval < min_score:
                    min_score = score_eval

                if min_score <= alpha:
                    break

            score = min_score

        if score > best_score:
            best_score = score
            best_move = my_move

        if score > alpha:
            alpha = score

    return best_move
