"""FastAPI application entrypoint for Battlecode 9x9 RPS Platform.

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
    title="Battlecode 9x9 RPS Platform API",
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

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "current_user": current_user,
            "user_bots": user_bots,
            "user_matches": user_matches,
        },
    )


@app.get("/replay/{match_id}", response_class=HTMLResponse, tags=["web"])
def replay_page(
    match_id: int,
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


@app.get("/admin", response_class=HTMLResponse, tags=["web"])
def admin_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Render tournament configuration management and bracket generator page."""
    current_user = _get_optional_user(request, db)
    if current_user is None:
        return RedirectResponse(
            url="/login?next=/admin",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )

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
            "current_user": current_user,
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
