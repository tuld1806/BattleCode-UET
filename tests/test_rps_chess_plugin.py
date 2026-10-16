"""Tests for RPS Chess 9x9 plugin engine implementation."""

import pytest
from games.rps_chess.engine import RPSChessEngine


def test_rps_chess_engine_lifecycle():
    """Verify that RPSChessEngine satisfies the GameEngine interface contract."""
    engine = RPSChessEngine()
    assert engine.get_max_turns() == 200

    state = engine.get_initial_state(1, 2)
    assert state["turn"] == 1
    assert "board" in state
    assert len(state["board"]) == 9
    assert len(state["board"][0]) == 9

    # Player 1 views board
    view = engine.get_player_view(state, 1)
    assert "board" in view

    # Check move legality: ((0, 3), (1, 3)) should be valid for initial state
    valid = engine.is_action_valid(state, 1, ((0, 3), (1, 3)))
    assert valid is True

    # Apply action
    new_state = engine.apply_action(state, 1, ((0, 3), (1, 3)))
    assert new_state["turn"] == 2
    assert new_state["board"][1][3] is not None
    assert new_state["board"][0][3] is None

    # Check winner
    winner, reason = engine.check_winner(new_state)
    assert winner is None
    assert reason == ""

    # Check tiebreak score calculation
    score1 = engine.score_for_tiebreak(new_state, 1)
    score2 = engine.score_for_tiebreak(new_state, 2)
    assert isinstance(score1, (int, float))
    assert isinstance(score2, (int, float))
