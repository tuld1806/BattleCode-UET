"""Integration tests for administrator boss deployment API and arena management."""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server.bosses import BOSS_REGISTRY
from server.database import SessionLocal, engine, init_db
from server.main import app
from server.models import Bot, TournamentSetting, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Ensure clean database and tables for every test."""
    init_db()
    yield
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


def _create_admin_and_login(username="boss_admin", password="adminpassword123"):
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


def _create_user_and_login(username="student_user", password="studentpassword123"):
    """Helper to register and login a regular user, returning auth header and user info."""
    res_reg = client.post("/api/auth/register", json={"username": username, "password": password})
    assert res_reg.status_code in (200, 201)

    res_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res_login.status_code == 200
    token = res_login.json()["token"]
    user_id = res_login.json()["user"]["id"]
    return {"Authorization": f"Bearer {token}"}, user_id


def test_bosses_auth_protection():
    """Verify GET and POST /api/admin/bosses endpoints reject unauthenticated and non-admin requests."""
    fresh_client = TestClient(app)

    # 1. Unauthenticated requests return 401
    res_unauth_get = fresh_client.get("/api/admin/bosses")
    assert res_unauth_get.status_code == 401

    res_unauth_post = fresh_client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "deploy"},
    )
    assert res_unauth_post.status_code == 401

    # 2. Non-admin requests return 403
    student_headers, _ = _create_user_and_login()
    res_student_get = client.get("/api/admin/bosses", headers=student_headers)
    assert res_student_get.status_code == 403

    res_student_post = client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "deploy"},
        headers=student_headers,
    )
    assert res_student_post.status_code == 403

    # 3. Admin requests succeed
    admin_headers = _create_admin_and_login()
    res_admin_get = client.get("/api/admin/bosses", headers=admin_headers)
    assert res_admin_get.status_code == 200


def test_get_all_bosses_status():
    """Verify GET /api/admin/bosses returns all 5 registered bosses with expected metadata fields."""
    admin_headers = _create_admin_and_login()
    res = client.get("/api/admin/bosses", headers=admin_headers)
    assert res.status_code == 200
    bosses = res.json()

    assert len(bosses) == 5
    expected_slugs = ["novice", "rusher", "sentinel", "tactician", "apex"]

    for idx, boss in enumerate(bosses):
        assert boss["boss_slug"] == expected_slugs[idx]
        assert boss["level"] == idx + 1
        assert "display_name" in boss
        assert "description" in boss
        assert "is_deployed" in boss
        assert "elo" in boss
        assert boss["is_deployed"] is False
        assert boss["elo"] == BOSS_REGISTRY[boss["boss_slug"]]["default_elo"]


def test_deploy_boss_creates_user_and_active_bot():
    """Verify deploying novice boss creates user with calibrated Elo, active bot, and leaderboard visibility."""
    admin_headers = _create_admin_and_login()

    deploy_res = client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "deploy"},
        headers=admin_headers,
    )
    assert deploy_res.status_code == 200
    data = deploy_res.json()
    assert data["boss_slug"] == "novice"
    assert data["is_deployed"] is True
    assert data["elo"] == 1000

    # Verify user account in database
    db = SessionLocal()
    try:
        boss_user = db.query(User).filter(User.username == "[Boss] Level 1: Novice").first()
        assert boss_user is not None
        assert boss_user.elo == 1000
        assert boss_user.is_admin is False

        # Verify active bot record
        boss_bot = db.query(Bot).filter(Bot.user_id == boss_user.id).first()
        assert boss_bot is not None
        assert boss_bot.is_active is True
        assert Path(boss_bot.filepath).exists()
    finally:
        db.close()

    # Verify appearance on leaderboard
    res_lb = client.get("/api/leaderboard")
    assert res_lb.status_code == 200
    lb_entries = res_lb.json()
    boss_entry = next((entry for entry in lb_entries if entry["username"] == "[Boss] Level 1: Novice"), None)
    assert boss_entry is not None
    assert boss_entry["elo"] == 1000
    assert boss_entry["has_active_bot"] is True


def test_retract_boss_deactivates_bot():
    """Verify retracting boss deactivates bot record and removes from active matchmaking."""
    admin_headers = _create_admin_and_login()

    # Deploy novice boss
    client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "deploy"},
        headers=admin_headers,
    )

    # Retract novice boss
    retract_res = client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "retract"},
        headers=admin_headers,
    )
    assert retract_res.status_code == 200
    data = retract_res.json()
    assert data["boss_slug"] == "novice"
    assert data["is_deployed"] is False

    # Verify in DB
    db = SessionLocal()
    try:
        boss_user = db.query(User).filter(User.username == "[Boss] Level 1: Novice").first()
        assert boss_user is not None
        boss_bot = db.query(Bot).filter(Bot.user_id == boss_user.id).first()
        assert boss_bot is not None
        assert boss_bot.is_active is False
    finally:
        db.close()

    # GET /api/admin/bosses reports is_deployed = False
    res_bosses = client.get("/api/admin/bosses", headers=admin_headers)
    novice_info = next(b for b in res_bosses.json() if b["boss_slug"] == "novice")
    assert novice_info["is_deployed"] is False


def test_student_can_challenge_deployed_boss():
    """Verify student user can challenge deployed boss in FFA matchmaking when portal is open."""
    admin_headers = _create_admin_and_login()
    student_headers, student_id = _create_user_and_login()

    # Open tournament portal via admin settings
    client.post("/api/admin/settings", json={"portal_mode": "true"}, headers=admin_headers)

    # Deploy novice boss
    client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "deploy"},
        headers=admin_headers,
    )

    db = SessionLocal()
    try:
        boss_user = db.query(User).filter(User.username == "[Boss] Level 1: Novice").first()
        assert boss_user is not None
        boss_user_id = boss_user.id

        # Give student an active bot
        student_bot = Bot(
            user_id=student_id,
            filename="student_bot.py",
            filepath=BOSS_REGISTRY["novice"]["file_path"],
            is_active=True,
        )
        db.add(student_bot)
        db.commit()
    finally:
        db.close()

    # Student challenges deployed boss
    res_challenge = client.post(
        "/api/matches/challenge",
        json={"opponent_id": boss_user_id},
        headers=student_headers,
    )
    assert res_challenge.status_code == 201
    challenge_data = res_challenge.json()
    assert challenge_data["status"] == "queued"
    assert challenge_data["player2_id"] == boss_user_id

    # Now retract boss and confirm subsequent challenge fails
    client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "retract"},
        headers=admin_headers,
    )
    res_challenge_fail = client.post(
        "/api/matches/challenge",
        json={"opponent_id": boss_user_id},
        headers=student_headers,
    )
    assert res_challenge_fail.status_code == 400
    assert "active bot" in res_challenge_fail.json()["detail"].lower()


def test_repeated_deployment_idempotence():
    """Verify repeated deployments do not create duplicate user accounts or orphan bot records."""
    admin_headers = _create_admin_and_login()

    # Deploy 3 times consecutively
    for _ in range(3):
        res = client.post(
            "/api/admin/bosses/deploy",
            json={"boss_slug": "novice", "action": "deploy"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["is_deployed"] is True

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.username == "[Boss] Level 1: Novice").all()
        assert len(users) == 1
        bots = db.query(Bot).filter(Bot.user_id == users[0].id).all()
        assert len(bots) == 1
        assert bots[0].is_active is True
    finally:
        db.close()

    # Retract and redeploy
    client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "retract"},
        headers=admin_headers,
    )
    client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "deploy"},
        headers=admin_headers,
    )

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.username == "[Boss] Level 1: Novice").all()
        assert len(users) == 1
        bots = db.query(Bot).filter(Bot.user_id == users[0].id).all()
        assert len(bots) == 1
        assert bots[0].is_active is True
    finally:
        db.close()


def test_admin_page_renders_boss_arena():
    """Verify admin portal HTML renders Benchmark Boss Arena section with all 5 bosses."""
    admin_headers = _create_admin_and_login()
    res = client.get("/admin", headers=admin_headers)
    assert res.status_code == 200
    html = res.text
    assert "Benchmark Boss Arena" in html
    assert "boss-card-novice" in html
    assert "boss-card-rusher" in html
    assert "boss-card-sentinel" in html
    assert "boss-card-tactician" in html
    assert "boss-card-apex" in html


def test_deploy_boss_invalid_slug_and_action():
    """Verify deploy API rejects invalid boss slugs with 404 and invalid actions with 400."""
    admin_headers = _create_admin_and_login()

    # Invalid slug
    res_bad_slug = client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "nonexistent_boss", "action": "deploy"},
        headers=admin_headers,
    )
    assert res_bad_slug.status_code == 404

    # Invalid action
    res_bad_action = client.post(
        "/api/admin/bosses/deploy",
        json={"boss_slug": "novice", "action": "explode"},
        headers=admin_headers,
    )
    assert res_bad_action.status_code == 400

