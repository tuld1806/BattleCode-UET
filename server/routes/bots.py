"""Bot upload and management API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from engine.sandbox import validate_bot_source
from server.database import get_db
from server.models import Bot, Game, TournamentEnrollment, User
from server.routes.auth import get_current_user

router = APIRouter(prefix="/bots", tags=["bots"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_bot(
    file: UploadFile = File(...),
    game_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Upload a Python bot file, validate with AST sandbox, save to disk, and mark active."""
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot upload player bots.",
        )

    raw_filename = file.filename or "bot.py"
    if not raw_filename.endswith(".py"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a Python (.py) file",
        )

    try:
        content_bytes = await file.read()
        source_code = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content must be valid UTF-8 text",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        )

    # Validate syntax and security rules via AST sandbox
    is_valid, error_msg = validate_bot_source(source_code)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bot validation failed: {error_msg}",
        )

    # Save bot script to disk in bots/ directory
    bots_dir = Path("bots").resolve()
    bots_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(datetime.now(timezone.utc).timestamp())
    safe_stem = Path(raw_filename).stem.replace(" ", "_")
    target_filename = f"user_{current_user.id}_{timestamp}_{safe_stem}.py"
    target_path = bots_dir / target_filename
    target_path.write_text(source_code, encoding="utf-8")

    target_game_id = game_id
    if target_game_id is None:
        default_game = db.query(Game).filter(Game.is_active == True).order_by(Game.id.asc()).first()  # noqa: E712
        target_game_id = default_game.id if default_game else 1

    # Deactivate existing active bots for this user on this game only
    db.query(Bot).filter(
        Bot.user_id == current_user.id,
        Bot.game_id == target_game_id,
        Bot.is_active == True,  # noqa: E712
    ).update({"is_active": False})

    # Create new active Bot record
    new_bot = Bot(
        user_id=current_user.id,
        game_id=target_game_id,
        filename=raw_filename,
        filepath=str(target_path),
        is_active=True,
    )
    db.add(new_bot)
    db.commit()
    db.refresh(new_bot)

    return {
        "id": new_bot.id,
        "filename": new_bot.filename,
        "filepath": new_bot.filepath,
        "is_active": new_bot.is_active,
        "uploaded_at": new_bot.uploaded_at.isoformat(),
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_my_bots(
    game_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all bot submissions uploaded by the authenticated user, optionally filtered by game_id."""
    query = db.query(Bot).filter(Bot.user_id == current_user.id)
    if game_id is not None:
        query = query.filter(Bot.game_id == game_id)
    bots = query.order_by(Bot.uploaded_at.desc()).all()
    results = []
    for b in bots:
        enrollments = db.query(TournamentEnrollment).filter(TournamentEnrollment.bot_id == b.id).all()
        enrolled_tournaments = [e.tournament.name for e in enrollments if e.tournament]
        results.append({
            "id": b.id,
            "filename": b.filename,
            "game_id": b.game_id,
            "is_active": b.is_active,
            "uploaded_at": b.uploaded_at.isoformat(),
            "enrolled_tournaments": enrolled_tournaments,
        })
    return results


@router.get("/active")
def get_active_bot(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve the currently active bot for the authenticated user."""
    bot = (
        db.query(Bot)
        .filter(Bot.user_id == current_user.id, Bot.is_active == True)  # noqa: E712
        .first()
    )
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active bot found",
        )

    return {
        "id": bot.id,
        "filename": bot.filename,
        "is_active": bot.is_active,
        "uploaded_at": bot.uploaded_at.isoformat(),
    }


@router.post("/{bot_id}/activate")
def activate_bot(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a specific previously uploaded bot as the active bot."""
    bot = (
        db.query(Bot)
        .filter(Bot.id == bot_id, Bot.user_id == current_user.id)
        .first()
    )
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    db.query(Bot).filter(
        Bot.user_id == current_user.id,
        Bot.game_id == bot.game_id,
    ).update({"is_active": False})

    bot.is_active = True
    db.commit()
    db.refresh(bot)

    return {
        "id": bot.id,
        "filename": bot.filename,
        "is_active": bot.is_active,
        "uploaded_at": bot.uploaded_at.isoformat(),
    }
