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
from server.models import Bot, GameProfile, Match, TournamentSetting, User
from server.queue import execute_match_job
from server.routes.auth import get_current_user
from server.tournament import is_ffa_portal_open
from server.tournament_config import load_tournament_config

router = APIRouter(prefix="/matches", tags=["matches"])


class ChallengeRequest(BaseModel):
    """Pydantic payload for initiating a challenge match."""
    opponent_id: int
    game_id: Optional[int] = 1


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
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin accounts cannot participate in match challenges.",
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

    if opponent.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot challenge an admin account.",
        )

    target_game_id = payload.game_id or 1

    # Verify both users have active friendly bot submissions for target_game_id
    bot1 = (
        db.query(Bot)
        .filter(
            Bot.user_id == current_user.id,
            or_(Bot.game_id == target_game_id, Bot.game_id == None),  # noqa: E711
            Bot.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not bot1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You do not have an active bot uploaded for this game.",
        )

    bot2 = (
        db.query(Bot)
        .filter(
            Bot.user_id == opponent.id,
            or_(Bot.game_id == target_game_id, Bot.game_id == None),  # noqa: E711
            Bot.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not bot2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Opponent does not have an active bot uploaded for this game.",
        )

    # Get or create GameProfile for both users
    gp1 = db.query(GameProfile).filter(
        GameProfile.user_id == current_user.id,
        GameProfile.game_id == target_game_id,
    ).first()
    if not gp1:
        gp1 = GameProfile(user_id=current_user.id, game_id=target_game_id, elo=current_user.elo or 1200)
        db.add(gp1)
        db.flush()

    gp2 = db.query(GameProfile).filter(
        GameProfile.user_id == opponent.id,
        GameProfile.game_id == target_game_id,
    ).first()
    if not gp2:
        gp2 = GameProfile(user_id=opponent.id, game_id=target_game_id, elo=opponent.elo or 1200)
        db.add(gp2)
        db.flush()

    # Create pending Match record
    match = Match(
        game_id=target_game_id,
        player1_id=current_user.id,
        player2_id=opponent.id,
        bot1_id=bot1.id,
        bot2_id=bot2.id,
        p1_elo_before=gp1.elo,
        p2_elo_before=gp2.elo,
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
        "game_id": target_game_id,
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
    match_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve match execution details and outcome statistics by match ID or identifier."""
    if match_id.isdigit():
        match = db.query(Match).filter(Match.id == int(match_id)).first()
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found.",
            )
        return _serialize_match(match)

    # Check for direct bracket replay file
    safe_name = Path(match_id).name
    replay_file = Path("replays") / (safe_name if safe_name.endswith(".json") else f"{safe_name}.json")
    if not replay_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    try:
        data = json.loads(replay_file.read_text(encoding="utf-8"))
        p1 = data.get("player1") or {}
        p2 = data.get("player2") or {}
        return {
            "id": match_id,
            "player1_id": p1.get("id"),
            "player2_id": p2.get("id"),
            "player1": p1,
            "player2": p2,
            "winner_id": data.get("winner"),
            "win_reason": data.get("win_reason"),
            "total_turns": data.get("total_turns", len(data.get("moves", []))),
            "replay_path": str(replay_file),
            "is_bracket": True,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read match details: {exc}",
        )


@router.get("/{match_id}/replay")
def get_match_replay(
    match_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve full replay JSON data for visualization."""
    if match_id.isdigit():
        match = db.query(Match).filter(Match.id == int(match_id)).first()
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
    else:
        safe_name = Path(match_id).name
        replay_path = Path("replays") / (safe_name if safe_name.endswith(".json") else f"{safe_name}.json")

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
