"""Leaderboard rankings and user profile API routes."""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Bot, Match, User
from server.rating_history import (
    get_top_teams_rating_history,
    get_user_rating_history,
)

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])



@router.get("", response_model=List[Dict[str, Any]])
def get_leaderboard(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Retrieve current Elo leaderboard sorted in descending rating order."""
    users = (
        db.query(User)
        .order_by(User.elo.desc(), User.wins.desc(), User.id.asc())
        .all()
    )

    rankings: List[Dict[str, Any]] = []
    for rank_idx, user in enumerate(users, start=1):
        has_active = any(bot.is_active for bot in user.bots)
        rankings.append({
            "rank": rank_idx,
            "id": user.id,
            "username": user.username,
            "elo": user.elo,
            "wins": user.wins,
            "losses": user.losses,
            "draws": user.draws,
            "has_active_bot": has_active,
        })

    return rankings


@router.get("/rating-history")
def get_top_rating_history(
    top: int = Query(5, ge=1, le=10),
    limit: int = Query(30, ge=5, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve chronological rating trajectories for the top N ranked users."""
    return get_top_teams_rating_history(db=db, top=top, limit=limit)


@router.get("/users/{user_id}/rating-history")
def get_single_user_rating_history(
    user_id: int,
    limit: int = Query(50, ge=5, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve chronological Elo trajectory for a specific user ID."""
    history = get_user_rating_history(user_id=user_id, db=db, limit=limit)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return history


@router.get("/users/{user_id}")
def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve participant public profile, statistics, active bot, and recent match history."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    active_bot = (
        db.query(Bot)
        .filter(Bot.user_id == user.id, Bot.is_active == True)  # noqa: E712
        .first()
    )

    recent_matches = (
        db.query(Match)
        .filter((Match.player1_id == user.id) | (Match.player2_id == user.id))
        .order_by(Match.created_at.desc())
        .limit(10)
        .all()
    )

    total_matches = user.wins + user.losses + user.draws
    win_rate = round((user.wins / total_matches) * 100.0, 1) if total_matches > 0 else 0.0

    return {
        "id": user.id,
        "username": user.username,
        "elo": user.elo,
        "wins": user.wins,
        "losses": user.losses,
        "draws": user.draws,
        "total_matches": total_matches,
        "win_rate": win_rate,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "active_bot": {
            "id": active_bot.id,
            "filename": active_bot.filename,
            "uploaded_at": active_bot.uploaded_at.isoformat() if active_bot.uploaded_at else None,
        } if active_bot else None,
        "recent_matches": [
            {
                "id": m.id,
                "winner_id": m.winner_id,
                "win_reason": m.win_reason,
                "total_turns": m.total_turns,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in recent_matches
        ],
    }
