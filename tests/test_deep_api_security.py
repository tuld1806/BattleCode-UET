import io
import os
import shutil
import pytest
from fastapi.testclient import TestClient
from server.main import app
from server.database import SessionLocal, init_db, engine
from server.models import User, TournamentSetting
from main import seed_admin_and_starter_bots


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Ensure clean database and tables for every security test."""
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
        shutil.rmtree("bots", ignore_errors=True)
    if os.path.exists("replays"):
        shutil.rmtree("replays", ignore_errors=True)


def test_unauthenticated_admin_endpoint_rejected():
    """Verify that accessing admin settings without authentication returns 401."""
    client = TestClient(app)

    res = client.get("/api/admin/settings")
    assert res.status_code == 401


def test_non_admin_user_forbidden_from_admin_endpoints():
    """Verify that a regular authenticated user cannot access or modify admin settings."""
    client = TestClient(app)

    # Register and login regular student user
    client.post(
        "/api/auth/register",
        json={"username": "student_deep_test", "password": "password123"},
    )
    login_res = client.post(
        "/api/auth/login",
        json={"username": "student_deep_test", "password": "password123"},
    )
    token = login_res.json()["token"]

    # Attempt to read admin settings
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/admin/settings", headers=headers)
    assert res.status_code == 403
    assert "privileges required" in res.json()["detail"].lower()

    # Attempt to modify admin settings
    res_post = client.post(
        "/api/admin/settings",
        json={"is_portal_open": True, "daily_multiplier_x": 2.5},
        headers=headers,
    )
    assert res_post.status_code == 403


def test_spoofed_or_expired_session_token():
    """Verify that arbitrary or forged session tokens are rejected with 401."""
    client = TestClient(app)
    forged_tokens = [
        "Bearer fake_token_abc123456789",
        "Bearer " + "0" * 48,
        "Bearer non_existent_token",
    ]
    for token_header in forged_tokens:
        res = client.get("/api/auth/me", headers={"Authorization": token_header})
        assert res.status_code == 401


def test_nonexistent_replay_returns_404_not_500():
    """Verify that requesting a nonexistent match replay returns clean 404 rather than unhandled 500."""
    client = TestClient(app)
    res = client.get("/api/matches/99999999/replay")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_upload_oversized_bot_rejected():
    """Verify that uploading a bot exceeding 1MB is rejected with 400 Bad Request."""
    client = TestClient(app)

    # Register and login
    client.post(
        "/api/auth/register",
        json={"username": "uploader_user", "password": "password123"},
    )
    login_res = client.post(
        "/api/auth/login",
        json={"username": "uploader_user", "password": "password123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Generate 5.5MB dummy Python file (>5MB payload check)
    large_code = "def get_move(board, my_player, history):\n    return ((0, 0), (1, 1))\n" + "#" * (5_500_000)
    file_bytes = io.BytesIO(large_code.encode("utf-8"))

    res = client.post(
        "/api/bots/upload",
        files={"file": ("giant_bot.py", file_bytes, "text/x-python")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "exceeds maximum" in res.json()["detail"].lower()


def test_challenge_self_strictly_rejected():
    """Verify user cannot challenge their own bot."""
    client = TestClient(app)

    # Register & login
    client.post(
        "/api/auth/register",
        json={"username": "self_challenger", "password": "password123"},
    )
    login = client.post(
        "/api/auth/login",
        json={"username": "self_challenger", "password": "password123"},
    )
    token = login.json()["token"]
    user_id = login.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Force open FFA portal in DB
    db = SessionLocal()
    try:
        setting = db.query(TournamentSetting).filter(TournamentSetting.key == "is_portal_open").first()
        if not setting:
            setting = TournamentSetting(key="is_portal_open", value="true")
            db.add(setting)
        else:
            setting.value = "true"
        db.commit()
    finally:
        db.close()

    res = client.post(
        "/api/matches/challenge",
        json={"opponent_id": user_id},
        headers=headers,
    )
    assert res.status_code == 400
    assert "cannot challenge yourself" in res.json()["detail"].lower()
