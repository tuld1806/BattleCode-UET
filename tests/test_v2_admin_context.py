"""Unit tests for contextual admin per game (/admin/games/{slug})."""

import pytest
from fastapi.testclient import TestClient

from server.database import get_db_context, init_db
from server.main import app
from server.models import Game, Tournament, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_admin_game_context_page_requires_admin():
    """Verify anonymous access is redirected to login."""
    res = client.get("/admin/games/rps-chess", follow_redirects=False)
    assert res.status_code in [303, 401, 403]


def test_admin_game_context_page_renders_for_admin():
    """Verify admin user can load the contextual admin dashboard for a game."""
    with get_db_context() as db:
        admin = db.query(User).filter(User.username == "admin_context_test").first()
        if not admin:
            admin = User(username="admin_context_test", is_admin=True)
            admin.set_password("AdminPass123!")
            db.add(admin)
            db.commit()

    login_res = client.post(
        "/api/auth/login",
        json={"username": "admin_context_test", "password": "AdminPass123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies

    res = client.get("/admin/games/rps-chess", cookies=cookies)
    assert res.status_code == 200
    assert "rps-chess" in res.text or "Oan Tu Ti" in res.text


def test_admin_deploy_and_retract_boss_scoped_to_game():
    """Verify admin can deploy and retract bosses scoped to the game slug."""
    login_res = client.post(
        "/api/auth/login",
        json={"username": "admin_context_test", "password": "AdminPass123!"},
    )
    cookies = login_res.cookies

    # Deploy boss
    dep_res = client.post(
        "/api/admin/games/rps-chess/bosses/deploy",
        json={"boss_slug": "novice"},
        cookies=cookies,
    )
    assert dep_res.status_code == 200
    data = dep_res.json()
    assert data.get("is_deployed") is True or data.get("status") in ["deployed", "active"]

    # Retract boss
    ret_res = client.post(
        "/api/admin/games/rps-chess/bosses/retract",
        json={"boss_slug": "novice"},
        cookies=cookies,
    )
    assert ret_res.status_code == 200
    ret_data = ret_res.json()
    assert ret_data.get("is_deployed") is False or ret_data.get("status") in ["retracted", "inactive"]


def test_admin_create_tournament_in_game_context():
    """Verify creating a tournament via contextual game admin route scopes game_id automatically."""
    login_res = client.post(
        "/api/auth/login",
        json={"username": "admin_context_test", "password": "AdminPass123!"},
    )
    cookies = login_res.cookies

    tourney_name = "Context Scoped Tourney Test"
    res = client.post(
        "/api/admin/games/rps-chess/tournaments",
        json={
            "name": tourney_name,
            "ffa_start_time": "20:00",
            "ffa_end_time": "22:00",
            "bracket_top_n": 8,
        },
        cookies=cookies,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == tourney_name
    assert "id" in data

    with get_db_context() as db:
        game = db.query(Game).filter(Game.slug == "rps-chess").first()
        tourney = db.query(Tournament).filter(Tournament.id == data["id"]).first()
        assert tourney is not None
        assert tourney.game_id == game.id
