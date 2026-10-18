"""Admin API routes for managing and uploading game plugins."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from engine.plugin_loader import PluginSecurityError, PluginValidationError
from server.database import get_db
from server.game_registry import GameRegistry
from server.models import Game, User
from server.routes.auth import get_current_admin

router = APIRouter(prefix="/admin/games", tags=["admin-games"])


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
