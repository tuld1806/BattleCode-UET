"""Domain 5 Deep Testing: Tournament bracket anomalies, odd player counts, and mathematical extremes."""

import pytest
from server.tournament import (
    calculate_elo_delta,
    generate_bracket,
    calculate_final_scores,
    is_ffa_portal_open,
)


def test_bracket_odd_player_counts():
    """Verify generate_bracket gracefully handles non-power-of-2 player counts."""
    # 3 players -> takes top 2
    users3 = [{"id": i, "elo": 1200 + i * 10} for i in range(3)]
    b3 = generate_bracket(users3)
    assert len(b3) == 1
    assert b3[0]["round_name"] == "Final"

    # 5 players -> takes top 4
    users5 = [{"id": i, "elo": 1200 + i * 10} for i in range(5)]
    b5 = generate_bracket(users5)
    assert len(b5) == 2
    assert b5[0]["round_name"] == "Semi-Final"

    # 7 players -> takes top 4
    users7 = [{"id": i, "elo": 1200 + i * 10} for i in range(7)]
    b7 = generate_bracket(users7)
    assert len(b7) == 2
    assert b7[0]["round_name"] == "Semi-Final"

    # 1 player -> returns empty list
    b1 = generate_bracket([{"id": 1, "elo": 1200}])
    assert b1 == []


def test_elo_extreme_ratings_convergence():
    """Verify Elo calculation behavior with massive rating differentials (e.g. 50 vs 3000)."""
    # Giant beats novice
    delta_giant, delta_novice = calculate_elo_delta(
        r_a=3000,
        r_b=50,
        score=1.0,  # Giant wins
        multiplier=1.0,
        k=32,
    )
    # Expected: giant gains ~0 points, novice loses ~0 points
    assert delta_giant == 0
    assert delta_novice == 0

    # Novice miraculously beats giant
    delta_novice, delta_giant = calculate_elo_delta(
        r_a=50,
        r_b=3000,
        score=1.0,  # Novice wins!
        multiplier=1.0,
        k=32,
    )
    # Expected: novice gains maximum 32 points, giant loses 32 points
    assert delta_novice == 32
    assert delta_giant == -32


def test_negative_multiplier_rejected_or_clamped():
    """Verify that a negative multiplier does not invert Elo reward polarity."""
    # If a player wins (score=1.0), delta must NOT be negative!
    delta_a, delta_b = calculate_elo_delta(
        r_a=1200,
        r_b=1200,
        score=1.0,
        multiplier=-2.0,  # Invalid negative multiplier
        k=32,
    )
    # Delta for winner must be >= 0 (never negative)
    assert delta_a >= 0
    assert delta_b <= 0


def test_final_scores_all_equal_elo():
    """Verify composite final score when all participants have identical Elo."""
    users = [
        {"id": 1, "username": "p1", "elo": 1200},
        {"id": 2, "username": "p2", "elo": 1200},
        {"id": 3, "username": "p3", "elo": 1200},
    ]
    # Standing points: p1=1 (Champion, 100pts), p2=2 (Runner-up, 80pts)
    standings = {1: 1, 2: 2}

    results = calculate_final_scores(users, standings, weight_elo=0.5, weight_bracket=0.5)

    assert len(results) == 3
    # Equal Elo normalizes to 100.0 each
    assert all(r["normalized_elo"] == 100.0 for r in results)
    # Champion has highest final score: 0.5*100 + 0.5*100 = 100
    assert results[0]["id"] == 1
    assert results[0]["final_score"] == 100.0
    assert results[0]["rank"] == 1
