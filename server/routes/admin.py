"""Tournament administration, setting configuration, and bracket generation routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.boss_manager import deploy_boss, get_all_bosses_status, retract_boss
from server.database import get_db
from server.models import Bot, BracketMatch, TournamentSetting, User
from server.routes.auth import get_current_admin
from server.tournament import generate_bracket, is_ffa_portal_open
from server.tournament_config import load_tournament_config

router = APIRouter(prefix="/admin", tags=["admin"])


class BossDeployRequest(BaseModel):
    """Pydantic payload for deploying or retracting a benchmark boss bot."""
    boss_slug: str
    action: str = "deploy"


class UpdateSettingsRequest(BaseModel):
    """Pydantic payload for updating tournament dynamic parameters."""
    is_portal_open: Optional[Union[bool, str]] = None
    portal_mode: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    daily_multiplier_x: Optional[float] = Field(None, ge=0.1, le=10.0)
    current_day: Optional[int] = Field(None, ge=1)
    total_days: Optional[int] = Field(None, ge=1)
    max_turns: Optional[int] = Field(None, ge=10, le=1000)
    turn_timeout_seconds: Optional[float] = Field(None, ge=0.1, le=10.0)


def _get_setting_row(db: Session, key: str) -> TournamentSetting | None:
    """Retrieve setting row from database by key."""
    return db.query(TournamentSetting).filter(TournamentSetting.key == key).first()


def _upsert_setting(db: Session, key: str, value: str) -> None:
    """Insert or update a tournament setting key-value pair."""
    setting = _get_setting_row(db, key)
    if setting:
        setting.value = value
    else:
        setting = TournamentSetting(key=key, value=value)
        db.add(setting)


def _get_all_settings_dict(db: Session) -> Dict[str, Any]:
    """Retrieve full configuration merged with database overrides."""
    config = load_tournament_config()
    t_cfg = config.get("tournament", {})
    daily_cfg = t_cfg.get("daily_schedule", {})
    elo_cfg = t_cfg.get("elo", {})
    rules_cfg = t_cfg.get("match_rules", {})
    bracket_cfg = t_cfg.get("final_bracket", {})

    settings_map: Dict[str, str] = {
        s.key: s.value for s in db.query(TournamentSetting).all()
    }

    start_time = settings_map.get("start_time", daily_cfg.get("start_time", "19:00"))
    end_time = settings_map.get("end_time", daily_cfg.get("end_time", "21:00"))
    raw_mode = settings_map.get("portal_mode") or settings_map.get("is_portal_open", "auto")
    raw_mode_str = str(raw_mode).strip().lower()
    if raw_mode_str in ("true", "1", "yes"):
        portal_mode = "true"
    elif raw_mode_str in ("false", "0", "no"):
        portal_mode = "false"
    else:
        portal_mode = "auto"

    # Evaluate dynamic portal state
    portal_open = is_ffa_portal_open(config, db_settings=settings_map)

    # Daily multiplier x
    if "daily_multiplier_x" in settings_map:
        multiplier_x = float(settings_map["daily_multiplier_x"])
    else:
        multiplier_x = float(elo_cfg.get("daily_multiplier_x", 1.5))

    # Current day
    if "current_day" in settings_map:
        current_day = int(settings_map["current_day"])
    else:
        current_day = int(t_cfg.get("current_day", 1))

    # Total days
    if "total_days" in settings_map:
        total_days = int(settings_map["total_days"])
    else:
        total_days = int(t_cfg.get("total_days", 7))

    # Max turns
    if "max_turns" in settings_map:
        max_turns = int(settings_map["max_turns"])
    else:
        max_turns = int(rules_cfg.get("max_turns", 200))

    # Timeout
    if "turn_timeout_seconds" in settings_map:
        timeout_seconds = float(settings_map["turn_timeout_seconds"])
    else:
        timeout_seconds = float(rules_cfg.get("turn_timeout_seconds", 1.0))

    return {
        "is_portal_open": portal_open,
        "portal_mode": portal_mode,
        "start_time": start_time,
        "end_time": end_time,
        "daily_multiplier_x": multiplier_x,
        "current_day": current_day,
        "total_days": total_days,
        "max_turns": max_turns,
        "turn_timeout_seconds": timeout_seconds,
        "top_players_count": int(bracket_cfg.get("top_players_count", 8)),
        "bosses": get_all_bosses_status(db),
    }


@router.get("/settings")
def get_settings(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve active tournament configuration and settings."""
    return _get_all_settings_dict(db)


@router.post("/settings")
def update_settings(
    payload: UpdateSettingsRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update tournament settings (portal status, schedule, daily multiplier, days limit)."""
    if payload.portal_mode is not None:
        p_mode = payload.portal_mode.strip().lower()
        _upsert_setting(db, "portal_mode", p_mode)
        _upsert_setting(db, "is_portal_open", p_mode)
    elif payload.is_portal_open is not None:
        p_mode = str(payload.is_portal_open).strip().lower()
        _upsert_setting(db, "is_portal_open", p_mode)
        _upsert_setting(db, "portal_mode", p_mode)

    if payload.start_time is not None:
        _upsert_setting(db, "start_time", payload.start_time.strip())

    if payload.end_time is not None:
        _upsert_setting(db, "end_time", payload.end_time.strip())

    if payload.daily_multiplier_x is not None:
        _upsert_setting(db, "daily_multiplier_x", str(payload.daily_multiplier_x))

    if payload.current_day is not None:
        _upsert_setting(db, "current_day", str(payload.current_day))

    if payload.total_days is not None:
        _upsert_setting(db, "total_days", str(payload.total_days))

    if payload.max_turns is not None:
        _upsert_setting(db, "max_turns", str(payload.max_turns))

    if payload.turn_timeout_seconds is not None:
        _upsert_setting(db, "turn_timeout_seconds", str(payload.turn_timeout_seconds))

    db.commit()
    return _get_all_settings_dict(db)


@router.post("/bracket/generate")
def trigger_bracket_generation(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Seed and generate single-elimination tournament bracket for top participants."""
    settings = _get_all_settings_dict(db)
    top_n = settings.get("top_players_count", 8)

    # Select top users with active bots
    users = (
        db.query(User)
        .order_by(User.elo.desc(), User.id.asc())
        .all()
    )

    eligible_users: List[Dict[str, Any]] = []
    for u in users:
        has_active = any(b.is_active for b in u.bots)
        if has_active:
            eligible_users.append({
                "id": u.id,
                "username": u.username,
                "elo": u.elo,
            })
            if len(eligible_users) >= top_n:
                break

    # If fewer eligible users with active bots, take top users generally
    if len(eligible_users) < 2:
        for u in users:
            if not any(eu["id"] == u.id for eu in eligible_users):
                eligible_users.append({
                    "id": u.id,
                    "username": u.username,
                    "elo": u.elo,
                })
                if len(eligible_users) >= top_n:
                    break

    if len(eligible_users) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 participants are required to generate a tournament bracket.",
        )

    matchups = generate_bracket(eligible_users)

    # Purge any existing pending bracket matches
    db.query(BracketMatch).filter(BracketMatch.status == "pending").delete()

    saved_bracket_matches: List[BracketMatch] = []
    for m in matchups:
        bm = BracketMatch(
            round_name=m["round_name"],
            match_index=m["match_index"],
            player1_id=m["player1_id"],
            player2_id=m["player2_id"],
            status="pending",
        )
        db.add(bm)
        saved_bracket_matches.append(bm)

    db.commit()
    for bm in saved_bracket_matches:
        db.refresh(bm)

    return matchups


@router.get("/bracket")
def get_bracket(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve all current bracket match pairings and statuses."""
    matches = (
        db.query(BracketMatch)
        .order_by(BracketMatch.id.asc())
        .all()
    )
    return [
        {
            "id": bm.id,
            "round_name": bm.round_name,
            "match_index": bm.match_index,
            "player1_id": bm.player1_id,
            "player2_id": bm.player2_id,
            "player1": {"id": bm.player1.id, "username": bm.player1.username} if bm.player1 else None,
            "player2": {"id": bm.player2.id, "username": bm.player2.username} if bm.player2 else None,
            "winner_id": bm.winner_id,
            "score_p1": bm.score_p1,
            "score_p2": bm.score_p2,
            "status": bm.status,
            "created_at": bm.created_at.isoformat() if bm.created_at else None,
        }
        for bm in matches
    ]


@router.get("/bosses")
def list_bosses(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all benchmark boss bots and their current deployment status."""
    return get_all_bosses_status(db)


@router.post("/bosses/deploy")
def toggle_boss_deployment(
    payload: BossDeployRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Deploy or retract a benchmark boss bot in the active tournament arena."""
    action = payload.action.strip().lower()
    if action == "deploy":
        try:
            return deploy_boss(db, payload.boss_slug)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(err),
            )
    elif action == "retract":
        try:
            return retract_boss(db, payload.boss_slug)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(err),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: '{payload.action}'. Expected 'deploy' or 'retract'.",
        )
