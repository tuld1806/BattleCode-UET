"""Standard GameEngine Abstract Base Interface for Multi-Game Support.

Every game plugin (e.g. RPS Chess, Cyber-Grid, Stellar Armada) must implement
the GameEngine interface defined in this module to interact with the tournament
platform and subprocess match runner.
"""

from __future__ import annotations

import abc
from typing import Any


class GameEngine(abc.ABC):
    """Abstract interface defining the contract for game plugins."""

    @abc.abstractmethod
    def get_initial_state(self, player1_id: int, player2_id: int) -> dict[str, Any]:
        """Return the initial game state as a JSON-serializable dictionary.

        Args:
            player1_id: Unique identifier for Player 1.
            player2_id: Unique identifier for Player 2.

        Returns:
            Dictionary representing the starting game state.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_player_view(self, state: dict[str, Any], player_id: int) -> dict[str, Any]:
        """Return a filtered view of the game state for a specific player.

        Useful for Fog of War or hidden information games.

        Args:
            state: Full game state dictionary.
            player_id: Identifier of the player observing the state.

        Returns:
            Filtered state dictionary visible to player_id.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def apply_action(self, state: dict[str, Any], player_id: int, action: Any) -> dict[str, Any]:
        """Apply a player's move/action and return the updated game state.

        Args:
            state: Current game state dictionary.
            player_id: Player taking the action.
            action: Action data structure (move coordinates, command, etc.).

        Returns:
            New game state dictionary resulting from applying the action.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def check_winner(self, state: dict[str, Any]) -> tuple[int | None, str]:
        """Check if the game has concluded and return the winner and reason.

        Args:
            state: Current game state dictionary.

        Returns:
            Tuple of (winner_id or None, reason_string).
            Common reason strings include: 'goal', 'wipeout', 'timeout', 'score',
            'draw', 'max_turns', 'invalid_move', 'error'.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def is_action_valid(self, state: dict[str, Any], player_id: int, action: Any) -> bool:
        """Validate whether a candidate action is legal in the current state.

        Args:
            state: Current game state dictionary.
            player_id: Player attempting the action.
            action: Candidate action data structure.

        Returns:
            True if the action is legal, False otherwise.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_max_turns(self) -> int:
        """Return the maximum number of turns before forced game termination.

        Returns:
            Integer maximum turn limit.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def score_for_tiebreak(self, state: dict[str, Any], player_id: int) -> float:
        """Calculate a tiebreaker score for the given player at turn limit.

        Args:
            state: Terminal game state dictionary.
            player_id: Player to evaluate.

        Returns:
            Numeric score where higher values represent superior performance.
        """
        raise NotImplementedError
