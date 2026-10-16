"""Match challenge creation, listing, details, and replay routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Bot, Match, TournamentSetting, User
from server.queue import execute_match_job
from server.routes.auth import get_current_user
from server.tournament import is_ffa_portal_open
from server.tournament_config import load_tournament_config

router = APIRouter(prefix="/matches", tags=["matches"])


class ChallengeRequest(BaseModel):
    """Pydantic payload for initiating an FFA challenge match."""
    opponent_id: int


def _is_portal_open_now(db: Session) -> bool:
    """Check if the FFA challenge portal is active based on database settings and schedule.

    Queries all TournamentSetting records into a dictionary and delegates evaluation
    to is_ffa_portal_open with dynamic database overrides.
    """
    settings_dict = {s.key: s.value for s in db.query(TournamentSetting).all()}
    config = load_tournament_config()
    return is_ffa_portal_open(config, db_settings=settings_dict)


def _serialize_match(m: Match) -> Dict[str, Any]:
    """Serialize a Match SQLAlchemy entity to a dictionary."""
    return {
        "id": m.id,
        "player1_id": m.player1_id,
        "player2_id": m.player2_id,
        "player1": {"id": m.player1.id, "username": m.player1.username} if m.player1 else None,
        "player2": {"id": m.player2.id, "username": m.player2.username} if m.player2 else None,
        "bot1_id": m.bot1_id,
        "bot2_id": m.bot2_id,
        "winner_id": m.winner_id,
        "win_reason": m.win_reason,
        "total_turns": m.total_turns,
        "p1_elo_before": m.p1_elo_before,
        "p1_elo_after": m.p1_elo_after,
        "p2_elo_before": m.p2_elo_before,
        "p2_elo_after": m.p2_elo_after,
        "replay_path": m.replay_path,
        "is_bracket": m.is_bracket,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.post("/challenge", status_code=status.HTTP_201_CREATED)
def challenge_opponent(
    payload: ChallengeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create an FFA challenge match between the current user and target opponent."""
    if not _is_portal_open_now(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FFA portal is currently closed for ranked matches.",
        )

    if current_user.id == payload.opponent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot challenge yourself.",
        )

    opponent = db.query(User).filter(User.id == payload.opponent_id).first()
    if not opponent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opponent user not found.",
        )

    # Verify both users have active bot submissions
    bot1 = (
        db.query(Bot)
        .filter(Bot.user_id == current_user.id, Bot.is_active == True)  # noqa: E712
        .first()
    )
    if not bot1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You do not have an active bot uploaded.",
        )

    bot2 = (
        db.query(Bot)
        .filter(Bot.user_id == opponent.id, Bot.is_active == True)  # noqa: E712
        .first()
    )
    if not bot2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Opponent does not have an active bot uploaded.",
        )

    # Create pending Match record
    match = Match(
        player1_id=current_user.id,
        player2_id=opponent.id,
        bot1_id=bot1.id,
        bot2_id=bot2.id,
        p1_elo_before=current_user.elo,
        p2_elo_before=opponent.elo,
        is_bracket=False,
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    # Queue async execution in background tasks
    background_tasks.add_task(
        execute_match_job,
        match.id,
        bot1.filepath,
        bot2.filepath,
    )

    return {
        "match_id": match.id,
        "status": "queued",
        "player1_id": current_user.id,
        "player2_id": opponent.id,
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_matches(
    user_id: Optional[int] = Query(None, description="Filter by participant user ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List recent matches with pagination and optional user filtering."""
    query = db.query(Match)
    if user_id is not None:
        query = query.filter(or_(Match.player1_id == user_id, Match.player2_id == user_id))

    matches = query.order_by(Match.created_at.desc()).offset(offset).limit(limit).all()
    return [_serialize_match(m) for m in matches]


@router.get("/{match_id}")
def get_match_detail(
    match_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve match execution details and outcome statistics by match ID."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )
    return _serialize_match(match)


@router.get("/{match_id}/replay")
def get_match_replay(
    match_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve full replay JSON data for visualization."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    if not match.replay_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay is not yet available or match is still running.",
        )

    replay_path = Path(match.replay_path)
    if not replay_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay file could not be found on server disk.",
        )

    try:
        data = json.loads(replay_path.read_text(encoding="utf-8"))
        return data
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read replay data: {exc}",
        )
