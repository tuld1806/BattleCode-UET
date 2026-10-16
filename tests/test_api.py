"""Integration tests for FastAPI endpoints, authentication, bot uploads, and match queue."""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server.database import Base, SessionLocal, engine, init_db
from server.models import Bot, Match, TournamentSetting, User
from server.queue import execute_match_job
from server.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Ensure clean database and tables for every test."""
    init_db()
    yield
    # Clean up DB after test
    engine.dispose()
    for db_artifact in ["app.db", "app.db-shm", "app.db-wal"]:
        if os.path.exists(db_artifact):
            try:
                os.remove(db_artifact)
            except OSError:
                pass
    if os.path.exists("bots"):
        import shutil
        shutil.rmtree("bots", ignore_errors=True)
    if os.path.exists("replays"):
        import shutil
        shutil.rmtree("replays", ignore_errors=True)


def _create_admin_and_login(username="admin_user", password="adminpassword123"):
    """Helper to create an admin user and return authorization header."""
    db = SessionLocal()
    try:
        user = User(username=username, is_admin=True)
        user.set_password(password)
        db.add(user)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/auth/login", data={"username": username, "password": password})
    assert res.status_code == 200
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create_user_and_login(username="player_test", password="testpassword123"):
    """Helper to register and login a regular user, returning auth header and user info."""
    res_reg = client.post("/api/auth/register", json={"username": username, "password": password})
    assert res_reg.status_code in (200, 201)

    res_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res_login.status_code == 200
    token = res_login.json()["token"]
    user_info = res_login.json()["user"]
    return {"Authorization": f"Bearer {token}"}, user_info


def test_api_leaderboard_endpoint():
    """Verify leaderboard endpoint returns list of users with ranking details."""
    res = client.get("/api/leaderboard")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_register_and_login():
    """Verify registration, login with form/json, me, and logout lifecycle."""
    # 1. Register new user
    res = client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    assert res.status_code in (200, 201)
    data = res.json()
    assert data["username"] == "bob"

    # 2. Duplicate registration rejected
    res_dup = client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    assert res_dup.status_code == 400

    # 3. Login with form data
    res_login_form = client.post("/api/auth/login", data={"username": "bob", "password": "password123"})
    assert res_login_form.status_code == 200
    token = res_login_form.json()["token"]
    assert token

    # 4. Login with JSON
    res_login_json = client.post("/api/auth/login", json={"username": "bob", "password": "password123"})
    assert res_login_json.status_code == 200

    # 5. Invalid password rejected
    res_bad = client.post("/api/auth/login", json={"username": "bob", "password": "wrongpassword"})
    assert res_bad.status_code == 401

    # 6. Current user /me endpoint with Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    res_me = client.get("/api/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "bob"

    # 7. Logout
    res_logout = client.post("/api/auth/logout", headers=headers)
    assert res_logout.status_code == 200

    # 8. Me endpoint is now unauthorized
    res_me_after = client.get("/api/auth/me", headers=headers)
    assert res_me_after.status_code == 401


def test_bot_upload_validation_and_management():
    """Verify bot uploads enforce sandbox AST security and management works."""
    headers, user = _create_user_and_login("bot_coder")

    # 1. Upload dangerous bot rejected by AST sandbox
    bad_code = "import os\ndef get_move(board, my_player, history):\n    return ((0,0),(1,0))\n"
    res_bad = client.post(
        "/api/bots/upload",
        files={"file": ("bad_bot.py", bad_code.encode("utf-8"), "text/x-python")},
        headers=headers,
    )
    assert res_bad.status_code == 400
    assert "Forbidden import 'os'" in res_bad.json()["detail"]

    # 2. Upload bot without get_move function rejected
    no_move_code = "def some_function():\n    pass\n"
    res_no_move = client.post(
        "/api/bots/upload",
        files={"file": ("no_move.py", no_move_code.encode("utf-8"), "text/x-python")},
        headers=headers,
    )
    assert res_no_move.status_code == 400
    assert "get_move" in res_no_move.json()["detail"]

    # 3. Upload valid bot (using starter_kit/bot_template.py)
    template_path = Path("starter_kit/bot_template.py")
    valid_code = template_path.read_text(encoding="utf-8")
    res_valid = client.post(
        "/api/bots/upload",
        files={"file": ("my_bot.py", valid_code.encode("utf-8"), "text/x-python")},
        headers=headers,
    )
    assert res_valid.status_code in (200, 201)
    bot_info = res_valid.json()
    assert bot_info["is_active"] is True
    assert bot_info["filename"] == "my_bot.py"

    # 4. List user's bots
    res_list = client.get("/api/bots", headers=headers)
    assert res_list.status_code == 200
    bots = res_list.json()
    assert len(bots) == 1
    assert bots[0]["id"] == bot_info["id"]

    # 5. Get active bot
    res_active = client.get("/api/bots/active", headers=headers)
    assert res_active.status_code == 200
    assert res_active.json()["id"] == bot_info["id"]


def test_challenge_ffa_match_lifecycle_and_replay():
    """Verify FFA challenges, background execution, replay JSON, and Elo updates."""
    # 1. Setup Admin and enable portal
    admin_headers = _create_admin_and_login("tourney_admin")
    res_open = client.post(
        "/api/admin/settings",
        json={"is_portal_open": False},
        headers=admin_headers,
    )
    assert res_open.status_code == 200

    # 2. Setup 2 players with active bots
    h1, u1 = _create_user_and_login("player_alpha")
    h2, u2 = _create_user_and_login("player_beta")

    bot_code = Path("starter_kit/bot_template.py").read_text(encoding="utf-8")
    client.post("/api/bots/upload", files={"file": ("bot1.py", bot_code.encode("utf-8"), "text/plain")}, headers=h1)
    client.post("/api/bots/upload", files={"file": ("bot2.py", bot_code.encode("utf-8"), "text/plain")}, headers=h2)

    # 3. Challenge when portal closed -> 400
    res_closed_challenge = client.post(
        "/api/matches/challenge",
        json={"opponent_id": u2["id"]},
        headers=h1,
    )
    assert res_closed_challenge.status_code == 400
    assert "portal" in res_closed_challenge.json()["detail"].lower()

    # 4. Open portal via admin
    client.post(
        "/api/admin/settings",
        json={"is_portal_open": True, "daily_multiplier_x": 1.0},
        headers=admin_headers,
    )

    # 5. Challenge when portal open -> Queued and executed via TestClient background tasks
    res_challenge = client.post(
        "/api/matches/challenge",
        json={"opponent_id": u2["id"]},
        headers=h1,
    )
    assert res_challenge.status_code in (200, 201)
    match_data = res_challenge.json()
    match_id = match_data["match_id"]

    # 6. Check match details
    res_match = client.get(f"/api/matches/{match_id}")
    assert res_match.status_code == 200
    m_info = res_match.json()
    assert m_info["id"] == match_id
    assert m_info["winner_id"] in (u1["id"], u2["id"], None)
    assert m_info["total_turns"] > 0
    assert m_info["replay_path"] is not None

    # 7. Check replay JSON endpoint
    res_replay = client.get(f"/api/matches/{match_id}/replay")
    assert res_replay.status_code == 200
    replay = res_replay.json()
    assert "moves" in replay
    assert "initial_board" in replay
    assert len(replay["moves"]) > 0

    # 8. Check leaderboard reflects match
    res_lb = client.get("/api/leaderboard")
    assert res_lb.status_code == 200
    lb = res_lb.json()
    assert len(lb) >= 2


def test_admin_settings_and_bracket():
    """Verify admin endpoints, role authorization, and bracket generation."""
    h_reg, _ = _create_user_and_login("regular_user")
    h_admin = _create_admin_and_login("super_admin")

    # 1. Regular user forbidden from admin settings
    res_forbid = client.get("/api/admin/settings", headers=h_reg)
    assert res_forbid.status_code == 403

    # 2. Admin retrieves settings
    res_get = client.get("/api/admin/settings", headers=h_admin)
    assert res_get.status_code == 200
    settings = res_get.json()
    assert "daily_multiplier_x" in settings
    assert "is_portal_open" in settings

    # 3. Admin updates settings
    res_update = client.post(
        "/api/admin/settings",
        json={"is_portal_open": True, "daily_multiplier_x": 2.5, "current_day": 3},
        headers=h_admin,
    )
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["daily_multiplier_x"] == 2.5
    assert updated["current_day"] == 3
    assert updated["is_portal_open"] is True

    # 4. Create 4 users with bots for bracket generation
    for i in range(1, 5):
        h, u = _create_user_and_login(f"bracket_seed_{i}")
        bot_code = Path("starter_kit/bot_template.py").read_text(encoding="utf-8")
        client.post(
            "/api/bots/upload",
            files={"file": (f"b{i}.py", bot_code.encode("utf-8"), "text/plain")},
            headers=h,
        )

    # 5. Generate bracket
    res_bracket = client.post("/api/admin/bracket/generate", headers=h_admin)
    assert res_bracket.status_code == 200
    matchups = res_bracket.json()
    assert len(matchups) >= 2

    # 6. Retrieve bracket
    res_get_bracket = client.get("/api/admin/bracket", headers=h_admin)
    assert res_get_bracket.status_code == 200
    assert len(res_get_bracket.json()) >= 2


def test_execute_match_job_direct(tmp_path):
    """Verify execute_match_job executes a match, calculates Elo, and writes replay."""
    init_db()
    db = SessionLocal()
    try:
        u1 = User(username="direct_u1", elo=1200)
        u1.set_password("p1")
        u2 = User(username="direct_u2", elo=1200)
        u2.set_password("p2")
        db.add_all([u1, u2])
        db.commit()

        b1_path = str(Path("starter_kit/bot_template.py").resolve())
        b2_path = str(Path("starter_kit/heuristic_bot.py").resolve())

        bot1 = Bot(user_id=u1.id, filename="bot_template.py", filepath=b1_path)
        bot2 = Bot(user_id=u2.id, filename="heuristic_bot.py", filepath=b2_path)
        db.add_all([bot1, bot2])
        db.commit()

        match = Match(
            player1_id=u1.id,
            player2_id=u2.id,
            bot1_id=bot1.id,
            bot2_id=bot2.id,
            p1_elo_before=1200,
            p2_elo_before=1200,
        )
        db.add(match)
        db.commit()
        match_id = match.id
        u1_id = u1.id
        u2_id = u2.id
    finally:
        db.close()

    # Execute match job
    execute_match_job(match_id=match_id, bot1_path=b1_path, bot2_path=b2_path, db_factory=SessionLocal)

    # Verify database updates
    db2 = SessionLocal()
    try:
        updated_match = db2.query(Match).filter(Match.id == match_id).first()
        assert updated_match is not None
        assert updated_match.winner_id is not None or updated_match.win_reason is not None
        assert updated_match.total_turns > 0
        assert updated_match.replay_path is not None
        assert Path(updated_match.replay_path).is_file()

        u1_up = db2.query(User).filter(User.id == u1_id).first()
        u2_up = db2.query(User).filter(User.id == u2_id).first()
        # Elo ratings or wins/losses updated
        assert (u1_up.wins + u1_up.losses + u1_up.draws) == 1
        assert (u2_up.wins + u2_up.losses + u2_up.draws) == 1
    finally:
        db2.close()
