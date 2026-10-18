"""Integration tests for Admin Game Management API routes (server/routes/admin_games.py)."""

import io
import zipfile
import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.database import Base, get_db
from server.main import app
from server.models import Game, User
from server.routes.auth import ACTIVE_SESSIONS


@pytest.fixture
def client_and_db(tmp_path):
    """Create test client with isolated in-memory DB and authenticated sessions."""
    db_file = tmp_path / "test_admin_games.db"
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

    # Create admin and normal user
    session = TestingSession()
    admin_user = User(username="admin_test", is_admin=True)
    admin_user.set_password("admin_pass")
    normal_user = User(username="player_test", is_admin=False)
    normal_user.set_password("player_pass")

    existing_game = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    session.add_all([admin_user, normal_user, existing_game])
    session.commit()

    admin_token = "admin-test-token"
    player_token = "player-test-token"
    ACTIVE_SESSIONS[admin_token] = admin_user.id
    ACTIVE_SESSIONS[player_token] = normal_user.id

    client = TestClient(app)

    yield {
        "client": client,
        "admin_token": admin_token,
        "player_token": player_token,
        "session": session,
    }

    app.dependency_overrides.clear()
    ACTIVE_SESSIONS.pop(admin_token, None)
    ACTIVE_SESSIONS.pop(player_token, None)
    session.close()


def test_admin_games_auth_guard(client_and_db):
    """Endpoints must require admin privileges."""
    client = client_and_db["client"]
    player_token = client_and_db["player_token"]
    admin_token = client_and_db["admin_token"]

    # 1. Unauthenticated -> 401
    resp = client.get("/api/admin/games")
    assert resp.status_code == 401

    # 2. Player token -> 403
    resp = client.get("/api/admin/games", headers={"Authorization": f"Bearer {player_token}"})
    assert resp.status_code == 403

    # 3. Admin token -> 200
    resp = client.get("/api/admin/games", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(g["slug"] == "rps-chess" for g in data)


def test_admin_games_upload_valid_plugin(client_and_db, tmp_path):
    """Uploading a valid plugin zip must unpack, register in DB, and return 200."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]
    db = client_and_db["session"]

    # Build valid zip in memory
    engine_py = """from engine.base import GameEngine

class SampleEngine(GameEngine):
    def get_initial_state(self, p1, p2): return {}
    def get_player_view(self, state, p): return state
    def apply_action(self, state, p, a): return state
    def check_winner(self, state): return (None, 'ongoing')
    def is_action_valid(self, state, p, a): return True
    def get_max_turns(self): return 50
    def score_for_tiebreak(self, state, p): return 0.0
"""
    config_yaml = yaml.dump({
        "slug": "sample-game",
        "display_name": "Sample Game Plugin",
        "description_md": "A test sample game plugin",
    })

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("engine.py", engine_py)
        zf.writestr("config.yaml", config_yaml)
    zip_bytes = zip_buffer.getvalue()

    resp = client.post(
        "/api/admin/games/upload",
        files={"file": ("sample-game.zip", zip_bytes, "application/zip")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    body = resp.json()
    assert body["status"] == "success"
    assert body["game"]["slug"] == "sample-game"

    # Verify persisted in database
    db.expire_all()
    created_game = db.query(Game).filter(Game.slug == "sample-game").first()
    assert created_game is not None
    assert created_game.is_active is True


def test_admin_games_upload_malicious_plugin_rejected(client_and_db):
    """Uploading a zip with forbidden AST imports must be rejected with HTTP 400."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]

    malicious_engine_py = """import os
from engine.base import GameEngine

class ExploitEngine(GameEngine):
    def get_initial_state(self, p1, p2):
        os.system('echo pwned')
        return {}
    def get_player_view(self, state, p): return state
    def apply_action(self, state, p, a): return state
    def check_winner(self, state): return (None, 'ongoing')
    def is_action_valid(self, state, p, a): return True
    def get_max_turns(self): return 10
    def score_for_tiebreak(self, state, p): return 0.0
"""
    config_yaml = yaml.dump({
        "slug": "malicious-game",
        "display_name": "Malicious Game",
    })

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("engine.py", malicious_engine_py)
        zf.writestr("config.yaml", config_yaml)
    zip_bytes = zip_buffer.getvalue()

    resp = client.post(
        "/api/admin/games/upload",
        files={"file": ("malicious.zip", zip_bytes, "application/zip")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "Forbidden" in resp.json()["detail"] or "os" in resp.json()["detail"]


def test_admin_games_toggle_status(client_and_db):
    """Toggling game active status should switch between True and False."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]
    db = client_and_db["session"]

    # Initial state is True
    game = db.query(Game).filter(Game.slug == "rps-chess").first()
    assert game.is_active is True

    # 1. Toggle to False
    resp = client.post(
        "/api/admin/games/rps-chess/toggle",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    db.expire_all()
    assert game.is_active is False

    # 2. Toggle back to True
    resp = client.post(
        "/api/admin/games/rps-chess/toggle",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    db.expire_all()
    assert game.is_active is True


def test_admin_games_toggle_nonexistent_returns_404(client_and_db):
    """Toggling unknown slug must return 404."""
    client = client_and_db["client"]
    admin_token = client_and_db["admin_token"]

    resp = client.post(
        "/api/admin/games/unknown-slug/toggle",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
