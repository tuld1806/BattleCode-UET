"""RPS Chess 9x9 Game Engine Plugin.

Wraps the core 9x9 Rock-Paper-Scissors Chess game rules into the standard
GameEngine interface for multi-game execution.
"""

from __future__ import annotations

import copy
from typing import Any

from engine.base import GameEngine as BaseGameEngine
from engine.game import (
    DIRECTIONS,
    GOALS,
    MAX_TURNS,
    GameState,
    create_initial_board,
    notation,
)


class GameEngine(BaseGameEngine):
    """Concrete GameEngine implementation for 9x9 RPS Chess."""

    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        """Initialize the RPS Chess engine with turn limit."""
        self._max_turns = max_turns

    def get_initial_state(self, player1_id: int, player2_id: int) -> dict[str, Any]:
        """Return the initial game state as a serializable dictionary."""
        initial_board = create_initial_board()
        state = GameState(
            board=initial_board,
            turn=1,
            move_no=1,
            max_turns=self._max_turns,
        )
        data = state.to_dict()
        data["player1_id"] = player1_id
        data["player2_id"] = player2_id
        return data

    def get_player_view(self, state: dict[str, Any], player_id: int) -> dict[str, Any]:
        """Return a player's perspective of the board.

        RPS Chess has complete information (no Fog of War), so this returns
        an isolated deep copy of the current state.
        """
        return copy.deepcopy(state)

    def is_action_valid(self, state: dict[str, Any], player_id: int, action: Any) -> bool:
        """Validate whether a candidate move action is legal."""
        if not isinstance(action, (list, tuple)) or len(action) != 2:
            return False

        from_pos, to_pos = action[0], action[1]
        if not isinstance(from_pos, (list, tuple)) or len(from_pos) != 2:
            return False
        if not isinstance(to_pos, (list, tuple)) or len(to_pos) != 2:
            return False

        norm_move = ((int(from_pos[0]), int(from_pos[1])), (int(to_pos[0]), int(to_pos[1])))

        game = GameState(
            board=state["board"],
            turn=state["turn"],
            move_no=state["move_no"],
            max_turns=state.get("max_turns", self._max_turns),
        )
        valid_moves = game.get_valid_moves(player_id)
        return norm_move in valid_moves

    def apply_action(self, state: dict[str, Any], player_id: int, action: Any) -> dict[str, Any]:
        """Apply a player's move action and return the updated game state."""
        from_pos, to_pos = action[0], action[1]
        norm_from = (int(from_pos[0]), int(from_pos[1]))
        norm_to = (int(to_pos[0]), int(to_pos[1]))

        game = GameState(
            board=state["board"],
            turn=state["turn"],
            move_no=state["move_no"],
            max_turns=state.get("max_turns", self._max_turns),
        )
        game.history = copy.deepcopy(state.get("history", []))
        game.winner = state.get("winner")
        game.win_reason = state.get("win_reason", "")
        game.wiped_type = state.get("wiped_type")

        game.apply_move(norm_from, norm_to)

        new_state = game.to_dict()
        new_state["player1_id"] = state.get("player1_id", 1)
        new_state["player2_id"] = state.get("player2_id", 2)
        return new_state

    def check_winner(self, state: dict[str, Any]) -> tuple[int | None, str]:
        """Check if the game has concluded and return winner and reason string."""
        return state.get("winner"), state.get("win_reason") or ""


    def get_max_turns(self) -> int:
        """Return the maximum allowed turns for RPS Chess."""
        return self._max_turns

    def score_for_tiebreak(self, state: dict[str, Any], player_id: int) -> float:
        """Calculate piece count tiebreaker score for the given player."""
        game = GameState(
            board=state["board"],
            turn=state["turn"],
            move_no=state["move_no"],
            max_turns=state.get("max_turns", self._max_turns),
        )
        return float(game.count_pieces(player_id))


# Backward compatibility alias
RPSChessEngine = GameEngine
