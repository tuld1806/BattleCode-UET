"""Player-facing API routes for game catalog exploration and tournament enrollment."""

from __future__ import annotations

import json
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Bot, Game, GameProfile, Tournament, TournamentEnrollment, User
from server.rating_history import get_top_teams_rating_history, get_user_rating_history
from server.routes.auth import get_current_user

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=List[Dict[str, Any]])
def list_active_games(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all publicly active game plugins with tournament counts."""
    games = db.query(Game).filter(Game.is_active == True).order_by(Game.id.asc()).all()  # noqa: E712
    results = []
    for g in games:
        results.append({
            "id": g.id,
            "slug": g.slug,
            "display_name": g.display_name,
            "description_md": g.description_md,
            "icon_path": g.icon_path,
            "tournaments_count": len([t for t in g.tournaments if t.status != "finished"]),
            "players_count": len(g.profiles),
        })
    return results


@router.get("/{slug}", response_model=Dict[str, Any])
def get_game_detail(slug: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve details, rules, and tournaments for a specific game."""
    game = db.query(Game).filter(Game.slug == slug, Game.is_active == True).first()  # noqa: E712
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found or inactive.",
        )

    tournaments_data = []
    for t in game.tournaments:
        tournaments_data.append({
            "id": t.id,
            "name": t.name,
            "status": t.status,
            "ffa_start_time": t.ffa_start_time,
            "ffa_end_time": t.ffa_end_time,
            "ffa_day_count": t.ffa_day_count,
            "bracket_top_n": t.bracket_top_n,
            "elo_multiplier": t.elo_multiplier,
            "enrollment_open": t.enrollment_open,
            "enrolled_count": len(t.enrollments),
        })

    config_data = {}
    if game.config_json:
        try:
            config_data = json.loads(game.config_json)
        except Exception:
            pass

    return {
        "id": game.id,
        "slug": game.slug,
        "display_name": game.display_name,
        "description_md": game.description_md,
        "icon_path": game.icon_path,
        "config": config_data,
        "tournaments": tournaments_data,
    }


@router.get("/{slug}/tournaments", response_model=List[Dict[str, Any]])
def list_game_tournaments(slug: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List tournaments scoped to a specific game."""
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game '{slug}' not found.")

    return [
        {
            "id": t.id,
            "name": t.name,
            "status": t.status,
            "ffa_start_time": t.ffa_start_time,
            "ffa_end_time": t.ffa_end_time,
            "bracket_top_n": t.bracket_top_n,
            "elo_multiplier": t.elo_multiplier,
            "enrollment_open": t.enrollment_open,
            "enrolled_count": len(t.enrollments),
        }
        for t in game.tournaments
    ]


@router.get("/{slug}/tournaments/{tournament_id}", response_model=Dict[str, Any])
def get_game_tournament_detail(slug: str, tournament_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve detailed tournament overview for players."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney or (tourney.game and tourney.game.slug != slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found for this game.")

    return {
        "id": tourney.id,
        "game_id": tourney.game_id,
        "game_slug": slug,
        "name": tourney.name,
        "status": tourney.status,
        "ffa_start_time": tourney.ffa_start_time,
        "ffa_end_time": tourney.ffa_end_time,
        "ffa_day_count": tourney.ffa_day_count,
        "bracket_top_n": tourney.bracket_top_n,
        "elo_multiplier": tourney.elo_multiplier,
        "enrollment_open": tourney.enrollment_open,
        "enrolled_count": len(tourney.enrollments),
    }


@router.post("/{slug}/tournaments/{tournament_id}/enroll", response_model=Dict[str, Any])
def enroll_in_tournament(
    slug: str,
    tournament_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Enroll participant into a tournament using their active game-specific bot."""
    # 1. Admin decoupling invariant
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin accounts cannot enroll in tournaments (Admin-Player Decoupling Invariant).",
        )

    # 2. Check game and tournament
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game '{slug}' not found.")

    tourney = db.query(Tournament).filter(Tournament.id == tournament_id, Tournament.game_id == game.id).first()
    if not tourney:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found.")

    if tourney.status != "open" or not tourney.enrollment_open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Enrollment is closed for tournament '{tourney.name}' (current status: {tourney.status}).",
        )

    # 3. Check for active bot for this game
    active_bot = db.query(Bot).filter(
        Bot.user_id == current_user.id,
        or_(Bot.game_id == game.id, Bot.game_id == None),  # noqa: E711
        Bot.is_active == True,  # noqa: E712
    ).first()

    if not active_bot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You must have an active bot uploaded for '{game.display_name}' to enroll.",
        )

    # 4. Check duplicate enrollment
    existing_enrollment = db.query(TournamentEnrollment).filter(
        TournamentEnrollment.tournament_id == tourney.id,
        TournamentEnrollment.user_id == current_user.id,
    ).first()

    if existing_enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already enrolled in this tournament.",
        )

    # 5. Find or create GameProfile
    profile = db.query(GameProfile).filter(
        GameProfile.user_id == current_user.id,
        GameProfile.game_id == game.id,
    ).first()

    if not profile:
        profile = GameProfile(
            user_id=current_user.id,
            game_id=game.id,
            elo=1200,
            wins=0,
            losses=0,
            draws=0,
        )
        db.add(profile)

    # 6. Create enrollment record
    enrollment = TournamentEnrollment(
        tournament_id=tourney.id,
        user_id=current_user.id,
        bot_id=active_bot.id,
    )
    db.add(enrollment)
    db.commit()

    return {
        "status": "enrolled",
        "tournament_id": tourney.id,
        "game_slug": slug,
        "bot_id": active_bot.id,
        "message": f"Successfully enrolled in {tourney.name}.",
    }


@router.post("/{slug}/tournaments/{tournament_id}/unenroll", response_model=Dict[str, Any])
def unenroll_from_tournament(
    slug: str,
    tournament_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Cancel enrollment from an open tournament."""
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found.")

    if tourney.status != "open":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot un-enroll once tournament is {tourney.status}.",
        )

    enrollment = db.query(TournamentEnrollment).filter(
        TournamentEnrollment.tournament_id == tourney.id,
        TournamentEnrollment.user_id == current_user.id,
    ).first()

    if not enrollment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enrolled in this tournament.")

    db.delete(enrollment)
    db.commit()

    return {
        "status": "unenrolled",
        "tournament_id": tourney.id,
        "message": f"Successfully un-enrolled from {tourney.name}.",
    }


@router.get("/{slug}/leaderboard", response_model=List[Dict[str, Any]])
def get_game_leaderboard(
    slug: str,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve per-game Elo leaderboard ordered by rating descending.

    Non-admin users with a GameProfile for the specified game are ranked by profile.
    Falls back to global User.elo/wins/losses/draws for users without a GameProfile,
    ensuring newly registered players appear on the leaderboard seamlessly.
    Strictly excludes administrator accounts.
    """
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game and slug == "rps-chess":
        from server.database import seed_default_game
        seed_default_game(db_session=db)
        game = db.query(Game).filter(Game.slug == slug).first()

    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game '{slug}' not found.")

    profiles = (
        db.query(GameProfile)
        .join(User, GameProfile.user_id == User.id)
        .filter(
            GameProfile.game_id == game.id,
            User.is_admin == False,  # noqa: E712
        )
        .all()
    )

    seen_user_ids = set()
    entries: List[Dict[str, Any]] = []

    for profile in profiles:
        user = db.query(User).filter(User.id == profile.user_id).first()
        if not user or user.is_admin:
            continue
        has_active = any(
            bot.is_active for bot in db.query(Bot).filter(Bot.user_id == user.id).all()
        )
        entries.append({
            "id": user.id,
            "username": user.username,
            "elo": profile.elo,
            "wins": profile.wins,
            "losses": profile.losses,
            "draws": profile.draws,
            "has_active_bot": has_active,
        })
        seen_user_ids.add(user.id)

    # Fallback: include registered non-admin users without a GameProfile
    fallback_users = (
        db.query(User)
        .filter(User.is_admin == False)  # noqa: E712
        .all()
    )
    for u in fallback_users:
        if u.id not in seen_user_ids:
            has_active = any(
                bot.is_active for bot in db.query(Bot).filter(Bot.user_id == u.id).all()
            )
            entries.append({
                "id": u.id,
                "username": u.username,
                "elo": u.elo if u.elo is not None else 1200,
                "wins": u.wins if u.wins is not None else 0,
                "losses": u.losses if u.losses is not None else 0,
                "draws": u.draws if u.draws is not None else 0,
                "has_active_bot": has_active,
            })
            seen_user_ids.add(u.id)

    # Sort descending by elo, then wins, then ascending by user id
    entries.sort(key=lambda x: (x["elo"], x["wins"], -x["id"]), reverse=True)

    rankings: List[Dict[str, Any]] = []
    for rank_idx, entry in enumerate(entries, start=1):
        rankings.append({
            "rank": rank_idx,
            "id": entry["id"],
            "username": entry["username"],
            "elo": entry["elo"],
            "wins": entry["wins"],
            "losses": entry["losses"],
            "draws": entry["draws"],
            "has_active_bot": entry["has_active_bot"],
        })

    return rankings


@router.get("/{slug}/rating-history")
def get_game_rating_history(
    slug: str,
    top: int = Query(5, ge=1, le=10),
    limit: int = Query(30, ge=5, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve top-N rating trajectories scoped to a specific game."""
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game '{slug}' not found.")
    return get_top_teams_rating_history(db=db, game_id=game.id, top=top, limit=limit)


@router.get("/{slug}/users/{user_id}/rating-history")
def get_game_user_rating_history(
    slug: str,
    user_id: int,
    limit: int = Query(50, ge=5, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve per-game Elo trajectory for a specific user."""
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game '{slug}' not found.")
    history = get_user_rating_history(user_id=user_id, db=db, game_id=game.id, limit=limit)
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return history

