"""Admin API routes for managing and uploading game plugins."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from engine.plugin_loader import PluginSecurityError, PluginValidationError
from server.boss_manager import deploy_boss, retract_boss
from server.database import get_db
from server.game_registry import GameRegistry
from server.models import Game, Tournament, User
from server.routes.auth import get_current_admin

router = APIRouter(prefix="/admin/games", tags=["admin-games"])


class BossActionRequest(BaseModel):
    boss_slug: str


class ContextCreateTournamentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    ffa_start_time: str = "19:00"
    ffa_end_time: str = "21:00"
    ffa_day_count: int = Field(7, ge=1)
    bracket_top_n: int = Field(8, ge=2)
    elo_multiplier: float = Field(1.0, ge=0.0)
    enrollment_open: bool = True


@router.get("", response_model=List[Dict[str, Any]])
def list_all_games(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> List[Dict[str, Any]]:
    """Retrieve full catalog of registered games for administrative management."""
    games = db.query(Game).order_by(Game.id.asc()).all()
    results = []
    for g in games:
        results.append({
            "id": g.id,
            "slug": g.slug,
            "display_name": g.display_name,
            "description_md": g.description_md,
            "is_active": g.is_active,
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "tournaments_count": len(g.tournaments),
        })
    return results


@router.post("/upload")
async def upload_game_plugin(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Upload, AST-scan, unpack, and register a new game plugin zip archive."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .zip archive packages are permitted.",
        )

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        registry = GameRegistry.get_instance()
        game = registry.register_from_zip(tmp_path, db)
        return {
            "status": "success",
            "message": f"Game plugin '{game.display_name}' registered successfully.",
            "game": {
                "id": game.id,
                "slug": game.slug,
                "display_name": game.display_name,
                "is_active": game.is_active,
            },
        }
    except (PluginSecurityError, PluginValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    finally:
        if tmp_path.is_file():
            try:
                tmp_path.unlink()
            except Exception:
                pass


@router.post("/{slug}/toggle")
def toggle_game_active_status(
    slug: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Toggle the is_active status of a game plugin."""
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found.",
        )

    game.is_active = not game.is_active
    db.commit()
    db.refresh(game)
    return {
        "slug": game.slug,
        "is_active": game.is_active,
        "message": f"Game '{game.slug}' is now {'active' if game.is_active else 'inactive'}.",
    }


@router.post("/{slug}/bosses/deploy")
def deploy_game_boss(
    slug: str,
    payload: BossActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Deploy a benchmark boss bot in the arena for a specific game."""
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found.",
        )
    try:
        return deploy_boss(db, payload.boss_slug, game_id=game.id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )


@router.post("/{slug}/bosses/retract")
def retract_game_boss(
    slug: str,
    payload: BossActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Retract a benchmark boss bot from a specific game arena."""
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found.",
        )
    try:
        return retract_boss(db, payload.boss_slug, game_id=game.id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )


@router.post("/{slug}/tournaments")
def create_game_tournament(
    slug: str,
    payload: ContextCreateTournamentRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Create a new tournament scoped to the specified game slug."""
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found.",
        )

    tourney = Tournament(
        game_id=game.id,
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
