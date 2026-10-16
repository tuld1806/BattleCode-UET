"""Domain 1 Deep Testing: Game engine extremes, boundary conditions, and combat hierarchies."""

import pytest
from engine.game import GameState, beats, coord_name, notation


def test_coord_name_boundaries():
    """Verify coordinate naming at all corners and boundary bounds."""
    assert coord_name(0, 0) == "a1"
    assert coord_name(0, 8) == "i1"
    assert coord_name(8, 0) == "a9"
    assert coord_name(8, 8) == "i9"
    with pytest.raises(ValueError):
        coord_name(-1, 0)
    with pytest.raises(ValueError):
        coord_name(0, 9)


def test_beats_rock_paper_scissors_exhaustive():
    """Verify all 9 permutations of RPS combat comparison."""
    # Strict wins
    assert beats("R", "S") is True
    assert beats("S", "P") is True
    assert beats("P", "R") is True

    # Losses
    assert beats("S", "R") is False
    assert beats("P", "S") is False
    assert beats("R", "P") is False

    # Ties (same type cannot beat)
    assert beats("R", "R") is False
    assert beats("P", "P") is False
    assert beats("S", "S") is False


def test_clone_complete_isolation():
    """Verify that cloning a GameState creates an independent deep copy."""
    state = GameState()
    clone = state.clone()

    # Modify clone board
    clone.board[0][0] = None
    assert state.board[0][0] is not None
    assert state.board[0][0]["type"] == "R"

    # Modify clone history
    clone.history.append({"test": 123})
    assert len(state.history) == 0


def test_same_piece_type_and_inferior_combat_blocked():
    """Verify that same type pieces block each other, and inferior pieces cannot attack."""
    state = GameState()
    # Clear board and set up exact scenario
    for r in range(9):
        for c in range(9):
            state.board[r][c] = None

    # Place P1 Rock at (4, 4)
    state.board[4][4] = {"type": "R", "player": 1}
    # Place P2 Rock at (4, 5) -> same type blocks
    state.board[4][5] = {"type": "R", "player": 2}
    # Place P2 Paper at (5, 5) -> Paper beats Rock, so Rock cannot capture Paper
    state.board[5][5] = {"type": "P", "player": 2}
    # Place P2 Scissors at (3, 4) -> Rock beats Scissors, so Rock CAN capture Scissors
    state.board[3][4] = {"type": "S", "player": 2}

    valid_moves = state.get_valid_moves(1)
    
    # Moving into P2 Rock (4, 5) must NOT be valid
    assert ((4, 4), (4, 5)) not in valid_moves
    # Moving into P2 Paper (5, 5) must NOT be valid (Rock loses to Paper)
    assert ((4, 4), (5, 5)) not in valid_moves
    # Moving into P2 Scissors (3, 4) MUST be valid (Rock beats Scissors)
    assert ((4, 4), (3, 4)) in valid_moves


def test_apply_invalid_moves_raise_exceptions():
    """Verify apply_move rejects out of turn, invalid origins, or illegal steps."""
    state = GameState()

    # Empty origin square
    with pytest.raises(ValueError):
        state.apply_move((4, 4), (4, 5))

    # Wrong player's turn (P2 piece moved when turn == 1)
    with pytest.raises(ValueError):
        state.apply_move((8, 0), (7, 0))

    # Stepping more than 1 square (illegal king jump)
    with pytest.raises(ValueError):
        state.apply_move((0, 0), (2, 0))


def test_turn_200_goal_precedence():
    """Verify that reaching goal on turn 200 awards 'goal' win rather than 'max_turns'."""
    state = GameState()
    # Fast forward move_no to 200
    state.move_no = 200
    state.turn = 1

    # Place P1 Paper adjacent to goal (8, 8) (P2 starts with Rock at (8, 8), so Paper beats Rock)
    state.board[7][7] = {"type": "P", "player": 1}
    state.apply_move((7, 7), (8, 8))

    assert state.winner == 1
    assert state.win_reason == "goal"


def test_stalemate_zero_moves_detected_cleanly():
    """Verify get_valid_moves returns empty list if all pieces are completely trapped."""
    state = GameState()
    for r in range(9):
        for c in range(9):
            state.board[r][c] = None

    # Corner piece P1 Rock at (0, 0)
    state.board[0][0] = {"type": "R", "player": 1}
    # Trapped by friendly pieces on all adjacent squares
    state.board[0][1] = {"type": "R", "player": 1}
    state.board[1][0] = {"type": "R", "player": 1}
    state.board[1][1] = {"type": "R", "player": 1}

    # Surround (0, 1), (1, 0), (1, 1) so no pieces can move
    # (Surround with P2 Paper so Rock cannot move anywhere)
    for r in range(3):
        for c in range(3):
            if (r, c) not in [(0, 0), (0, 1), (1, 0), (1, 1)]:
                state.board[r][c] = {"type": "P", "player": 2}

    moves_corner = [m for m in state.get_valid_moves(1) if m[0] == (0, 0)]
    assert moves_corner == []


def test_coord_non_integer_inputs_rejected():
    """Verify that passing non-integer coordinates (floats, strings) raises TypeError or ValueError."""
    state = GameState()
    with pytest.raises((TypeError, ValueError)):
        state.apply_move((0.5, 1.2), (2, 3))  # type: ignore

    with pytest.raises((TypeError, ValueError)):
        state.apply_move(("a", "b"), (1, 2))  # type: ignore

    with pytest.raises((TypeError, ValueError)):
        coord_name(1.5, 2.5)  # type: ignore

    with pytest.raises((TypeError, ValueError)):
        coord_name("0", "0")  # type: ignore

