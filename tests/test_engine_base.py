"""Tests for GameEngine abstract base interface."""

import pytest
from engine.base import GameEngine


def test_cannot_instantiate_abstract_game_engine():
    """Verify that GameEngine cannot be instantiated directly without abstract methods."""
    with pytest.raises(TypeError) as excinfo:
        GameEngine()
    assert "Can't instantiate abstract class GameEngine" in str(excinfo.value)


def test_abstract_methods_enforced_on_incomplete_subclass():
    """Verify that incomplete subclasses missing any abstract methods cannot be instantiated."""
    class IncompleteEngine(GameEngine):
        def get_initial_state(self, p1: int, p2: int) -> dict:
            return {}

    with pytest.raises(TypeError) as excinfo:
        IncompleteEngine()
    assert "Can't instantiate abstract class IncompleteEngine" in str(excinfo.value)


def test_concrete_subclass_implements_interface():
    """Verify that a properly implemented subclass can be instantiated and called."""
    class DummyEngine(GameEngine):
        def get_initial_state(self, p1: int, p2: int) -> dict:
            return {"turn": 1, "p1": p1, "p2": p2}

        def get_player_view(self, state: dict, player_id: int) -> dict:
            return {"turn": state["turn"]}

        def apply_action(self, state: dict, player_id: int, action: dict) -> dict:
            return {"turn": state["turn"] + 1, "last_action": action}

        def check_winner(self, state: dict) -> tuple[int | None, str]:
            return None, ""

        def is_action_valid(self, state: dict, player_id: int, action: dict) -> bool:
            return True

        def get_max_turns(self) -> int:
            return 100

        def score_for_tiebreak(self, state: dict, player_id: int) -> float:
            return 0.0

    engine = DummyEngine()
    assert engine.get_max_turns() == 100
    init_state = engine.get_initial_state(1, 2)
    assert init_state["turn"] == 1
    assert engine.is_action_valid(init_state, 1, {"move": "test"}) is True
    assert engine.check_winner(init_state) == (None, "")
