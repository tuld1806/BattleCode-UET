"""Integration tests for Admin Tournament Management API routes (server/routes/admin_tournaments.py)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.database import Base, get_db
from server.main import app
from server.models import Bot, BracketMatch, Game, GameProfile, Tournament, TournamentEnrollment, User
from server.routes.auth import ACTIVE_SESSIONS


@pytest.fixture
def client_and_db(tmp_path):
    """Create test client with isolated database and authenticated sessions."""
    db_file = tmp_path / "test_admin_tournaments.db"
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
    # Create admin and players
    admin_user = User(username="admin_tourney", is_admin=True)
    admin_user.set_password("admin_pass")
    player1 = User(username="player1", is_admin=False)
    player1.set_password("pass1")
    player2 = User(username="player2", is_admin=False)
    player2.set_password("pass2")
    player3 = User(username="player3", is_admin=False)
    player3.set_password("pass3")
    player4 = User(username="player4", is_admin=False)
    player4.set_password("pass4")

    game = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    session.add_all([admin_user, player1, player2, player3, player4, game])
    session.commit()

    # Create GameProfiles
    gp1 = GameProfile(user_id=player1.id, game_id=game.id, elo=1400)
    gp2 = GameProfile(user_id=player2.id, game_id=game.id, elo=1600)
    gp3 = GameProfile(user_id=player3.id, game_id=game.id, elo=1300)
    gp4 = GameProfile(user_id=player4.id, game_id=game.id, elo=1500)
    session.add_all([gp1, gp2, gp3, gp4])

    # Create active bots
    b1 = Bot(user_id=player1.id, game_id=game.id, filename="b1.py", filepath="b1.py", is_active=True)
    b2 = Bot(user_id=player2.id, game_id=game.id, filename="b2.py", filepath="b2.py", is_active=True)
    b3 = Bot(user_id=player3.id, game_id=game.id, filename="b3.py", filepath="b3.py", is_active=True)
    b4 = Bot(user_id=player4.id, game_id=game.id, filename="b4.py", filepath="b4.py", is_active=True)
    session.add_all([b1, b2, b3, b4])
    session.commit()

    admin_token = "admin-tourney-token"
    player_token = "player-tourney-token"
    ACTIVE_SESSIONS[admin_token] = admin_user.id
    ACTIVE_SESSIONS[player_token] = player1.id

    client = TestClient(app)

    yield {
        "client": client,
        "admin_token": admin_token,
        "player_token": player_token,
        "session": session,
        "game": game,
        "players": [player1, player2, player3, player4],
    }

    app.dependency_overrides.clear()
    ACTIVE_SESSIONS.pop(admin_token, None)
    ACTIVE_SESSIONS.pop(player_token, None)
    session.close()


def test_admin_tournaments_auth_guard(client_and_db):
    """Admin tournament endpoints require admin session."""
    client = client_and_db["client"]
    player_token = client_and_db["player_token"]
    admin_token = client_and_db["admin_token"]

    resp = client.get("/api/admin/tournaments")
    assert resp.status_code == 401

    resp = client.get("/api/admin/tournaments", headers={"Authorization": f"Bearer {player_token}"})
    assert resp.status_code == 403

    resp = client.get("/api/admin/tournaments", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_tournament_success_and_validation(client_and_db):
    """Admin can create tournament with validation of parameters and game_id."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]
    game = client_and_db["game"]

    # 1. Invalid game_id
    resp = client.post(
        "/api/admin/tournaments",
        json={"game_id": 9999, "name": "Fake Tourney"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code in (400, 404)

    # 2. Valid creation
    payload = {
        "game_id": game.id,
        "name": "Spring Championship",
        "ffa_start_time": "18:00",
        "ffa_end_time": "22:00",
        "ffa_day_count": 5,
        "bracket_top_n": 4,
        "elo_multiplier": 1.5,
        "enrollment_open": True,
    }
    resp = client.post(
        "/api/admin/tournaments",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Spring Championship"
    assert data["status"] == "open"
    assert data["bracket_top_n"] == 4


def test_tournament_status_transitions(client_and_db):
    """Validate allowed and disallowed status state machine transitions."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]
    game = client_and_db["game"]
    session = client_and_db["session"]

    tourney = Tournament(
        game_id=game.id,
        name="State Machine Test",
        status="open",
        bracket_top_n=4,
    )
    session.add(tourney)
    session.commit()

    # 1. open -> running (valid)
    resp = client.post(
        f"/api/admin/tournaments/{tourney.id}/set-status",
        json={"status": "running"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

    # 2. running -> finished (valid)
    resp = client.post(
        f"/api/admin/tournaments/{tourney.id}/set-status",
        json={"status": "finished"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "finished"

    # 3. finished -> running (invalid transition)
    resp = client.post(
        f"/api/admin/tournaments/{tourney.id}/set-status",
        json={"status": "running"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


def test_start_bracket_seeds_enrolled_players(client_and_db):
    """Starting bracket must seed Top N enrolled players by GameProfile Elo."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]
    game = client_and_db["game"]
    players = client_and_db["players"]
    session = client_and_db["session"]

    tourney = Tournament(
        game_id=game.id,
        name="Bracket Playoff Test",
        status="running",
        bracket_top_n=4,
    )
    session.add(tourney)
    session.commit()

    # Enroll all 4 players
    for p in players:
        enrollment = TournamentEnrollment(
            tournament_id=tourney.id,
            user_id=p.id,
            bot_id=p.bots[0].id if p.bots else None,
        )
        session.add(enrollment)
    session.commit()

    resp = client.post(
        f"/api/admin/tournaments/{tourney.id}/start-bracket",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "bracket"
    assert "matchups" in result
    assert len(result["matchups"]) == 2  # 4 players -> 2 Semi-Final matchups

    # Verify BracketMatch records in DB
    session.expire_all()
    bms = session.query(BracketMatch).all()
    assert len(bms) == 2
    # Seed 1 should be player2 (elo 1600), Seed 2 should be player4 (elo 1500)
    # Match 1: Seed 1 vs Seed 4 (player2 vs player3)
    p2_id = players[1].id  # elo 1600
    p3_id = players[2].id  # elo 1300
    p4_id = players[3].id  # elo 1500
    p1_id = players[0].id  # elo 1400

    match1 = bms[0]
    match2 = bms[1]
    assert {match1.player1_id, match1.player2_id} == {p2_id, p3_id}
    assert {match2.player1_id, match2.player2_id} == {p4_id, p1_id}
