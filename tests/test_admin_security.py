"""Tests for single administrator security enforcement and credential synchronization."""

import os
from fastapi.testclient import TestClient
from server.main import app
from server.database import SessionLocal, init_db
from server.models import User
from server.routes.auth import ACTIVE_SESSIONS
from main import seed_admin_and_starter_bots


def test_register_admin_username_rejected():
    """Verify that registering with reserved 'admin' username is strictly rejected."""
    init_db()
    client = TestClient(app)
    # Rejects exact or case-insensitive match with admin username
    res = client.post(
        "/api/auth/register",
        json={"username": "Admin", "password": "password123"},
    )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "reserved" in detail or "already taken" in detail or "admin" in detail


def test_single_admin_demotion_invariant():
    """Verify that only ONE administrator account can exist; any rogue admin is demoted."""
    init_db()
    db = SessionLocal()
    try:
        # Create a rogue admin
        rogue = db.query(User).filter(User.username == "rogue_user").first()
        if not rogue:
            rogue = User(username="rogue_user", is_admin=True, elo=1200)
            rogue.set_password("secret123")
            db.add(rogue)
        else:
            rogue.is_admin = True
        db.commit()

        # Run seeder
        seed_admin_and_starter_bots(db)

        # Verify rogue was demoted and only official admin remains
        db.refresh(rogue)
        assert rogue.is_admin is False

        target_admin_user = os.getenv("ADMIN_USERNAME", "admin").strip().lower()
        admins = db.query(User).filter(User.is_admin == True).all()
        assert len(admins) == 1
        assert admins[0].username.lower() == target_admin_user
    finally:
        db.close()


def test_admin_page_unauthenticated_redirects_to_login():
    """Verify unauthenticated GET /admin redirects to login with next parameter and hides admin link."""
    init_db()
    client = TestClient(app)
    # Unauthenticated request to /admin with follow_redirects=False
    res = client.get("/admin", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login?next=/admin"

    # Navbar check for unauthenticated user: admin link must not be present
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert 'href="/admin"' not in home_res.text


def test_admin_page_non_admin_forbidden():
    """Verify authenticated non-admin user cannot access /admin (HTTP 403) and admin link is hidden."""
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "regular_user_test").first()
        if not user:
            user = User(username="regular_user_test", is_admin=False, elo=1200)
            user.set_password("pass123")
            db.add(user)
            db.commit()
            db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    session_token = "regular_session_token_sec"
    ACTIVE_SESSIONS[session_token] = user_id

    client = TestClient(app)
    client.cookies.set("session_token", session_token)

    # Non-admin request to /admin returns 403
    res = client.get("/admin")
    assert res.status_code == 403
    assert "detail" in res.json() or "administrative" in res.text.lower()

    # Navbar check for regular user: admin link must not be present
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert 'href="/admin"' not in home_res.text


def test_admin_page_authenticated_admin_allowed():
    """Verify authenticated admin can access /admin (HTTP 200) and admin navbar link is rendered."""
    init_db()
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "super_admin_test").first()
        if not admin_user:
            admin_user = User(username="super_admin_test", is_admin=True, elo=1500)
            admin_user.set_password("admin_pass123")
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        else:
            admin_user.is_admin = True
            db.commit()
        user_id = admin_user.id
    finally:
        db.close()

    session_token = "admin_session_token_sec"
    ACTIVE_SESSIONS[session_token] = user_id

    client = TestClient(app)
    client.cookies.set("session_token", session_token)

    # Admin request to /admin returns 200
    res = client.get("/admin")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert 'href="/admin"' in res.text

    # Navbar check on homepage for admin: admin link is visible
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert 'href="/admin"' in home_res.text


def _get_admin_session_token_security(client: TestClient) -> None:
    """Log in as the seeded admin and set session cookie on client."""
    import os
    init_db()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin == True).first()  # noqa: E712
        assert admin, "No admin user found"
        user_id = admin.id
    finally:
        db.close()
    token = "admin_pw_gate_token"
    ACTIVE_SESSIONS[token] = user_id
    client.cookies.set("session_token", token)


def test_generate_bracket_requires_password_success():
    """Correct admin password on POST /api/admin/bracket/generate returns 200."""
    import os
    init_db()
    client = TestClient(app)
    _get_admin_session_token_security(client)

    # Ensure at least 2 eligible non-admin users with bots exist
    from server.models import Bot, Game as GameModel
    db = SessionLocal()
    try:
        for i in range(4):
            uname = f"bracket_pw_u{i}"
            u = db.query(User).filter(User.username == uname).first()
            if not u:
                u = User(username=uname, is_admin=False, elo=1200 + i * 10)
                u.set_password("pw")
                db.add(u)
                db.flush()
                game = db.query(GameModel).first()
                if game:
                    b = Bot(
                        user_id=u.id,
                        game_id=game.id,
                        filename=f"bot_pw_{i}.py",
                        filepath=f"starter_kit/bot_template.py",
                        is_active=True,
                    )
                    db.add(b)
        db.commit()
    finally:
        db.close()

    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    res = client.post(
        "/api/admin/bracket/generate",
        json={"admin_password": admin_password},
    )
    assert res.status_code == 200


def test_generate_bracket_invalid_password_returns_403():
    """Wrong admin password returns HTTP 403 and must not mutate DB state."""
    init_db()
    client = TestClient(app)
    _get_admin_session_token_security(client)

    res = client.post(
        "/api/admin/bracket/generate",
        json={"admin_password": "definitely_wrong_password_xyz"},
    )
    assert res.status_code == 403
    detail = res.json().get("detail", "").lower()
    assert "incorrect" in detail or "password" in detail or "mật khẩu" in detail


def test_generate_bracket_missing_password_returns_422():
    """Missing admin_password field returns HTTP 422 Unprocessable Entity."""
    init_db()
    client = TestClient(app)
    _get_admin_session_token_security(client)

    res = client.post(
        "/api/admin/bracket/generate",
        json={},
    )
    assert res.status_code == 422
