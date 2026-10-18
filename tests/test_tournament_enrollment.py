"""Integration tests for Player Games & Tournament Enrollment API routes (server/routes/games.py)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.database import Base, get_db
from server.main import app
from server.models import Bot, Game, GameProfile, Tournament, TournamentEnrollment, User
from server.routes.auth import ACTIVE_SESSIONS


@pytest.fixture
def client_and_db(tmp_path):
    """Create test client with isolated database and authenticated sessions."""
    db_file = tmp_path / "test_games_enrollment.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSession()
    # Create admin, player with bot, player without bot
    admin_user = User(username="admin_sys", is_admin=True)
    admin_user.set_password("admin_pass")
    player_with_bot = User(username="player_bot", is_admin=False)
    player_with_bot.set_password("pass")
    player_no_bot = User(username="player_nobot", is_admin=False)
    player_no_bot.set_password("pass")

    game1 = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    game2 = Game(slug="cyber-grid", display_name="Cyber Grid", is_active=False)
    session.add_all([admin_user, player_with_bot, player_no_bot, game1, game2])
    session.commit()

    # Bot for player_with_bot on game1
    bot1 = Bot(
        user_id=player_with_bot.id,
        game_id=game1.id,
        filename="my_rps_bot.py",
        filepath="bots/my_rps_bot.py",
        is_active=True,
    )
    session.add(bot1)

    # Tournaments for game1
    tourney_open = Tournament(
        game_id=game1.id,
        name="Open RPS Championship",
        status="open",
        enrollment_open=True,
    )
    tourney_running = Tournament(
        game_id=game1.id,
        name="Running RPS Cup",
        status="running",
        enrollment_open=False,
    )
    session.add_all([tourney_open, tourney_running])
    session.commit()

    admin_token = "admin-enroll-token"
    player_bot_token = "player-bot-token"
    player_nobot_token = "player-nobot-token"
    ACTIVE_SESSIONS[admin_token] = admin_user.id
    ACTIVE_SESSIONS[player_bot_token] = player_with_bot.id
    ACTIVE_SESSIONS[player_nobot_token] = player_no_bot.id

    client = TestClient(app)

    yield {
        "client": client,
        "admin_token": admin_token,
        "player_bot_token": player_bot_token,
        "player_nobot_token": player_nobot_token,
        "session": session,
        "game1": game1,
        "game2": game2,
        "tourney_open": tourney_open,
        "tourney_running": tourney_running,
        "player_with_bot": player_with_bot,
    }

    app.dependency_overrides.clear()
    ACTIVE_SESSIONS.pop(admin_token, None)
    ACTIVE_SESSIONS.pop(player_bot_token, None)
    ACTIVE_SESSIONS.pop(player_nobot_token, None)
    session.close()


def test_list_games_and_detail(client_and_db):
    """GET /api/games returns only active games; GET /api/games/{slug} returns game detail."""
    client = client_and_db["client"]

    # 1. List active games
    resp = client.get("/api/games")
    assert resp.status_code == 200
    games = resp.json()
    assert isinstance(games, list)
    assert any(g["slug"] == "rps-chess" for g in games)
    assert not any(g["slug"] == "cyber-grid" for g in games)  # inactive game hidden

    # 2. Game detail
    resp = client.get("/api/games/rps-chess")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["slug"] == "rps-chess"
    assert "tournaments" in detail


def test_player_enroll_success_creates_game_profile(client_and_db):
    """Enrolling in an open tournament with an active bot succeeds and seeds GameProfile."""
    client = client_and_db["client"]
    token = client_and_db["player_bot_token"]
    tourney = client_and_db["tourney_open"]
    player = client_and_db["player_with_bot"]
    session = client_and_db["session"]

    resp = client.post(
        f"/api/games/rps-chess/tournaments/{tourney.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "enrolled"
    assert data["tournament_id"] == tourney.id

    # Verify GameProfile was created
    session.expire_all()
    gp = session.query(GameProfile).filter(
        GameProfile.user_id == player.id,
        GameProfile.game_id == tourney.game_id,
    ).first()
    assert gp is not None
    assert gp.elo == 1200


def test_admin_cannot_enroll_in_tournament(client_and_db):
    """Admin accounts must be strictly blocked from enrolling in tournaments."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]
    tourney = client_and_db["tourney_open"]

    resp = client.post(
        f"/api/games/rps-chess/tournaments/{tourney.id}/enroll",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code in (400, 403)
    assert "admin" in resp.json()["detail"].lower()


def test_player_cannot_enroll_without_active_bot(client_and_db):
    """Player without an active bot for the game cannot enroll."""
    client = client_and_db["client"]
    token = client_and_db["player_nobot_token"]
    tourney = client_and_db["tourney_open"]

    resp = client.post(
        f"/api/games/rps-chess/tournaments/{tourney.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "active bot" in resp.json()["detail"].lower()


def test_player_cannot_enroll_when_closed_or_running(client_and_db):
    """Enrollment must be rejected if tournament is running or enrollment_open is False."""
    client = client_and_db["client"]
    token = client_and_db["player_bot_token"]
    tourney = client_and_db["tourney_running"]

    resp = client.post(
        f"/api/games/rps-chess/tournaments/{tourney.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_duplicate_enrollment_rejected(client_and_db):
    """Attempting to enroll twice in the same tournament returns 400."""
    client = client_and_db["client"]
    token = client_and_db["player_bot_token"]
    tourney = client_and_db["tourney_open"]

    # 1st attempt
    resp1 = client.post(
        f"/api/games/rps-chess/tournaments/{tourney.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200

    # 2nd attempt
    resp2 = client.post(
        f"/api/games/rps-chess/tournaments/{tourney.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 400
    assert "already enrolled" in resp2.json()["detail"].lower()


def test_unenroll_when_open_vs_running(client_and_db):
    """Un-enrolling is allowed when status is 'open', disallowed when 'running'."""
    client = client_and_db["client"]
    token = client_and_db["player_bot_token"]
    tourney_open = client_and_db["tourney_open"]
    tourney_running = client_and_db["tourney_running"]
    player = client_and_db["player_with_bot"]
    session = client_and_db["session"]

    # 1. Enroll in open tourney then unenroll
    client.post(
        f"/api/games/rps-chess/tournaments/{tourney_open.id}/enroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        f"/api/games/rps-chess/tournaments/{tourney_open.id}/unenroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "unenrolled"

    # 2. Try un-enrolling from running tournament
    # Manually add enrollment to running tourney
    enr = TournamentEnrollment(
        tournament_id=tourney_running.id,
        user_id=player.id,
        bot_id=player.bots[0].id,
    )
    session.add(enr)
    session.commit()

    resp = client.post(
        f"/api/games/rps-chess/tournaments/{tourney_running.id}/unenroll",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
