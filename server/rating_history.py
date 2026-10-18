"""Historical Elo rating reconstruction service for participants and top teams."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from server.models import Match, User, GameProfile

PALETTE: List[str] = [
    "#2dd4bf",
    "#38bdf8",
    "#fbbf24",
    "#c084fc",
    "#f43f5e",
    "#ec4899",
    "#a855f7",
    "#3b82f6",
    "#10b981",
    "#f97316",
]


def get_user_rating_history(
    user_id: int,
    db: Session,
    limit: int = 50,
    game_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve chronological Elo rating trajectory for a specific user.

    Args:
        user_id: Unique database identifier of the target user.
        db: Active SQLAlchemy database session.
        limit: Maximum number of chronological match data points to return.

    Returns:
        Dictionary containing user summary metrics and milestone points, or
        None if the user does not exist.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    clamped_limit = max(5, min(100, int(limit)))

    # Determine effective game_id (default to 1 if None)
    effective_game_id = game_id or 1

    # Fetch all completed regular (non-bracket) matches involving this user for the specific game
    all_matches = (
        db.query(Match)
        .filter(
            or_(Match.player1_id == user.id, Match.player2_id == user.id),
            or_(Match.winner_id.isnot(None), Match.win_reason.isnot(None)),
            Match.is_bracket.is_(False),
            (Match.game_id == effective_game_id) | (Match.game_id.is_(None) if effective_game_id == 1 else False),
        )
        .order_by(Match.created_at.asc(), Match.id.asc())
        .all()
    )

    total_matches = len(all_matches)

    # Get GameProfile for this user and game
    profile = (
        db.query(GameProfile)
        .filter(GameProfile.user_id == user.id, GameProfile.game_id == effective_game_id)
        .first()
    )
    profile_elo = profile.elo if profile else 1200

    # Compute peak and lowest Elo using profile Elo and match records
    historical_elos = [profile_elo]
    for match in all_matches:
        if match.player1_id == user.id:
            if match.p1_elo_after is not None:
                historical_elos.append(match.p1_elo_after)
            elif match.p1_elo_before is not None:
                historical_elos.append(match.p1_elo_before)
        elif match.player2_id == user.id:
            if match.p2_elo_after is not None:
                historical_elos.append(match.p2_elo_after)
            elif match.p2_elo_before is not None:
                historical_elos.append(match.p2_elo_before)

    peak_elo = max(historical_elos)
    lowest_elo = min(historical_elos)

    # Slice to latest matches within clamped limit window
    selected_matches = (
        all_matches[-clamped_limit:]
        if total_matches > clamped_limit
        else all_matches
    )

    # Determine initial milestone rating and timestamp based on profile Elo
    initial_elo = profile_elo

    start_created_at = (
        user.created_at.isoformat()
        if user.created_at is not None
        else datetime.now(timezone.utc).isoformat()
    )

    points: List[Dict[str, Any]] = [
        {
            "match_id": 0,
            "created_at": start_created_at,
            "elo": initial_elo,
            "delta": 0,
            "opponent": "Start",
            "win": None,
        }
    ]

    for match in selected_matches:
        match_time = (
            match.created_at.isoformat()
            if match.created_at is not None
            else datetime.now(timezone.utc).isoformat()
        )

        if match.player1_id == user.id:
            if match.p1_elo_after is not None:
                elo = match.p1_elo_after
            elif match.p1_elo_before is not None:
                elo = match.p1_elo_before
            else:
                elo = initial_elo

            delta = (
                match.p1_elo_after - match.p1_elo_before
                if (match.p1_elo_after is not None and match.p1_elo_before is not None)
                else 0
            )
            opponent = match.player2.username if match.player2 else "Unknown"
            win = (match.winner_id == user.id) if match.winner_id is not None else None
        else:
            if match.p2_elo_after is not None:
                elo = match.p2_elo_after
            elif match.p2_elo_before is not None:
                elo = match.p2_elo_before
            else:
                elo = initial_elo

            delta = (
                match.p2_elo_after - match.p2_elo_before
                if (match.p2_elo_after is not None and match.p2_elo_before is not None)
                else 0
            )
            opponent = match.player1.username if match.player1 else "Unknown"
            win = (match.winner_id == user.id) if match.winner_id is not None else None

        points.append({
            "match_id": match.id,
            "created_at": match_time,
            "elo": elo,
            "delta": delta,
            "opponent": opponent,
            "win": win,
        })

    return {
        "user_id": user.id,
        "username": user.username,
        "current_elo": user.elo,
        "peak_elo": peak_elo,
        "lowest_elo": lowest_elo,
        "total_matches": total_matches,
        "points": points,
    }


def get_top_teams_rating_history(
    db: Session,
    top: int = 5,
    limit: int = 30,
    game_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve chronological rating trajectories for the top N active users.

    This version first attempts to use per‑game ``GameProfile`` records. If fewer
    than ``top`` profiles exist (e.g., new users without a profile), it falls back
    to the global ``User.elo`` values to fill the remaining slots. This ensures the
    endpoint always returns the requested number of users.
    """
    clamped_top = max(1, min(10, int(top)))
    clamped_limit = max(5, min(100, int(limit)))
    effective_game_id = game_id or 1

    # Attempt to fetch top per‑game profiles.
    top_profiles = (
        db.query(GameProfile)
        .join(User, GameProfile.user_id == User.id)
        .filter(User.is_admin == False, GameProfile.game_id == effective_game_id)
        .order_by(GameProfile.elo.desc(), GameProfile.wins.desc(), User.id.asc())
        .limit(clamped_top)
        .all()
    )

    users_data: List[Dict[str, Any]] = []
    seen_user_ids = set()
    rank_idx = 1

    def _add_user(user_obj, elo_value, color):
        nonlocal rank_idx
        history = get_user_rating_history(user_obj.id, db, limit=clamped_limit, game_id=effective_game_id)
        points = history["points"] if history is not None else []
        users_data.append({
            "id": user_obj.id,
            "username": user_obj.username,
            "rank": rank_idx,
            "current_elo": elo_value,
            "color": color,
            "points": points,
        })
        seen_user_ids.add(user_obj.id)
        rank_idx += 1

    # Process per‑game profiles first.
    for profile in top_profiles:
        user = db.query(User).filter(User.id == profile.user_id).first()
        if not user:
            continue
        color = PALETTE[(rank_idx - 1) % len(PALETTE)]
        _add_user(user, profile.elo, color)
        if len(users_data) >= clamped_top:
            break

    # Fill remaining slots using global User elo.
    if len(users_data) < clamped_top:
        needed = clamped_top - len(users_data)
        fallback_users = (
            db.query(User)
            .filter(User.is_admin == False, ~User.id.in_(list(seen_user_ids)))
            .order_by(User.elo.desc(), User.id.asc())
            .limit(needed)
            .all()
        )
        for user in fallback_users:
            color = PALETTE[(rank_idx - 1) % len(PALETTE)]
            _add_user(user, user.elo, color)

    return {"users": users_data}

