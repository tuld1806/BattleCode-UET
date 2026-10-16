"""Unit tests for Elo calculation engine, tournament portal scheduling, bracket seeding, and final scoring."""

import pytest

from server.tournament import (
    apply_elo_change,
    calculate_elo_delta,
    calculate_final_scores,
    generate_bracket,
    is_ffa_portal_open,
)


def test_elo_calculation_win():
    """Verify Elo calculation for a win between equally rated opponents."""
    delta_a, delta_b = calculate_elo_delta(1200, 1200, score=1.0, multiplier=1.0, k=32)
    assert delta_a == 16
    assert delta_b == -16


def test_elo_calculation_loss():
    """Verify Elo calculation for a loss between equally rated opponents."""
    delta_a, delta_b = calculate_elo_delta(1200, 1200, score=0.0, multiplier=1.0, k=32)
    assert delta_a == -16
    assert delta_b == 16


def test_elo_calculation_draw():
    """Verify Elo calculation for a draw between equally rated opponents produces zero delta."""
    delta_a, delta_b = calculate_elo_delta(1200, 1200, score=0.5, multiplier=1.0, k=32)
    assert delta_a == 0
    assert delta_b == 0


def test_elo_with_multiplier():
    """Verify daily multiplier scales Elo deltas proportionally."""
    # Multiplier x = 2.0
    delta_a, delta_b = calculate_elo_delta(1200, 1200, score=1.0, multiplier=2.0, k=32)
    assert delta_a == 32
    assert delta_b == -32

    # Multiplier x = 1.5
    delta_a_15, delta_b_15 = calculate_elo_delta(1200, 1200, score=1.0, multiplier=1.5, k=32)
    assert delta_a_15 == 24
    assert delta_b_15 == -24


def test_elo_rating_difference():
    """Verify higher rated player gains fewer points on win and lower rated player gains more."""
    # High rated (1600) beats lower rated (1200)
    delta_high_win, delta_low_loss = calculate_elo_delta(1600, 1200, score=1.0, multiplier=1.0, k=32)
    assert 0 < delta_high_win < 16
    assert -16 < delta_low_loss < 0

    # Low rated (1200) upsets higher rated (1600)
    delta_upset_win, delta_upset_loss = calculate_elo_delta(1200, 1600, score=1.0, multiplier=1.0, k=32)
    assert delta_upset_win > 16
    assert delta_upset_loss < -16


def test_apply_elo_change_floor():
    """Verify Elo rating cannot drop below 0."""
    assert apply_elo_change(1200, 32) == 1232
    assert apply_elo_change(1200, -50) == 1150
    assert apply_elo_change(10, -50) == 0
    assert apply_elo_change(0, -10) == 0
    assert apply_elo_change(0, 15) == 15


def test_is_ffa_portal_open_override():
    """Verify admin portal open override ignores current time."""
    config = {
        "tournament": {
            "daily_schedule": {
                "start_time": "19:00",
                "end_time": "21:00",
                "is_portal_open": True,
            }
        }
    }
    # Outside scheduled hours, but is_portal_open is True
    assert is_ffa_portal_open(config, current_time_str="12:00") is True
    assert is_ffa_portal_open(config, current_time_str="23:30") is True

    # Flat dictionary support
    flat_config = {
        "daily_schedule": {
            "start_time": "19:00",
            "end_time": "21:00",
            "is_portal_open": True,
        }
    }
    assert is_ffa_portal_open(flat_config, current_time_str="08:00") is True


def test_is_ffa_portal_open_schedule_within_window():
    """Verify portal is open during active scheduled window."""
    config = {
        "tournament": {
            "daily_schedule": {
                "start_time": "19:00",
                "end_time": "21:00",
                "is_portal_open": False,
            }
        }
    }
    assert is_ffa_portal_open(config, current_time_str="19:00") is True
    assert is_ffa_portal_open(config, current_time_str="20:00") is True
    assert is_ffa_portal_open(config, current_time_str="21:00") is True


def test_is_ffa_portal_open_schedule_outside_window():
    """Verify portal is closed outside scheduled hours."""
    config = {
        "tournament": {
            "daily_schedule": {
                "start_time": "19:00",
                "end_time": "21:00",
                "is_portal_open": False,
            }
        }
    }
    assert is_ffa_portal_open(config, current_time_str="18:59") is False
    assert is_ffa_portal_open(config, current_time_str="21:01") is False
    assert is_ffa_portal_open(config, current_time_str="03:00") is False


def test_is_ffa_portal_open_overnight():
    """Verify portal handles overnight schedules spanning midnight."""
    config = {
        "tournament": {
            "daily_schedule": {
                "start_time": "22:00",
                "end_time": "02:00",
                "is_portal_open": False,
            }
        }
    }
    assert is_ffa_portal_open(config, current_time_str="22:30") is True
    assert is_ffa_portal_open(config, current_time_str="01:15") is True
    assert is_ffa_portal_open(config, current_time_str="03:00") is False
    assert is_ffa_portal_open(config, current_time_str="12:00") is False


def test_is_ffa_portal_open_missing_or_invalid_config():
    """Verify graceful handling of empty or missing config objects."""
    assert is_ffa_portal_open({}, current_time_str="20:00") is False
    assert is_ffa_portal_open({"tournament": {}}, current_time_str="20:00") is False
    assert is_ffa_portal_open({"tournament": {"daily_schedule": None}}, current_time_str="20:00") is False


def test_generate_top8_bracket():
    """Verify single-elimination Top 8 bracket pairing order."""
    users = [{"id": i, "username": f"user{i}", "elo": 1500 - i * 20} for i in range(1, 9)]
    bracket = generate_bracket(users)

    assert len(bracket) == 4  # 4 quarter-final matches
    assert bracket[0]["round_name"] == "Quarter-Final"

    # Seed 1 vs Seed 8
    assert bracket[0]["player1_id"] == 1 and bracket[0]["player2_id"] == 8
    assert bracket[0]["player1"]["id"] == 1 and bracket[0]["player2"]["id"] == 8
    assert bracket[0]["match_index"] == 0

    # Seed 4 vs Seed 5
    assert bracket[1]["player1_id"] == 4 and bracket[1]["player2_id"] == 5
    assert bracket[1]["match_index"] == 1

    # Seed 2 vs Seed 7
    assert bracket[2]["player1_id"] == 2 and bracket[2]["player2_id"] == 7
    assert bracket[2]["match_index"] == 2

    # Seed 3 vs Seed 6
    assert bracket[3]["player1_id"] == 3 and bracket[3]["player2_id"] == 6
    assert bracket[3]["match_index"] == 3


def test_generate_top4_bracket():
    """Verify single-elimination Top 4 bracket pairing order."""
    users = [{"id": i, "username": f"user{i}", "elo": 1500 - i * 20} for i in range(1, 5)]
    bracket = generate_bracket(users)

    assert len(bracket) == 2
    assert bracket[0]["round_name"] == "Semi-Final"
    # Seed 1 vs Seed 4
    assert bracket[0]["player1_id"] == 1 and bracket[0]["player2_id"] == 4
    # Seed 2 vs Seed 3
    assert bracket[1]["player1_id"] == 2 and bracket[1]["player2_id"] == 3


def test_generate_top16_bracket():
    """Verify single-elimination Top 16 bracket pairing order."""
    users = [{"id": i, "username": f"user{i}", "elo": 1600 - i * 10} for i in range(1, 17)]
    bracket = generate_bracket(users)

    assert len(bracket) == 8
    assert bracket[0]["round_name"] == "Round of 16"
    # Match 0: 1 vs 16
    assert bracket[0]["player1_id"] == 1 and bracket[0]["player2_id"] == 16
    # Match 1: 8 vs 9
    assert bracket[1]["player1_id"] == 8 and bracket[1]["player2_id"] == 9
    # Match 2: 4 vs 13
    assert bracket[2]["player1_id"] == 4 and bracket[2]["player2_id"] == 13
    # Match 3: 5 vs 12
    assert bracket[3]["player1_id"] == 5 and bracket[3]["player2_id"] == 12


def test_generate_bracket_edge_cases():
    """Verify bracket generation handles unsorted users and insufficient player counts."""
    assert generate_bracket([]) == []
    assert generate_bracket([{"id": 1, "elo": 1200}]) == []

    # Unsorted users by Elo should be automatically sorted by descending Elo
    unsorted_users = [
        {"id": 3, "username": "user3", "elo": 1300},
        {"id": 1, "username": "user1", "elo": 1500},
        {"id": 4, "username": "user4", "elo": 1200},
        {"id": 2, "username": "user2", "elo": 1400},
    ]
    bracket = generate_bracket(unsorted_users)
    assert len(bracket) == 2
    # Seed 1 (user1, elo 1500) vs Seed 4 (user4, elo 1200)
    assert bracket[0]["player1_id"] == 1 and bracket[0]["player2_id"] == 4
    # Seed 2 (user2, elo 1400) vs Seed 3 (user3, elo 1300)
    assert bracket[1]["player1_id"] == 2 and bracket[1]["player2_id"] == 3


def test_calculate_final_scores():
    """Verify combined Elo and bracket score calculation and final ranking."""
    users = [
        {"id": 1, "username": "user1", "elo": 1500},
        {"id": 2, "username": "user2", "elo": 1400},
        {"id": 3, "username": "user3", "elo": 1300},
        {"id": 4, "username": "user4", "elo": 1200},
    ]
    # user 1 is champion (rank 1 -> 100 pts), user 2 is runner-up (rank 2 -> 80 pts),
    # user 3 and 4 reached semi-finals (rank 3, 4 -> 60 pts)
    standings = {1: 1, 2: 2, 3: 3, 4: 4}
    results = calculate_final_scores(users, standings, weight_elo=0.5, weight_bracket=0.5)

    assert len(results) == 4
    # Sorted by final_score descending
    assert results[0]["id"] == 1
    assert results[0]["rank"] == 1
    assert results[0]["final_score"] == 100.0  # 0.5 * 100 + 0.5 * 100

    assert results[1]["id"] == 2
    assert results[1]["rank"] == 2
    assert results[1]["bracket_score"] == 80.0

    assert results[2]["id"] == 3
    assert results[2]["bracket_score"] == 60.0

    assert results[3]["id"] == 4
    assert results[3]["bracket_score"] == 60.0
    assert results[3]["rank"] == 4


def test_calculate_final_scores_with_non_bracket_users():
    """Verify users who didn't play in bracket receive 0 bracket points and rank by Elo."""
    users = [
        {"id": 1, "username": "user1", "elo": 1500},
        {"id": 2, "username": "user2", "elo": 1400},
        {"id": 3, "username": "user3", "elo": 1000},
    ]
    # Only users 1 and 2 participated in final bracket
    standings = {1: 1, 2: 2}
    results = calculate_final_scores(users, standings, weight_elo=0.5, weight_bracket=0.5)

    assert len(results) == 3
    user3_res = next(r for r in results if r["id"] == 3)
    assert user3_res["bracket_score"] == 0.0
    assert user3_res["rank"] == 3


def test_calculate_final_scores_custom_weights_and_direct_points():
    """Verify custom weights and direct point values in bracket_standings."""
    users = [
        {"id": 1, "username": "user1", "elo": 1500},
        {"id": 2, "username": "user2", "elo": 1300},
    ]
    # Direct points passed: 100 pts and 50 pts
    standings = {1: 100, 2: 50}

    # Bracket only (weight_elo=0, weight_bracket=1.0)
    bracket_only = calculate_final_scores(users, standings, weight_elo=0.0, weight_bracket=1.0)
    assert bracket_only[0]["final_score"] == 100.0
    assert bracket_only[1]["final_score"] == 50.0

    # Elo only (weight_elo=1.0, weight_bracket=0.0)
    elo_only = calculate_final_scores(users, standings, weight_elo=1.0, weight_bracket=0.0)
    assert elo_only[0]["final_score"] == 100.0
    assert elo_only[1]["final_score"] == 0.0
