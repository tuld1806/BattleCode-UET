"""Core 9x9 Rock-Paper-Scissors Chess Game Logic Engine.

This module provides the complete game simulation for the 9x9 RPS chess variant:
- Board coordinates: 9x9 matrix where row 0 = rank 1, row 8 = rank 9; col 0 = file a, col 8 = file i.
- Pieces: 'R' (Rock), 'P' (Paper), 'S' (Scissors).
- Combat rules: Rock beats Scissors, Scissors beats Paper, Paper beats Rock.
- Movement rules: 1 square in any of the 8 directions (like a King in chess).
- Win conditions:
    1. Reaching the opponent's home goal square (P1 -> i9 (8,8); P2 -> a1 (0,0)).
    2. Wiping out all 3 pieces of any single opponent piece type.
    3. Reaching turn 200 tiebreaker (highest surviving piece count wins; tie results in draw).
"""

from __future__ import annotations

import copy
from typing import Any


# Coordinate and board definitions
FILES: list[str] = ["a", "b", "c", "d", "e", "f", "g", "h", "i"]
RANKS: list[str] = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

# Piece types and UI iconography
TYPES: list[str] = ["R", "P", "S"]
TYPE_NAMES: dict[str, str] = {
    "R": "Rock",
    "P": "Paper",
    "S": "Scissors",
}
TYPE_ICONS: dict[str, str] = {
    "R": "✊",
    "P": "✋",
    "S": "✌",
}

# Goal squares for each player: P1 targets (8, 8) [i9], P2 targets (0, 0) [a1]
GOALS: dict[int, tuple[int, int]] = {
    1: (8, 8),
    2: (0, 0),
}

# Maximum turns before turn-limit tiebreaker triggers
MAX_TURNS: int = 200

# 8 directions for king-like movement
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


def beats(a: str, b: str) -> bool:
    """Check if piece type 'a' beats piece type 'b' in Rock-Paper-Scissors.

    Args:
        a: Attacking piece type ('R', 'P', or 'S').
        b: Defending piece type ('R', 'P', or 'S').

    Returns:
        True if 'a' beats 'b', False otherwise.
    """
    return (
        (a == "R" and b == "S")
        or (a == "S" and b == "P")
        or (a == "P" and b == "R")
    )


def coord_name(row: int, col: int) -> str:
    """Convert matrix coordinates (row, col) to standard algebraic square name (e.g., 'a1', 'i9').

    Args:
        row: Integer row in range [0, 8].
        col: Integer column in range [0, 8].

    Returns:
        Square coordinate string like 'a1' or 'i9'.

    Raises:
        ValueError: If row or col is outside the 0-8 range.
    """
    if not (0 <= row < 9 and 0 <= col < 9):
        raise ValueError(f"Coordinate ({row}, {col}) out of 9x9 board bounds.")
    return FILES[col] + RANKS[row]


def parse_coord(name: str) -> tuple[int, int]:
    """Parse standard algebraic notation string (e.g. 'a1', 'i9') to matrix coordinates (row, col).

    Args:
        name: Coordinate string like 'a1'.

    Returns:
        Tuple of (row, col).

    Raises:
        ValueError: If coordinate format or values are invalid.
    """
    if len(name) != 2:
        raise ValueError(f"Invalid coordinate format '{name}'. Expected 2 characters.")
    col_str, rank_str = name[0].lower(), name[1]
    if col_str not in FILES or rank_str not in RANKS:
        raise ValueError(f"Coordinate '{name}' is out of 9x9 board bounds.")
    return RANKS.index(rank_str), FILES.index(col_str)


def notation(
    piece: dict[str, Any],
    fr: int,
    fc: int,
    tr: int,
    tc: int,
    captured: dict[str, Any] | None = None,
) -> str:
    """Generate Short Algebraic Notation (SAN) for a move.

    Format:
        Non-capture: [Icon][from]-[to], e.g. '✋d1-d2'
        Capture:     [Icon][from]x[to]([CapturedIcon]), e.g. '✊a1xa2(✌)'

    Args:
        piece: Dict representing moving piece with 'type' key.
        fr: From row index.
        fc: From col index.
        tr: To row index.
        tc: To col index.
        captured: Optional dict representing captured piece with 'type' key.

    Returns:
        Formatted SAN notation string.
    """
    tag = TYPE_ICONS[piece["type"]]
    from_name = coord_name(fr, fc)
    to_name = coord_name(tr, tc)
    if captured:
        captured_tag = TYPE_ICONS[captured["type"]]
        return f"{tag}{from_name}x{to_name}({captured_tag})"
    return f"{tag}{from_name}-{to_name}"


def create_initial_board() -> list[list[dict[str, Any] | None]]:
    """Construct the initial 9x9 board configuration.

    Row 0 (Player 1): R, R, R, P, P, P, S, S, S
    Row 8 (Player 2): S, S, S, P, P, P, R, R, R
    Rows 1-7: Empty (None)

    Returns:
        9x9 list of lists containing piece dicts or None.
    """
    board: list[list[dict[str, Any] | None]] = [
        [None for _ in range(9)] for _ in range(9)
    ]
    p1_row = ["R", "R", "R", "P", "P", "P", "S", "S", "S"]
    p2_row = ["S", "S", "S", "P", "P", "P", "R", "R", "R"]

    for col in range(9):
        board[0][col] = {"type": p1_row[col], "player": 1}
        board[8][col] = {"type": p2_row[col], "player": 2}

    return board


class GameState:
    """Represents the complete state and rule evaluation of a 9x9 RPS chess match."""

    def __init__(
        self,
        board: list[list[dict[str, Any] | None]] | None = None,
        turn: int = 1,
        move_no: int = 1,
        max_turns: int = MAX_TURNS,
    ) -> None:
        """Initialize game state.

        Args:
            board: Optional 9x9 board matrix. If None, default initial board is used.
            turn: Current player turn (1 or 2). Defaults to 1.
            move_no: Move sequence number (starts at 1). Defaults to 1.
            max_turns: Maximum number of moves before tiebreaker triggers. Defaults to 200.
        """
        if board is None:
            self.board = create_initial_board()
        else:
            self.board = copy.deepcopy(board)

        self.turn: int = turn
        self.move_no: int = move_no
        self.max_turns: int = max_turns

        self.winner: int | None = None
        self.win_reason: str | None = None  # 'goal', 'wipeout', 'max_turns'
        self.wiped_type: str | None = None  # 'R', 'P', 'S' if win_reason == 'wipeout'
        self.history: list[dict[str, Any]] = []

    @property
    def is_game_over(self) -> bool:
        """Check if the game has concluded."""
        return self.winner is not None or self.win_reason is not None

    def count_pieces(self, player: int, piece_type: str | None = None) -> int:
        """Count surviving pieces for a player, optionally filtered by type.

        Args:
            player: 1 or 2.
            piece_type: 'R', 'P', 'S', or None to count all pieces.

        Returns:
            Number of matching pieces remaining on the board.
        """
        count = 0
        for r in range(9):
            for c in range(9):
                cell = self.board[r][c]
                if cell and cell["player"] == player:
                    if piece_type is None or cell["type"] == piece_type:
                        count += 1
        return count

    def get_valid_destinations(self, row: int, col: int) -> list[tuple[int, int]]:
        """Get all legal target coordinates for a piece located at (row, col).

        Args:
            row: Row index of piece.
            col: Col index of piece.

        Returns:
            List of valid (target_row, target_col) coordinates.
        """
        piece = self.board[row][col]
        if piece is None or piece["player"] != self.turn or self.is_game_over:
            return []

        valid: list[tuple[int, int]] = []
        for dr, dc in DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < 9 and 0 <= nc < 9:
                target = self.board[nr][nc]
                if target is None:
                    # Move to empty square
                    valid.append((nr, nc))
                elif target["player"] != piece["player"] and beats(
                    piece["type"], target["type"]
                ):
                    # Capture opponent piece with winning RPS type
                    valid.append((nr, nc))
        return valid

    def get_valid_moves(
        self, player: int | None = None
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Generate all legal moves available for the specified player.

        Args:
            player: Player number (1 or 2). Defaults to current turn if None.

        Returns:
            List of ((from_row, from_col), (to_row, to_col)) tuples.
        """
        if self.is_game_over:
            return []

        active_player = self.turn if player is None else player
        moves: list[tuple[tuple[int, int], tuple[int, int]]] = []

        for r in range(9):
            for c in range(9):
                piece = self.board[r][c]
                if piece and piece["player"] == active_player:
                    for dr, dc in DIRECTIONS:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 9 and 0 <= nc < 9:
                            target = self.board[nr][nc]
                            if target is None:
                                moves.append(((r, c), (nr, nc)))
                            elif target["player"] != active_player and beats(
                                piece["type"], target["type"]
                            ):
                                moves.append(((r, c), (nr, nc)))
        return moves

    def apply_move(
        self, from_pos: tuple[int, int], to_pos: tuple[int, int]
    ) -> dict[str, Any]:
        """Apply a move to the board, update state, check win conditions, and switch turn.

        Args:
            from_pos: (from_row, from_col) tuple.
            to_pos: (to_row, to_col) tuple.

        Returns:
            Dictionary containing move result details:
                - ok: bool
                - winner: int | None
                - win_reason: str | None ('goal', 'wipeout', 'max_turns')
                - wiped_type: str | None ('R', 'P', 'S')
                - captured: dict | None
                - san: str
                - from: tuple[int, int]
                - to: tuple[int, int]
                - piece: str
                - move_no: int

        Raises:
            ValueError: If game is already over or the move violates any game rules.
        """
        if self.is_game_over:
            raise ValueError("Cannot apply move: Game is already over.")

        fr, fc = from_pos
        tr, tc = to_pos

        if not (0 <= fr < 9 and 0 <= fc < 9 and 0 <= tr < 9 and 0 <= tc < 9):
            raise ValueError(f"Move coordinates out of bounds: {from_pos} -> {to_pos}")

        piece = self.board[fr][fc]
        if piece is None:
            raise ValueError(f"No piece found at {from_pos}.")
        if piece["player"] != self.turn:
            raise ValueError(
                f"Cannot move opponent piece at {from_pos}. Current turn is Player {self.turn}."
            )

        # Validate step distance (must be exactly 1 step in 8 directions)
        dr, dc = tr - fr, tc - fc
        if not (abs(dr) <= 1 and abs(dc) <= 1 and (dr != 0 or dc != 0)):
            raise ValueError(f"Illegal move distance from {from_pos} to {to_pos}.")

        target = self.board[tr][tc]
        if target is not None:
            if target["player"] == piece["player"]:
                raise ValueError(f"Square {to_pos} is occupied by friendly piece.")
            if not beats(piece["type"], target["type"]):
                raise ValueError(
                    f"Combat blocked: {piece['type']} does not beat {target['type']} at {to_pos}."
                )

        # Move execution
        captured = self.board[tr][tc]
        self.board[tr][tc] = piece
        self.board[fr][fc] = None

        san = notation(piece, fr, fc, tr, tc, captured)
        current_player = piece["player"]

        # Win Condition 1: Reaching opponent's home goal square
        goal = GOALS[current_player]
        if (tr, tc) == goal:
            self.winner = current_player
            self.win_reason = "goal"

        # Win Condition 2: Wiping out all pieces of any opponent type
        if self.winner is None and captured is not None:
            opp_player = captured["player"]
            if self.count_pieces(opp_player, captured["type"]) == 0:
                self.winner = current_player
                self.win_reason = "wipeout"
                self.wiped_type = captured["type"]

        # Win Condition 3: Reaching maximum allowed turns tiebreaker
        if self.winner is None and self.move_no >= self.max_turns:
            p1_count = self.count_pieces(1)
            p2_count = self.count_pieces(2)
            self.win_reason = "max_turns"
            if p1_count > p2_count:
                self.winner = 1
            elif p2_count > p1_count:
                self.winner = 2
            else:
                self.winner = None  # Draw

        # Append move record to game history
        current_move_no = self.move_no
        move_record = {
            "turn": current_move_no,
            "player": current_player,
            "from": from_pos,
            "to": to_pos,
            "piece": piece["type"],
            "captured": captured["type"] if captured else None,
            "san": san,
        }
        self.history.append(move_record)

        # Increment move count and switch turn if match is still ongoing
        self.move_no += 1
        if not self.is_game_over:
            self.turn = 2 if self.turn == 1 else 1

        return {
            "ok": True,
            "winner": self.winner,
            "win_reason": self.win_reason,
            "wiped_type": self.wiped_type,
            "captured": captured,
            "san": san,
            "from": from_pos,
            "to": to_pos,
            "piece": piece["type"],
            "move_no": current_move_no,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete game state into a dictionary.

        Returns:
            Dictionary representing current game snapshot.
        """
        return {
            "board": copy.deepcopy(self.board),
            "turn": self.turn,
            "move_no": self.move_no,
            "max_turns": self.max_turns,
            "winner": self.winner,
            "win_reason": self.win_reason,
            "wiped_type": self.wiped_type,
            "history": copy.deepcopy(self.history),
        }

    def clone(self) -> GameState:
        """Create an independent deep copy of the current game state.

        Returns:
            A cloned GameState instance with isolated memory.
        """
        new_state = GameState(
            board=self.board,
            turn=self.turn,
            move_no=self.move_no,
            max_turns=self.max_turns,
        )
        new_state.winner = self.winner
        new_state.win_reason = self.win_reason
        new_state.wiped_type = self.wiped_type
        new_state.history = copy.deepcopy(self.history)
        return new_state
