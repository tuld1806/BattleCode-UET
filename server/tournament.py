"""Tournament logic, Elo calculations, portal scheduling, and bracket management.

This module provides the competitive engine for the Battlecode RPS 9x9 tournament:
1. Daily Elo calculation with dynamic multipliers (x in [1.0, 3.0]) and floor clamping.
2. FFA portal schedule verification supporting manual admin overrides and overnight windows.
3. Standard tournament bracket generation and pairing for Top N playoff seeds.
4. Composite tournament scoring combining normalized group-stage Elo and playoff standings.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ROUND_NAMES: Dict[int, str] = {
    2: "Final",
    4: "Semi-Final",
    8: "Quarter-Final",
    16: "Round of 16",
    32: "Round of 32",
    64: "Round of 64",
}

# Default bracket placement points per tournament spec:
# Champion: 100, Runner-up: 80, Top 4: 60, Top 8: 40, Top 16: 20
DEFAULT_BRACKET_PLACEMENT_POINTS: Dict[int, float] = {
    1: 100.0,
    2: 80.0,
    3: 60.0,
    4: 60.0,
    5: 40.0,
    6: 40.0,
    7: 40.0,
    8: 40.0,
    9: 20.0,
    10: 20.0,
    11: 20.0,
    12: 20.0,
    13: 20.0,
    14: 20.0,
    15: 20.0,
    16: 20.0,
}


def calculate_elo_delta(
    r_a: int,
    r_b: int,
    score: float,
    multiplier: float,
    k: int = 32,
) -> Tuple[int, int]:
    """Calculate Elo delta changes for two players based on match outcome and daily multiplier.

    Formulas:
        E_A = 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / 400.0))
        E_B = 1.0 - E_A
        Delta_A = round(multiplier * k * (score - E_A))
        Delta_B = round(multiplier * k * ((1.0 - score) - E_B))

    Args:
        r_a: Pre-match Elo rating of Player A.
        r_b: Pre-match Elo rating of Player B.
        score: Match score for Player A (1.0 for win, 0.5 for draw, 0.0 for loss).
        multiplier: Daily tournament multiplier x (typically between 1.0 and 3.0).
        k: Base K-factor constant (default is 32).

    Returns:
        A tuple of (delta_a, delta_b) containing integer rating adjustments.
    """
    expected_a = 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / 400.0))
    expected_b = 1.0 - expected_a

    score_b = 1.0 - score

    safe_multiplier = max(0.0, float(multiplier))
    delta_a = round(safe_multiplier * float(k) * (float(score) - expected_a))
    delta_b = round(safe_multiplier * float(k) * (float(score_b) - expected_b))

    return int(delta_a), int(delta_b)


def apply_elo_change(rating: int, delta: int) -> int:
    """Apply an Elo adjustment delta while preventing the rating from dropping below 0.

    Args:
        rating: Current Elo rating.
        delta: Calculated Elo delta adjustment.

    Returns:
        Updated Elo rating clamped to a minimum of 0.
    """
    return max(0, int(rating) + int(delta))


def is_ffa_portal_open(
    config: Dict[str, Any],
    current_time_str: Optional[str] = None,
    db_settings: Optional[Dict[str, Any]] = None,
) -> bool:
    """Determine whether the FFA challenge portal is open for match submissions.

    Checks:
    1. If `db_settings` is provided:
       - Checks `is_portal_open` or `portal_mode`:
         - "true": returns True (force open override).
         - "false": returns False (force closed override).
         - "auto" or None: checks `start_time` and `end_time` (falling back to `config`).
    2. Otherwise, falls back to `config`:
       - If `is_portal_open` is explicitly True, returns True.
       - Checks time window defined by `start_time` and `end_time` (HH:MM).
    3. Evaluates both standard daytime and overnight intervals spanning midnight.

    Args:
        config: Tournament configuration dictionary or subsection.
        current_time_str: Optional time string in 'HH:MM' 24h format. If omitted,
            uses current system local time.
        db_settings: Optional dictionary of dynamic settings from the database.

    Returns:
        True if the portal is open, False otherwise.
    """
    if not isinstance(config, dict):
        t_cfg: Dict[str, Any] = {}
        schedule: Dict[str, Any] = {}
    else:
        # Support nested tournament section or top-level schedule
        t_cfg = config.get("tournament", config)
        if not isinstance(t_cfg, dict):
            schedule = {}
        else:
            schedule = t_cfg.get("daily_schedule", {})
            if not isinstance(schedule, dict):
                schedule = {}

    if db_settings is not None:
        mode = db_settings.get("is_portal_open")
        if mode is None:
            mode = db_settings.get("portal_mode")

        if isinstance(mode, bool):
            if mode is True:
                return True
            else:
                return False
        elif isinstance(mode, str):
            m_lower = mode.strip().lower()
            if m_lower in ("true", "1", "yes"):
                return True
            elif m_lower in ("false", "0", "no"):
                return False
            # "auto" or None falls through to time window evaluation

        start_time = db_settings.get("start_time") or schedule.get("start_time")
        end_time = db_settings.get("end_time") or schedule.get("end_time")
    else:
        # Admin override in config takes priority
        if schedule.get("is_portal_open") is True:
            return True

        start_time = schedule.get("start_time")
        end_time = schedule.get("end_time")

    if not isinstance(start_time, str) or not isinstance(end_time, str):
        return False

    if current_time_str is None:
        current_time_str = datetime.now().strftime("%H:%M")

    if start_time <= end_time:
        return start_time <= current_time_str <= end_time
    else:
        # Overnight schedule spanning past midnight (e.g., 22:00 to 02:00)
        return current_time_str >= start_time or current_time_str <= end_time


def _get_bracket_seed_pairs(num_players: int) -> List[Tuple[int, int]]:
    """Compute standard binary bracket seed pairings for a power of 2 participant count.

    Produces seed arrangements such that top seeds meet as late as possible:
    - 2 players: (1, 2)
    - 4 players: (1, 4), (2, 3)
    - 8 players: (1, 8), (4, 5), (2, 7), (3, 6)
    - 16 players: (1, 16), (8, 9), (4, 13), (5, 12), (2, 15), (7, 10), (3, 14), (6, 11)

    Args:
        num_players: Number of seeded players (power of 2).

    Returns:
        List of (seed1, seed2) 1-based tuples in bracket matchup order.
    """
    if num_players < 2:
        return []

    seeds = [1, 2]
    while len(seeds) < num_players:
        next_seeds: List[int] = []
        total = len(seeds) * 2 + 1
        for s in seeds:
            next_seeds.append(s)
            next_seeds.append(total - s)
        seeds = next_seeds

    return [(seeds[i], seeds[i + 1]) for i in range(0, len(seeds), 2)]


def generate_bracket(top_users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate single-elimination tournament matchups for top-seeded players.

    Seeds players by explicit 'seed' key if available, otherwise sorts descending by 'elo'.
    Pairs players according to standard playoff bracket structures (Top 4, Top 8, Top 16).

    Args:
        top_users: List of user dicts.

    Returns:
        List of matchup dictionaries containing:
        - match_index: 0-indexed position within the round
        - round_name: Descriptive stage name (e.g., 'Quarter-Final', 'Semi-Final')
        - player1: Full user dict for Seed 1
        - player2: Full user dict for Seed 2
        - player1_id: Identifier of Player 1
        - player2_id: Identifier of Player 2
        - seed1: Numeric seed of Player 1
        - seed2: Numeric seed of Player 2
    """
    if not top_users or len(top_users) < 2:
        return []

    # Sort players: prefer explicit 'seed', fallback to descending 'elo'
    if any("seed" in u for u in top_users):
        sorted_users = sorted(top_users, key=lambda u: u.get("seed", float("inf")))
    elif any("elo" in u for u in top_users):
        sorted_users = sorted(top_users, key=lambda u: u.get("elo", 0), reverse=True)
    else:
        sorted_users = list(top_users)

    # Determine largest power of 2 participant count <= len(sorted_users)
    n = 1 << (len(sorted_users).bit_length() - 1)
    if n < 2:
        return []

    seeded_players = sorted_users[:n]
    pairs = _get_bracket_seed_pairs(n)
    round_name = ROUND_NAMES.get(n, f"Round of {n}")

    matchups: List[Dict[str, Any]] = []
    for idx, (s1, s2) in enumerate(pairs):
        p1 = seeded_players[s1 - 1]
        p2 = seeded_players[s2 - 1]
        matchups.append({
            "match_index": idx,
            "round_name": round_name,
            "player1": p1,
            "player2": p2,
            "player1_id": p1.get("id"),
            "player2_id": p2.get("id"),
            "seed1": s1,
            "seed2": s2,
        })

    return matchups


def _resolve_bracket_points(standing_or_points: Optional[int | float]) -> float:
    """Resolve bracket placement standing rank (1..16) or direct points to score value.

    Args:
        standing_or_points: Placement rank or direct point number.

    Returns:
        Resolved bracket point value (float).
    """
    if standing_or_points is None:
        return 0.0

    val = float(standing_or_points)
    if val <= 0:
        return 0.0

    # Values > 16 are treated as direct point values (e.g., 100, 80, 60, 40)
    if val > 16.0:
        return val

    # Integer ranks 1..16 mapped to placement points
    rank_int = int(val)
    return DEFAULT_BRACKET_PLACEMENT_POINTS.get(rank_int, 0.0)


def calculate_final_scores(
    users: List[Dict[str, Any]],
    bracket_standings: Dict[int, int],
    weight_elo: float = 0.5,
    weight_bracket: float = 0.5,
) -> List[Dict[str, Any]]:
    """Calculate combined tournament scores for all users from normalized Elo and bracket standings.

    According to the tournament specification:
    - Bracket scoring:
        - Rank 1 (Champion): 100 points
        - Rank 2 (Runner-up): 80 points
        - Rank 3-4 (Semi-Finalist): 60 points
        - Rank 5-8 (Quarter-Finalist): 40 points
        - Other / non-bracket positions: 0 bracket points
    - Elo normalization:
        - Scaled across participants to a [0.0, 100.0] range via Min-Max normalization.
        - If all participants have equal ratings or only 1 participant exists, defaults to 100.0.
    - Final composite score:
        Score_final = weight_elo * normalized_elo + weight_bracket * bracket_score

    Args:
        users: List of user dictionaries containing at least 'id' and 'elo'.
        bracket_standings: Mapping of user_id to placement rank (1..8) or direct bracket points.
        weight_elo: Weight of normalized Elo component (default 0.5).
        weight_bracket: Weight of bracket placement component (default 0.5).

    Returns:
        List of user score dictionaries sorted by 'final_score' descending, each containing
        'normalized_elo', 'bracket_score', 'final_score', and final 'rank'.
    """
    if not users:
        return []

    elos = [float(u.get("elo", 1200)) for u in users]
    min_elo = min(elos)
    max_elo = max(elos)

    results: List[Dict[str, Any]] = []

    for user in users:
        u_id = user.get("id")
        u_elo = float(user.get("elo", 1200))

        # Min-Max Elo normalization to [0.0, 100.0]
        if max_elo > min_elo:
            normalized_elo = ((u_elo - min_elo) / (max_elo - min_elo)) * 100.0
        else:
            normalized_elo = 100.0 if max_elo > 0 else 0.0

        # Retrieve and resolve bracket placement points
        raw_standing = bracket_standings.get(u_id) if u_id is not None else None
        bracket_score = _resolve_bracket_points(raw_standing)

        final_score = (float(weight_elo) * normalized_elo) + (float(weight_bracket) * bracket_score)

        item = dict(user)
        item["normalized_elo"] = round(normalized_elo, 4)
        item["bracket_score"] = round(bracket_score, 4)
        item["bracket_points"] = round(bracket_score, 4)
        item["final_score"] = round(final_score, 4)
        results.append(item)

    # Sort by final_score descending, tie-breaking by raw elo descending, then id ascending
    results.sort(
        key=lambda r: (r["final_score"], float(r.get("elo", 0)), -int(r.get("id", 0))),
        reverse=True,
    )

    for rank_idx, r in enumerate(results, start=1):
        r["rank"] = rank_idx

    return results
