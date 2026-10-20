"""FastAPI application entrypoint for BattleCode UET RPS Platform.

Configures CORS, database initialization lifecycle, mounts all REST API routes
for authentication, bot management, match challenges, leaderboard rankings, and
tournament administration, and serves static files and Jinja2 web UI templates.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from server.boss_manager import get_all_bosses_status
from server.database import get_db, init_db
from server.models import Bot, BracketMatch, Game, GameProfile, Match, Tournament, TournamentEnrollment, User
from server.routes import admin, admin_games, admin_tournaments, auth, bots, leaderboard, matches, games
from server.routes.admin import _get_all_settings_dict
from server.routes.auth import ACTIVE_SESSIONS, get_token_from_request
from server.routes.matches import _is_portal_open_now


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "web" / "static"
TEMPLATES_DIR = BASE_DIR / "web" / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing startup and shutdown routines."""
    init_db()
    yield


app = FastAPI(
    title="BattleCode UET RPS Platform API",
    description="REST API for the 9x9 Rock-Paper-Scissors Chess tournament platform.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for local web client and remote tunnel access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web UI
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Jinja2 templates configuration
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount all feature routes under /api
app.include_router(auth.router, prefix="/api")
app.include_router(bots.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(leaderboard.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(admin_games.router, prefix="/api")
app.include_router(games.router, prefix="/api")
app.include_router(admin_tournaments.router, prefix="/api")
app.include_router(admin_tournaments.public_router, prefix="/api")


@app.get("/api/users/{user_id}/rating-history", tags=["users"])
def get_user_rating_history_alias(
    user_id: int,
    limit: int = Query(50, ge=5, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve chronological Elo trajectory for a specific user ID."""
    return leaderboard.get_single_user_rating_history(user_id=user_id, limit=limit, db=db)



def _get_optional_user(request: Request, db: Session) -> User | None:
    """Retrieve authenticated User from session cookie/header without raising HTTP 401."""
    token = get_token_from_request(request)
    if token and token in ACTIVE_SESSIONS:
        user_id = ACTIVE_SESSIONS[token]
        return db.query(User).filter(User.id == user_id).first()
    return None


# ================== WEB UI HTML ROUTES ==================


@app.get("/lobby", response_class=HTMLResponse, tags=["web"])
def lobby_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the multi-game lobby landing portal."""
    current_user = _get_optional_user(request, db)
    games = db.query(Game).filter(Game.is_active == True).order_by(Game.id.asc()).all()  # noqa: E712
    return templates.TemplateResponse(
        request=request,
        name="lobby.html",
        context={
            "games": games,
            "current_user": current_user,
        },
    )


@app.get("/", response_class=HTMLResponse, tags=["web"])
def home_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the homepage leaderboard and FFA challenge portal, or multi-game lobby."""
    current_user = _get_optional_user(request, db)
    games = db.query(Game).filter(Game.is_active == True).order_by(Game.id.asc()).all()  # noqa: E712

    view_mode = request.query_params.get("view", "").strip().lower()
    if view_mode == "lobby" or (len(games) > 1 and view_mode != "legacy"):
        return templates.TemplateResponse(
            request=request,
            name="lobby.html",
            context={
                "games": games,
                "current_user": current_user,
            },
        )

    users = (
        db.query(User)
        .filter(User.is_admin == False)  # noqa: E712
        .order_by(User.elo.desc(), User.wins.desc(), User.id.asc())
        .all()
    )

    ranking_list: List[Dict[str, Any]] = []
    for rank_idx, u in enumerate(users, start=1):
        has_active = any(b.is_active for b in u.bots)
        ranking_list.append({
            "rank": rank_idx,
            "id": u.id,
            "username": u.username,
            "elo": u.elo,
            "wins": u.wins,
            "losses": u.losses,
            "draws": u.draws,
            "has_active_bot": has_active,
        })

    settings = _get_all_settings_dict(db)
    is_portal_open = _is_portal_open_now(db)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "leaderboard": ranking_list,
            "is_portal_open": is_portal_open,
            "daily_multiplier_x": settings.get("daily_multiplier_x", 1.5),
            "current_user": current_user,
            "games": games,
        },
    )


@app.get("/games/{slug}", response_class=HTMLResponse, tags=["web"])
def game_detail_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the 3-tab game detail view (Rules, Leaderboard, Tournaments)."""
    current_user = _get_optional_user(request, db)
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found.",
        )

    profiles = (
        db.query(GameProfile)
        .filter(GameProfile.game_id == game.id)
        .order_by(GameProfile.elo.desc())
        .all()
    )

    tournaments = (
        db.query(Tournament)
        .filter(Tournament.game_id == game.id)
        .order_by(Tournament.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="game_detail.html",
        context={
            "game": game,
            "profiles": profiles,
            "tournaments": tournaments,
            "current_user": current_user,
        },
    )


@app.get("/games/{slug}/tournaments/{tournament_id}", response_class=HTMLResponse, tags=["web"])
def tournament_detail_page(
    slug: str,
    tournament_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render public tournament detail page with enrolled list and bracket tree."""
    current_user = _get_optional_user(request, db)
    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found.",
        )

    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney or tourney.game_id != game.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found for game '{slug}'.",
        )

    enrollments = (
        db.query(TournamentEnrollment)
        .filter(TournamentEnrollment.tournament_id == tournament_id)
        .order_by(TournamentEnrollment.enrolled_at.asc())
        .all()
    )

    bracket_matches = (
        db.query(BracketMatch)
        .order_by(BracketMatch.id.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="tournament_detail.html",
        context={
            "game": game,
            "tournament": tourney,
            "enrollments": enrollments,
            "bracket_matches": bracket_matches,
            "current_user": current_user,
        },
    )


@app.get("/login", response_class=HTMLResponse, tags=["web"])
def login_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the user login page."""
    current_user = _get_optional_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"current_user": current_user},
    )


@app.get("/register", response_class=HTMLResponse, tags=["web"])
def register_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the user registration page."""
    current_user = _get_optional_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"current_user": current_user},
    )


@app.get("/profile", response_class=HTMLResponse, tags=["web"])
def profile_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the user profile, bot upload drop zone, and match history page."""
    current_user = _get_optional_user(request, db)
    user_bots: List[Bot] = []
    user_matches: List[Match] = []

    if current_user:
        user_bots = (
            db.query(Bot)
            .filter(Bot.user_id == current_user.id)
            .order_by(Bot.uploaded_at.desc())
            .all()
        )
        user_matches = (
            db.query(Match)
            .filter(or_(Match.player1_id == current_user.id, Match.player2_id == current_user.id))
            .order_by(Match.created_at.desc())
            .limit(20)
            .all()
        )
        game_profiles = (
            db.query(GameProfile)
            .filter(GameProfile.user_id == current_user.id)
            .all()
        )
    else:
        game_profiles = []

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "current_user": current_user,
            "user_bots": user_bots,
            "user_matches": user_matches,
            "game_profiles": game_profiles,
        },
    )


@app.get("/profile/{user_id}", response_class=HTMLResponse, tags=["web"])
def user_profile_by_id_page(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render a specific user's profile viewable by other players."""
    current_user = _get_optional_user(request, db)
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    user_bots = (
        db.query(Bot)
        .filter(Bot.user_id == target_user.id)
        .order_by(Bot.uploaded_at.desc())
        .all()
    )
    user_matches = (
        db.query(Match)
        .filter(or_(Match.player1_id == target_user.id, Match.player2_id == target_user.id))
        .order_by(Match.created_at.desc())
        .limit(20)
        .all()
    )
    game_profiles = (
        db.query(GameProfile)
        .filter(GameProfile.user_id == target_user.id)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "current_user": current_user,
            "target_user": target_user,
            "user_bots": user_bots,
            "user_matches": user_matches,
            "game_profiles": game_profiles,
        },
    )


@app.get("/profile/{user_id}/games/{game_slug}", response_class=HTMLResponse, tags=["web"])
def user_game_profile_page(
    user_id: int,
    game_slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the per-game profile page showing Elo trajectory and game-specific matches."""
    current_user = _get_optional_user(request, db)
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    game = db.query(Game).filter(Game.slug == game_slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game with slug '{game_slug}' not found.",
        )

    profile = (
        db.query(GameProfile)
        .filter(GameProfile.user_id == user_id, GameProfile.game_id == game.id)
        .first()
    )

    game_matches = (
        db.query(Match)
        .filter(
            Match.game_id == game.id,
            or_(Match.player1_id == user_id, Match.player2_id == user_id),
        )
        .order_by(Match.created_at.desc())
        .limit(30)
        .all()
    )

    total_matches = (profile.wins + profile.losses + profile.draws) if profile else len(game_matches)
    win_rate = round((profile.wins / total_matches * 100), 1) if (profile and total_matches > 0) else 0.0

    return templates.TemplateResponse(
        request=request,
        name="game_profile.html",
        context={
            "current_user": current_user,
            "target_user": target_user,
            "game": game,
            "profile": profile,
            "game_matches": game_matches,
            "total_matches": total_matches,
            "win_rate": win_rate,
        },
    )


@app.get("/replay/{match_id}", response_class=HTMLResponse, tags=["web"])
def replay_page(
    match_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the interactive 9x9 visual replay arena."""
    current_user = _get_optional_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="replay.html",
        context={
            "match_id": match_id,
            "current_user": current_user,
        },
    )


def _require_admin_web_user(request: Request, db: Session, target_path: str) -> User | Response:
    """Ensure user is logged in as admin; redirect to login or raise 403."""
    user = _get_optional_user(request, db)
    if user is None:
        return RedirectResponse(
            url=f"/login?next={target_path}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )
    return user


@app.get("/admin", response_class=HTMLResponse, tags=["web"])
def admin_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render tournament configuration management and bracket generator page."""
    admin_auth = _require_admin_web_user(request, db, "/admin")
    if isinstance(admin_auth, Response):
        return admin_auth

    settings = _get_all_settings_dict(db)
    bracket_matches = (
        db.query(BracketMatch)
        .order_by(BracketMatch.id.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "settings": settings,
            "bracket_matches": bracket_matches,
            "current_user": admin_auth,
        },
    )


@app.get("/admin/dashboard", response_class=HTMLResponse, tags=["web"])
def admin_dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render the master admin operational overview dashboard."""
    admin_auth = _require_admin_web_user(request, db, "/admin/dashboard")
    if isinstance(admin_auth, Response):
        return admin_auth

    games = db.query(Game).order_by(Game.id.asc()).all()
    tournaments = db.query(Tournament).order_by(Tournament.created_at.desc()).all()
    users = db.query(User).order_by(User.id.asc()).all()
    bracket_matches = db.query(BracketMatch).order_by(BracketMatch.id.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "games": games,
            "tournaments": tournaments,
            "users": users,
            "bracket_matches": bracket_matches,
            "current_user": admin_auth,
        },
    )


@app.get("/admin/games", response_class=HTMLResponse, tags=["web"])
def admin_games_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render the admin games plugin catalog and status toggles."""
    admin_auth = _require_admin_web_user(request, db, "/admin/games")
    if isinstance(admin_auth, Response):
        return admin_auth

    games = db.query(Game).order_by(Game.id.asc()).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/games.html",
        context={
            "games": games,
            "current_user": admin_auth,
        },
    )


@app.get("/admin/games/upload", response_class=HTMLResponse, tags=["web"])
def admin_games_upload_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render the admin game plugin zip upload portal."""
    admin_auth = _require_admin_web_user(request, db, "/admin/games/upload")
    if isinstance(admin_auth, Response):
        return admin_auth

    return templates.TemplateResponse(
        request=request,
        name="admin/game_upload.html",
        context={
            "current_user": admin_auth,
        },
    )


@app.get("/admin/games/{slug}", response_class=HTMLResponse, tags=["web"])
def admin_game_context_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render the contextual administration portal for a specific game."""
    admin_auth = _require_admin_web_user(request, db, f"/admin/games/{slug}")
    if isinstance(admin_auth, Response):
        return admin_auth

    game = db.query(Game).filter(Game.slug == slug).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{slug}' not found.",
        )

    bosses = get_all_bosses_status(db, game_id=game.id)
    tournaments = (
        db.query(Tournament)
        .filter(Tournament.game_id == game.id)
        .order_by(Tournament.created_at.desc())
        .all()
    )
    bots = (
        db.query(Bot)
        .filter(Bot.game_id == game.id)
        .order_by(Bot.id.desc())
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="admin/game_context.html",
        context={
            "game": game,
            "bosses": bosses,
            "tournaments": tournaments,
            "bots": bots,
            "current_user": admin_auth,
        },
    )


@app.get("/admin/tournaments", response_class=HTMLResponse, tags=["web"])
def admin_tournaments_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render the admin tournaments management and creation view."""
    admin_auth = _require_admin_web_user(request, db, "/admin/tournaments")
    if isinstance(admin_auth, Response):
        return admin_auth

    tournaments = db.query(Tournament).order_by(Tournament.created_at.desc()).all()
    games = db.query(Game).filter(Game.is_active == True).order_by(Game.id.asc()).all()  # noqa: E712
    return templates.TemplateResponse(
        request=request,
        name="admin/tournaments.html",
        context={
            "tournaments": tournaments,
            "games": games,
            "current_user": admin_auth,
        },
    )


@app.get("/admin/tournaments/{tournament_id}", response_class=HTMLResponse, tags=["web"])
def admin_tournament_detail_page(
    tournament_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render the admin tournament coordination and playoff bracket control view."""
    admin_auth = _require_admin_web_user(request, db, f"/admin/tournaments/{tournament_id}")
    if isinstance(admin_auth, Response):
        return admin_auth

    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with id {tournament_id} not found.",
        )

    bracket_matches = db.query(BracketMatch).order_by(BracketMatch.id.asc()).all()
    enrollments = (
        db.query(TournamentEnrollment)
        .filter(TournamentEnrollment.tournament_id == tournament_id)
        .order_by(TournamentEnrollment.enrolled_at.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/tournament_detail.html",
        context={
            "tournament": tournament,
            "bracket_matches": bracket_matches,
            "enrollments": enrollments,
            "current_user": admin_auth,
        },
    )


@app.get("/admin/users", response_class=HTMLResponse, tags=["web"])
def admin_users_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render the admin registered accounts and player bot statuses."""
    admin_auth = _require_admin_web_user(request, db, "/admin/users")
    if isinstance(admin_auth, Response):
        return admin_auth

    users = db.query(User).order_by(User.id.asc()).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/users.html",
        context={
            "users": users,
            "current_user": admin_auth,
        },
    )


@app.get("/bracket", response_class=HTMLResponse, tags=["web"])
def bracket_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the tournament bracket elimination tree and match pairings."""
    current_user = _get_optional_user(request, db)
    bracket_matches = (
        db.query(BracketMatch)
        .order_by(BracketMatch.id.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="bracket.html",
        context={
            "bracket_matches": bracket_matches,
            "current_user": current_user,
        },
    )


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Health check endpoint to verify server responsiveness."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
