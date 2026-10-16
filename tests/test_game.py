"""Unit tests for the 9x9 Rock-Paper-Scissors Chess Game Engine."""

import pytest
from engine.game import (
    GameState,
    beats,
    coord_name,
    parse_coord,
    notation,
    GOALS,
    TYPES,
    TYPE_ICONS,
)


def test_initial_board_setup():
    """Verify initial 9x9 board pieces, turn counters, and clear middle tiles."""
    game = GameState()
    assert game.turn == 1
    assert game.move_no == 1
    assert game.winner is None
    assert game.win_reason is None
    assert game.wiped_type is None
    assert len(game.history) == 0

    # Player 1 setup on row 0: R, R, R, P, P, P, S, S, S
    expected_p1 = ["R", "R", "R", "P", "P", "P", "S", "S", "S"]
    for col, piece_type in enumerate(expected_p1):
        assert game.board[0][col] == {"type": piece_type, "player": 1}

    # Player 2 setup on row 8: S, S, S, P, P, P, R, R, R
    expected_p2 = ["S", "S", "S", "P", "P", "P", "R", "R", "R"]
    for col, piece_type in enumerate(expected_p2):
        assert game.board[8][col] == {"type": piece_type, "player": 2}

    # Middle rows (1 to 7) must all be None
    for r in range(1, 8):
        for c in range(9):
            assert game.board[r][c] is None

    # Verify initial piece counts
    for t in TYPES:
        assert game.count_pieces(1, t) == 3
        assert game.count_pieces(2, t) == 3


def test_rps_beats():
    """Verify Rock-Paper-Scissors cycle rules and non-winning comparisons."""
    assert beats("R", "S") is True
    assert beats("S", "P") is True
    assert beats("P", "R") is True

    # Same piece does not beat
    assert beats("R", "R") is False
    assert beats("S", "S") is False
    assert beats("P", "P") is False

    # Losing comparisons
    assert beats("R", "P") is False
    assert beats("P", "S") is False
    assert beats("S", "R") is False


def test_coordinate_and_notation_helpers():
    """Verify algebraic coordinate naming, coordinate parsing, and SAN generation."""
    assert coord_name(0, 0) == "a1"
    assert coord_name(8, 8) == "i9"
    assert coord_name(0, 3) == "d1"
    assert coord_name(1, 3) == "d2"

    assert parse_coord("a1") == (0, 0)
    assert parse_coord("i9") == (8, 8)
    assert parse_coord("d2") == (1, 3)

    # Notation without capture
    p1_paper = {"type": "P", "player": 1}
    assert notation(p1_paper, 0, 3, 1, 3, None) == "✋d1-d2"

    # Notation with capture
    p1_rock = {"type": "R", "player": 1}
    p2_scissors = {"type": "S", "player": 2}
    assert notation(p1_rock, 0, 0, 1, 0, p2_scissors) == "✊a1xa2(✌)"


def test_valid_moves_initial_state():
    """Verify initial available moves for Player 1."""
    game = GameState()
    moves_p1 = game.get_valid_moves(player=1)

    # Corner piece (0, 0) Rock can move forward (1, 0) or diagonal (1, 1)
    assert ((0, 0), (1, 0)) in moves_p1
    assert ((0, 0), (1, 1)) in moves_p1

    # Should not include backward or off-board moves
    assert ((0, 0), (-1, 0)) not in moves_p1

    # P1 pieces cannot move onto row 0 tiles occupied by fellow P1 pieces
    assert ((0, 0), (0, 1)) not in moves_p1


def test_combat_and_movement_restrictions():
    """Verify that same type blocks, losing type blocks, and winning type captures."""
    # Create empty board with controlled setup
    board = [[None for _ in range(9)] for _ in range(9)]
    # Place P1 Rock at (4, 4)
    board[4][4] = {"type": "R", "player": 1}
    # Place P2 Scissors at (5, 4) -> Can capture
    board[5][4] = {"type": "S", "player": 2}
    # Place P2 Rock at (5, 5) -> Same type blocks
    board[5][5] = {"type": "R", "player": 2}
    # Place P2 Paper at (4, 5) -> Losing RPS blocks
    board[4][5] = {"type": "P", "player": 2}
    # Place P1 Paper at (3, 4) -> Friendly piece blocks
    board[3][4] = {"type": "P", "player": 1}

    game = GameState(board=board, turn=1)
    valid_moves = game.get_valid_moves(player=1)

    # Capture winning piece
    assert ((4, 4), (5, 4)) in valid_moves
    # Blocked by same type
    assert ((4, 4), (5, 5)) not in valid_moves
    # Blocked by losing RPS
    assert ((4, 4), (4, 5)) not in valid_moves
    # Blocked by friendly piece
    assert ((4, 4), (3, 4)) not in valid_moves
    # Empty squares are reachable
    assert ((4, 4), (3, 3)) in valid_moves
    assert ((4, 4), (4, 3)) in valid_moves


def test_apply_move_normal():
    """Verify applying a legal move updates state, toggles turn, and logs history."""
    game = GameState()
    initial_p1_move = ((0, 3), (1, 3))
    res = game.apply_move(initial_p1_move[0], initial_p1_move[1])

    assert res["ok"] is True
    assert res["winner"] is None
    assert res["win_reason"] is None
    assert res["captured"] is None
    assert res["san"] == "✋d1-d2"

    # Board updated
    assert game.board[0][3] is None
    assert game.board[1][3] == {"type": "P", "player": 1}

    # Turn toggled to Player 2
    assert game.turn == 2
    assert game.move_no == 2
    assert len(game.history) == 1
    assert game.history[0]["san"] == "✋d1-d2"


def test_apply_move_invalid_raises():
    """Verify illegal moves raise ValueError."""
    game = GameState()

    # Move from empty tile
    with pytest.raises(ValueError):
        game.apply_move((4, 4), (4, 5))

    # Move opponent piece on P1 turn
    with pytest.raises(ValueError):
        game.apply_move((8, 0), (7, 0))

    # Move friendly piece onto friendly piece
    with pytest.raises(ValueError):
        game.apply_move((0, 0), (0, 1))

    # Jump multiple squares
    with pytest.raises(ValueError):
        game.apply_move((0, 0), (3, 0))


def test_goal_win_condition_p1():
    """Verify Player 1 wins when entering goal square (8, 8)."""
    board = [[None for _ in range(9)] for _ in range(9)]
    board[7][8] = {"type": "R", "player": 1}
    game = GameState(board=board, turn=1)

    res = game.apply_move((7, 8), (8, 8))
    assert res["ok"] is True
    assert res["winner"] == 1
    assert res["win_reason"] == "goal"
    assert game.winner == 1
    assert game.win_reason == "goal"
    assert game.is_game_over is True

    # No further moves allowed after game is over
    assert game.get_valid_moves(player=2) == []
    with pytest.raises(ValueError):
        game.apply_move((8, 8), (7, 8))


def test_goal_win_condition_p2():
    """Verify Player 2 wins when entering goal square (0, 0)."""
    board = [[None for _ in range(9)] for _ in range(9)]
    board[1][0] = {"type": "S", "player": 2}
    game = GameState(board=board, turn=2)

    res = game.apply_move((1, 0), (0, 0))
    assert res["ok"] is True
    assert res["winner"] == 2
    assert res["win_reason"] == "goal"
    assert game.winner == 2
    assert game.win_reason == "goal"
    assert game.is_game_over is True


def test_wipeout_win_condition():
    """Verify winning when all pieces of any one opponent type are eliminated."""
    board = [[None for _ in range(9)] for _ in range(9)]
    # Player 1 has a Rock
    board[3][3] = {"type": "R", "player": 1}
    # Player 2 has ONLY ONE Scissors (and some Paper and Rock)
    board[4][4] = {"type": "S", "player": 2}
    board[8][3] = {"type": "P", "player": 2}
    board[8][4] = {"type": "R", "player": 2}

    game = GameState(board=board, turn=1)
    assert game.count_pieces(2, "S") == 1

    # P1 Rock captures P2's only Scissors
    res = game.apply_move((3, 3), (4, 4))
    assert res["ok"] is True
    assert res["winner"] == 1
    assert res["win_reason"] == "wipeout"
    assert res["wiped_type"] == "S"
    assert game.winner == 1
    assert game.win_reason == "wipeout"
    assert game.wiped_type == "S"


def test_max_turns_win_condition_piece_advantage():
    """Verify tiebreaker at turn limit awards victory to player with more pieces."""
    board = [[None for _ in range(9)] for _ in range(9)]
    # P1 has 2 pieces
    board[0][0] = {"type": "R", "player": 1}
    board[0][1] = {"type": "P", "player": 1}
    # P2 has 1 piece
    board[8][8] = {"type": "P", "player": 2}

    # Set max_turns=2 and move_no=2 so applying move triggers max_turns check
    game = GameState(board=board, turn=1, move_no=2, max_turns=2)
    res = game.apply_move((0, 0), (1, 0))

    assert res["ok"] is True
    assert res["winner"] == 1
    assert res["win_reason"] == "max_turns"
    assert game.winner == 1
    assert game.win_reason == "max_turns"


def test_max_turns_tiebreaker_draw():
    """Verify tiebreaker at turn limit results in a Draw when piece counts are equal."""
    board = [[None for _ in range(9)] for _ in range(9)]
    board[0][0] = {"type": "R", "player": 1}
    board[8][8] = {"type": "R", "player": 2}

    # Set max_turns=2 and move_no=2
    game = GameState(board=board, turn=1, move_no=2, max_turns=2)
    res = game.apply_move((0, 0), (1, 0))

    assert res["ok"] is True
    assert res["winner"] is None
    assert res["win_reason"] == "max_turns"
    assert game.winner is None
    assert game.win_reason == "max_turns"


def test_coordinate_and_parse_errors():
    """Verify ValueError is raised for invalid coordinate strings and out-of-bound indices."""
    with pytest.raises(ValueError):
        coord_name(-1, 0)
    with pytest.raises(ValueError):
        coord_name(0, 9)

    with pytest.raises(ValueError):
        parse_coord("a")
    with pytest.raises(ValueError):
        parse_coord("z1")
    with pytest.raises(ValueError):
        parse_coord("a0")


def test_get_valid_destinations():
    """Verify get_valid_destinations helper returns correct destination cells."""
    game = GameState()
    # (0, 0) Rock on P1 turn
    dests = game.get_valid_destinations(0, 0)
    assert (1, 0) in dests
    assert (1, 1) in dests
    assert (0, 1) not in dests  # Friendly piece

    # Empty cell has no destinations
    assert game.get_valid_destinations(4, 4) == []

    # Opponent piece has no destinations on P1 turn
    assert game.get_valid_destinations(8, 0) == []

    # Place P2 Scissors next to P1 Rock
    game.board[1][0] = {"type": "S", "player": 2}
    dests_with_capture = game.get_valid_destinations(0, 0)
    assert (1, 0) in dests_with_capture


def test_apply_move_bounds_and_occupied_errors():
    """Verify apply_move validates coordinate bounds and friendly collisions."""
    game = GameState()
    with pytest.raises(ValueError, match="out of bounds"):
        game.apply_move((-1, 0), (0, 0))

    with pytest.raises(ValueError, match="friendly piece"):
        game.apply_move((0, 0), (0, 1))

    # Place P2 Paper at (1, 0), P1 Rock cannot capture it
    game.board[1][0] = {"type": "P", "player": 2}
    with pytest.raises(ValueError, match="Combat blocked"):
        game.apply_move((0, 0), (1, 0))



def test_max_turns_win_condition_p2_advantage():
    """Verify tiebreaker at turn limit awards victory to Player 2 when P2 has more pieces."""
    board = [[None for _ in range(9)] for _ in range(9)]
    # P1 has 1 piece
    board[0][0] = {"type": "R", "player": 1}
    # P2 has 2 pieces
    board[8][7] = {"type": "P", "player": 2}
    board[8][8] = {"type": "P", "player": 2}

    game = GameState(board=board, turn=1, move_no=2, max_turns=2)
    res = game.apply_move((0, 0), (1, 0))

    assert res["ok"] is True
    assert res["winner"] == 2
    assert res["win_reason"] == "max_turns"
    assert game.winner == 2


def test_clone_and_to_dict():
    """Verify serialization to dictionary and deep copy via clone."""
    game = GameState()
    game.apply_move((0, 3), (1, 3))

    serialized = game.to_dict()
    assert serialized["turn"] == 2
    assert serialized["move_no"] == 2
    assert serialized["board"][1][3] == {"type": "P", "player": 1}
    assert len(serialized["history"]) == 1

    cloned = game.clone()
    assert cloned.turn == 2
    assert cloned.move_no == 2
    assert cloned.board[1][3] == {"type": "P", "player": 1}

    # Modifying clone must not alter original
    cloned.board[1][3] = None
    assert game.board[1][3] is not None

