"""Tests for dynamic web-based tournament schedule configuration and evaluation."""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server.database import SessionLocal, engine, init_db
from server.main import app
from server.models import Bot, TournamentSetting, User
from server.tournament import is_ffa_portal_open
from server.tournament_config import load_tournament_config

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


def _create_admin_and_login(username="schedule_admin", password="adminpassword123"):
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


def _create_user_and_login(username="player_sched", password="testpassword123"):
    """Helper to register and login a regular user, returning auth header and user info."""
    res_reg = client.post("/api/auth/register", json={"username": username, "password": password})
    assert res_reg.status_code in (200, 201)

    res_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res_login.status_code == 200
    token = res_login.json()["token"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        user_dict = {"id": user.id, "username": user.username}
    finally:
        db.close()

    return {"Authorization": f"Bearer {token}"}, user_dict


def test_is_ffa_portal_open_auto_mode_standard_window():
    """Verify portal evaluation with dynamic db_settings in auto mode for daytime windows."""
    config = load_tournament_config()
    db_settings = {
        "start_time": "14:00",
        "end_time": "18:00",
        "is_portal_open": "auto",
    }
    # Within window
    assert is_ffa_portal_open(config, current_time_str="14:00", db_settings=db_settings) is True
    assert is_ffa_portal_open(config, current_time_str="16:00", db_settings=db_settings) is True
    assert is_ffa_portal_open(config, current_time_str="18:00", db_settings=db_settings) is True

    # Outside window
    assert is_ffa_portal_open(config, current_time_str="13:59", db_settings=db_settings) is False
    assert is_ffa_portal_open(config, current_time_str="18:01", db_settings=db_settings) is False
    assert is_ffa_portal_open(config, current_time_str="09:00", db_settings=db_settings) is False


def test_is_ffa_portal_open_auto_mode_overnight_window():
    """Verify portal evaluation with dynamic db_settings for overnight windows across midnight."""
    config = load_tournament_config()
    db_settings = {
        "start_time": "22:00",
        "end_time": "02:00",
        "is_portal_open": "auto",
    }
    # Late night before midnight
    assert is_ffa_portal_open(config, current_time_str="22:00", db_settings=db_settings) is True
    assert is_ffa_portal_open(config, current_time_str="23:30", db_settings=db_settings) is True
    assert is_ffa_portal_open(config, current_time_str="00:00", db_settings=db_settings) is True

    # Early morning after midnight
    assert is_ffa_portal_open(config, current_time_str="01:15", db_settings=db_settings) is True
    assert is_ffa_portal_open(config, current_time_str="02:00", db_settings=db_settings) is True

    # Daytime outside overnight window
    assert is_ffa_portal_open(config, current_time_str="02:01", db_settings=db_settings) is False
    assert is_ffa_portal_open(config, current_time_str="12:00", db_settings=db_settings) is False
    assert is_ffa_portal_open(config, current_time_str="21:59", db_settings=db_settings) is False


def test_is_ffa_portal_open_force_overrides_ignore_schedule():
    """Verify force open ('true') and force close ('false') overrides bypass time window."""
    config = load_tournament_config()

    # Force open overrides closed time
    db_open = {
        "start_time": "19:00",
        "end_time": "21:00",
        "is_portal_open": "true",
    }
    assert is_ffa_portal_open(config, current_time_str="08:00", db_settings=db_open) is True
    assert is_ffa_portal_open(config, current_time_str="23:00", db_settings=db_open) is True

    # Force closed overrides open time
    db_closed = {
        "start_time": "19:00",
        "end_time": "21:00",
        "is_portal_open": "false",
    }
    assert is_ffa_portal_open(config, current_time_str="20:00", db_settings=db_closed) is False
    assert is_ffa_portal_open(config, current_time_str="19:30", db_settings=db_closed) is False

    # Check portal_mode key fallback
    db_mode_open = {"start_time": "19:00", "end_time": "21:00", "portal_mode": "true"}
    assert is_ffa_portal_open(config, current_time_str="08:00", db_settings=db_mode_open) is True

    db_mode_closed = {"start_time": "19:00", "end_time": "21:00", "portal_mode": "false"}
    assert is_ffa_portal_open(config, current_time_str="20:00", db_settings=db_mode_closed) is False


def test_admin_post_settings_persists_schedule_to_db():
    """Verify POST /api/admin/settings persists start_time, end_time, and portal_mode to SQLite."""
    admin_headers = _create_admin_and_login()

    payload = {
        "start_time": "22:00",
        "end_time": "02:00",
        "portal_mode": "auto",
        "daily_multiplier_x": 2.0,
    }
    res = client.post("/api/admin/settings", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["start_time"] == "22:00"
    assert data["end_time"] == "02:00"
    assert data["portal_mode"] == "auto"

    # Verify rows in TournamentSetting table
    db = SessionLocal()
    try:
        st_row = db.query(TournamentSetting).filter(TournamentSetting.key == "start_time").first()
        assert st_row is not None and st_row.value == "22:00"

        et_row = db.query(TournamentSetting).filter(TournamentSetting.key == "end_time").first()
        assert et_row is not None and et_row.value == "02:00"

        mode_row = db.query(TournamentSetting).filter(TournamentSetting.key == "portal_mode").first()
        assert mode_row is not None and mode_row.value == "auto"
    finally:
        db.close()

    # Verify GET /api/admin/settings reflects saved values
    res_get = client.get("/api/admin/settings", headers=admin_headers)
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["start_time"] == "22:00"
    assert get_data["end_time"] == "02:00"
    assert get_data["portal_mode"] == "auto"


def test_challenge_opponent_honors_dynamic_schedule():
    """Verify /api/matches/challenge obeys the database-driven schedule and overrides."""
    admin_headers = _create_admin_and_login()
    h1, u1 = _create_user_and_login("player_alpha")
    h2, u2 = _create_user_and_login("player_beta")

    # Upload valid bots for both users
    bot_code = Path("starter_kit/bot_template.py").read_text(encoding="utf-8")
    client.post("/api/bots/upload", files={"file": ("b1.py", bot_code.encode("utf-8"), "text/plain")}, headers=h1)
    client.post("/api/bots/upload", files={"file": ("b2.py", bot_code.encode("utf-8"), "text/plain")}, headers=h2)

    # 1. Force closed -> challenge fails with 400
    client.post("/api/admin/settings", json={"portal_mode": "false"}, headers=admin_headers)
    res_closed = client.post("/api/matches/challenge", json={"opponent_id": u2["id"]}, headers=h1)
    assert res_closed.status_code == 400
    assert "portal" in res_closed.json()["detail"].lower()

    # 2. Force open -> challenge succeeds
    client.post("/api/admin/settings", json={"portal_mode": "true"}, headers=admin_headers)
    res_opened = client.post("/api/matches/challenge", json={"opponent_id": u2["id"]}, headers=h1)
    assert res_opened.status_code in (200, 201)

    # 3. Auto mode with full-day window [00:00, 23:59] -> challenge succeeds
    client.post(
        "/api/admin/settings",
        json={"portal_mode": "auto", "start_time": "00:00", "end_time": "23:59"},
        headers=admin_headers,
    )
    res_auto_open = client.post("/api/matches/challenge", json={"opponent_id": u2["id"]}, headers=h1)
    assert res_auto_open.status_code in (200, 201)

    # 4. Auto mode with 0-minute past window [03:00, 03:00] when current time is not 03:00 -> challenge fails
    # Use window definitely outside current hour if current hour isn't 04:00
    from datetime import datetime
    now_hour = datetime.now().hour
    closed_hour = (now_hour + 6) % 24
    st_str = f"{closed_hour:02d}:00"
    et_str = f"{closed_hour:02d}:01"
    client.post(
        "/api/admin/settings",
        json={"portal_mode": "auto", "start_time": st_str, "end_time": et_str},
        headers=admin_headers,
    )
    res_auto_closed = client.post("/api/matches/challenge", json={"opponent_id": u2["id"]}, headers=h1)
    assert res_auto_closed.status_code == 400
    assert "portal" in res_auto_closed.json()["detail"].lower()
