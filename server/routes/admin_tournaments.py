"""Admin API routes for managing tournaments and coordinating playoff brackets."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.bracket_export import generate_bracket_scores_csv
from server.bracket_runner import run_all_bracket_rounds, run_bracket_round
from server.database import get_db
from server.models import BracketMatch, Game, GameProfile, Tournament, TournamentEnrollment, User
from server.routes.admin import AdminConfirmPasswordPayload
from server.routes.auth import get_current_admin
from server.tournament import generate_bracket

router = APIRouter(prefix="/admin/tournaments", tags=["admin-tournaments"])

VALID_TRANSITIONS = {
    "open": {"running", "finished"},
    "running": {"bracket", "finished"},
    "bracket": {"finished"},
    "finished": set(),
}


class CreateTournamentRequest(BaseModel):
    """Schema for creating a new game tournament."""
    game_id: int
    name: str = Field(..., min_length=1, max_length=128)
    ffa_start_time: str = "19:00"
    ffa_end_time: str = "21:00"
    ffa_day_count: int = Field(7, ge=1)
    bracket_top_n: int = Field(8, ge=2)
    elo_multiplier: float = Field(1.0, ge=0.0)
    enrollment_open: bool = True


class SetTournamentStatusRequest(BaseModel):
    """Schema for updating a tournament's progression status."""
    status: str


@router.get("", response_model=List[Dict[str, Any]])
def list_tournaments(
    game_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> List[Dict[str, Any]]:
    """List tournaments, optionally filtered by game_id."""
    query = db.query(Tournament)
    if game_id is not None:
        query = query.filter(Tournament.game_id == game_id)
    tournaments = query.order_by(Tournament.created_at.desc()).all()

    results = []
    for t in tournaments:
        results.append({
            "id": t.id,
            "game_id": t.game_id,
            "game_slug": t.game.slug if t.game else None,
            "name": t.name,
            "status": t.status,
            "ffa_start_time": t.ffa_start_time,
            "ffa_end_time": t.ffa_end_time,
            "ffa_day_count": t.ffa_day_count,
            "bracket_top_n": t.bracket_top_n,
            "elo_multiplier": t.elo_multiplier,
            "enrollment_open": t.enrollment_open,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "enrolled_count": len(t.enrollments),
        })
    return results


@router.post("", response_model=Dict[str, Any])
def create_tournament(
    payload: CreateTournamentRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Create a new tournament scoped to a registered game."""
    game = db.query(Game).filter(Game.id == payload.game_id).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Game with id {payload.game_id} does not exist.",
        )

    tourney = Tournament(
        game_id=payload.game_id,
        name=payload.name.strip(),
        status="open",
        ffa_start_time=payload.ffa_start_time,
        ffa_end_time=payload.ffa_end_time,
        ffa_day_count=payload.ffa_day_count,
        bracket_top_n=payload.bracket_top_n,
        elo_multiplier=payload.elo_multiplier,
        enrollment_open=payload.enrollment_open,
    )
    db.add(tourney)
    db.commit()
    db.refresh(tourney)

    return {
        "id": tourney.id,
        "game_id": tourney.game_id,
        "name": tourney.name,
        "status": tourney.status,
        "ffa_start_time": tourney.ffa_start_time,
        "ffa_end_time": tourney.ffa_end_time,
        "bracket_top_n": tourney.bracket_top_n,
        "elo_multiplier": tourney.elo_multiplier,
        "enrollment_open": tourney.enrollment_open,
    }


@router.get("/{tournament_id}", response_model=Dict[str, Any])
def get_tournament_detail(
    tournament_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Retrieve detailed tournament information and list of enrolled contestants."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )

    enrolled_data = []
    for enr in tourney.enrollments:
        user = enr.user
        bot = enr.bot
        gp = db.query(GameProfile).filter(
            GameProfile.user_id == enr.user_id,
            GameProfile.game_id == tourney.game_id,
        ).first()
        elo = gp.elo if gp else (user.elo if user else 1200)

        enrolled_data.append({
            "enrollment_id": enr.id,
            "user_id": enr.user_id,
            "username": user.username if user else "Unknown",
            "bot_id": enr.bot_id,
            "bot_filename": bot.filename if bot else None,
            "elo": elo,
            "enrolled_at": enr.enrolled_at.isoformat() if enr.enrolled_at else None,
        })

    return {
        "id": tourney.id,
        "game_id": tourney.game_id,
        "game_slug": tourney.game.slug if tourney.game else None,
        "name": tourney.name,
        "status": tourney.status,
        "ffa_start_time": tourney.ffa_start_time,
        "ffa_end_time": tourney.ffa_end_time,
        "ffa_day_count": tourney.ffa_day_count,
        "bracket_top_n": tourney.bracket_top_n,
        "elo_multiplier": tourney.elo_multiplier,
        "enrollment_open": tourney.enrollment_open,
        "created_at": tourney.created_at.isoformat() if tourney.created_at else None,
        "enrolled_count": len(enrolled_data),
        "enrollments": enrolled_data,
    }


@router.post("/{tournament_id}/set-status", response_model=Dict[str, Any])
def set_tournament_status(
    tournament_id: int,
    payload: SetTournamentStatusRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Execute state machine progression on a tournament."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )

    current_status = tourney.status
    target_status = payload.status.strip().lower()

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed and target_status != current_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition from '{current_status}' to '{target_status}'.",
        )

    tourney.status = target_status
    if target_status in ("running", "bracket", "finished"):
        tourney.enrollment_open = False
    db.commit()
    db.refresh(tourney)

    return {
        "id": tourney.id,
        "status": tourney.status,
        "message": f"Tournament status transitioned to '{tourney.status}'.",
    }


@router.post("/{tournament_id}/start-bracket", response_model=Dict[str, Any])
def start_bracket(
    tournament_id: int,
    payload: AdminConfirmPasswordPayload,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Generate playoff bracket from enrolled contestants ordered by GameProfile Elo."""
    if not admin.verify_password(payload.admin_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect admin password. Bracket generation refused.",
        )

    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )

    if tourney.status not in ("open", "running"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start bracket from status '{tourney.status}'.",
        )

    # Collect enrolled players (excluding admin accounts)
    enrollments = db.query(TournamentEnrollment).filter(
        TournamentEnrollment.tournament_id == tournament_id
    ).all()
    enrolled_user_ids = [e.user_id for e in enrollments]

    enrolled_users = (
        db.query(User)
        .filter(User.id.in_(enrolled_user_ids), User.is_admin == False)  # noqa: E712
        .all()
    )

    if len(enrolled_users) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 non-admin enrolled contestants are required to generate bracket matchups.",
        )

    # Query per-game Elo for all enrolled users
    profiles = db.query(GameProfile).filter(
        GameProfile.game_id == tourney.game_id,
        GameProfile.user_id.in_([u.id for u in enrolled_users]),
    ).all()
    elo_map = {p.user_id: p.elo for p in profiles}

    user_dicts = []
    for u in enrolled_users:
        user_dicts.append({
            "id": u.id,
            "username": u.username,
            "elo": elo_map.get(u.id, 1200),
        })

    # Sort descending by GameProfile Elo
    user_dicts.sort(key=lambda x: x["elo"], reverse=True)
    top_candidates = user_dicts[: tourney.bracket_top_n]

    # Generate binary seed pairings
    matchups = generate_bracket(top_candidates)
    if not matchups:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to generate binary bracket matchups with current contestants count.",
        )

    # Persist matchups into BracketMatch rows
    db.query(BracketMatch).filter(BracketMatch.tournament_id == tournament_id).delete()
    for m in matchups:
        bm = BracketMatch(
            tournament_id=tournament_id,
            round_name=m["round_name"],
            match_index=m["match_index"],
            player1_id=m["player1_id"],
            player2_id=m["player2_id"],
            status="pending",
        )
        db.add(bm)

    tourney.status = "bracket"
    tourney.enrollment_open = False
    db.commit()
    db.refresh(tourney)

    return {
        "status": "bracket",
        "message": f"Bracket started with {len(top_candidates)} contestants.",
        "matchups": matchups,
    }


@router.post("/{tournament_id}/bracket/run-round")
def tournament_run_bracket_round(
    tournament_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Execute current pending round matches in a tournament bracket."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )
    return run_bracket_round(db, tournament_id=tournament_id)


@router.post("/{tournament_id}/bracket/run-all")
def tournament_run_all_bracket_rounds(
    tournament_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Sequentially execute all remaining rounds for a tournament until finished."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )
    return run_all_bracket_rounds(db, tournament_id=tournament_id)


@router.get("/{tournament_id}/export-scores")
def tournament_export_scores(
    tournament_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Response:
    """Export composite final scores for a specific tournament as an Excel UTF-8-SIG CSV attachment."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )
    csv_data = generate_bracket_scores_csv(db, tournament_id=tournament_id)
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=tournament_{tournament_id}_final_scores.csv"
        },
    )


public_router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@public_router.get("/{tournament_id}/bracket", response_model=Dict[str, Any])
def get_public_tournament_bracket(
    tournament_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve all bracket matches for a given tournament."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )
    matches = (
        db.query(BracketMatch)
        .filter(BracketMatch.tournament_id == tournament_id)
        .order_by(BracketMatch.id.asc())
        .all()
    )
    return {
        "tournament_id": tournament_id,
        "tournament_name": tourney.name,
        "status": tourney.status,
        "matches": [
            {
                "id": m.id,
                "tournament_id": m.tournament_id,
                "round_name": m.round_name,
                "match_index": m.match_index,
                "player1_id": m.player1_id,
                "player1_username": m.player1.username if m.player1 else None,
                "player2_id": m.player2_id,
                "player2_username": m.player2.username if m.player2 else None,
                "score_p1": m.score_p1,
                "score_p2": m.score_p2,
                "winner_id": m.winner_id,
                "status": m.status,
            }
            for m in matches
        ],
    }

