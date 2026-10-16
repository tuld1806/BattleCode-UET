"""Historical Elo rating reconstruction service for participants and top teams."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from server.models import Match, User

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

    # Fetch all completed regular (non-bracket) matches involving this user
    all_matches = (
        db.query(Match)
        .filter(
            or_(Match.player1_id == user.id, Match.player2_id == user.id),
            or_(Match.winner_id.isnot(None), Match.win_reason.isnot(None)),
            Match.is_bracket.is_(False),
        )
        .order_by(Match.created_at.asc(), Match.id.asc())
        .all()
    )

    total_matches = len(all_matches)

    # Compute peak and lowest Elo across user's complete match history
    historical_elos = [1200]
    if user.elo is not None:
        historical_elos.append(user.elo)

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

    # Determine initial milestone rating and timestamp
    if selected_matches:
        first_match = selected_matches[0]
        if first_match.player1_id == user.id:
            initial_elo = (
                first_match.p1_elo_before
                if first_match.p1_elo_before is not None
                else 1200
            )
        else:
            initial_elo = (
                first_match.p2_elo_before
                if first_match.p2_elo_before is not None
                else 1200
            )
    else:
        initial_elo = user.elo if user.elo is not None else 1200

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
) -> Dict[str, Any]:
    """Retrieve chronological rating trajectories for the top N active users.

    Args:
        db: Active SQLAlchemy database session.
        top: Number of top teams to retrieve (clamped between 1 and 10).
        limit: Number of match points per team (clamped between 5 and 100).

    Returns:
        Dictionary with a list of user rating trajectory objects.
    """
    clamped_top = max(1, min(10, int(top)))
    clamped_limit = max(5, min(100, int(limit)))

    top_users = (
        db.query(User)
        .order_by(User.elo.desc(), User.wins.desc(), User.id.asc())
        .limit(clamped_top)
        .all()
    )

    users_data: List[Dict[str, Any]] = []
    for rank_idx, user in enumerate(top_users, start=1):
        color = PALETTE[(rank_idx - 1) % len(PALETTE)]
        history = get_user_rating_history(user.id, db, limit=clamped_limit)
        points = history["points"] if history is not None else []

        users_data.append({
            "id": user.id,
            "username": user.username,
            "rank": rank_idx,
            "current_elo": user.elo,
            "color": color,
            "points": points,
        })

    return {"users": users_data}
