"""Integration tests for web UI routes and template rendering."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.database import Base, SessionLocal, engine
from server.main import app
from server.models import Bot, Match, TournamentSetting, User
from server.routes.auth import ACTIVE_SESSIONS


@pytest.fixture(autouse=True)
def setup_clean_db():
    """Reset database tables before each test case."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ACTIVE_SESSIONS.clear()
    yield
    Base.metadata.drop_all(bind=engine)
    ACTIVE_SESSIONS.clear()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_index_page_returns_200_and_renders_leaderboard(client: TestClient) -> None:
    """Verify that the home page (/) returns 200 and contains leaderboard elements."""
    db = SessionLocal()
    user = User(username="alice", elo=1350, wins=5, losses=1, draws=0)
    user.set_password("password123")
    db.add(user)
    db.commit()
    db.close()

    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    text = res.text
    assert "Leaderboard" in text or "Bảng xếp hạng" in text
    assert "alice" in text
    assert "1350" in text
    assert "portal" in text.lower() or "cổng" in text.lower()


def test_index_page_authenticated_user_highlight(client: TestClient) -> None:
    """Verify that an authenticated user sees their badge and 'Bạn' tag on leaderboard."""
    db = SessionLocal()
    user = User(username="charlie", elo=1420, wins=10, losses=2, draws=1)
    user.set_password("secret456")
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    session_token = "valid_session_token_123"
    ACTIVE_SESSIONS[session_token] = user_id

    client.cookies.set("session_token", session_token)
    res = client.get("/")
    assert res.status_code == 200
    assert "charlie" in res.text
    assert "Logout" in res.text
    assert "Bạn" in res.text


def test_login_page_returns_200_and_renders_form(client: TestClient) -> None:
    """Verify that /login returns 200 with authentication form inputs."""
    res = client.get("/login")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    text = res.text
    assert "username" in text.lower()
    assert "password" in text.lower()
    assert "<form" in text.lower()


def test_register_page_returns_200_and_renders_form(client: TestClient) -> None:
    """Verify that /register returns 200 with registration form inputs."""
    res = client.get("/register")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    text = res.text
    assert "username" in text.lower()
    assert "password" in text.lower()
    assert "<form" in text.lower()


def test_profile_page_returns_200_and_renders_bot_upload(client: TestClient) -> None:
    """Verify that /profile returns 200 with bot upload and match history elements."""
    res = client.get("/profile")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    text = res.text
    assert "upload" in text.lower() or "tải lên" in text.lower()
    assert ".py" in text
    assert "bot" in text.lower()


def test_profile_page_authenticated_renders_bots_and_matches(client: TestClient) -> None:
    """Verify that an authenticated user sees their uploaded bots and match history."""
    db = SessionLocal()
    user = User(username="botmaster", elo=1500, wins=3, losses=1, draws=0)
    user.set_password("pass123")
    db.add(user)
    db.commit()

    bot = Bot(user_id=user.id, filename="alpha_bot.py", filepath="bots/alpha.py", is_active=True)
    db.add(bot)

    match = Match(
        player1_id=user.id,
        player2_id=user.id,
        bot1_id=bot.id,
        bot2_id=bot.id,
        winner_id=user.id,
        win_reason="goal",
        total_turns=24,
    )
    db.add(match)
    db.commit()
    user_id = user.id
    db.close()

    session_token = "botmaster_token_abc"
    ACTIVE_SESSIONS[session_token] = user_id

    client.cookies.set("session_token", session_token)
    res = client.get("/profile")
    assert res.status_code == 200
    text = res.text
    assert "alpha_bot.py" in text
    assert "Đang kích hoạt" in text
    assert "#1" in text or "goal" in text


def test_replay_page_returns_200_and_renders_board_container(client: TestClient) -> None:
    """Verify that /replay/{match_id} returns 200 with 9x9 board visualizer components."""
    res = client.get("/replay/1")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    text = res.text
    assert "board" in text.lower()
    assert "visualizer.js" in text
    assert "play" in text.lower() or "speed" in text.lower()


def test_admin_page_returns_200_and_renders_settings_form(client: TestClient) -> None:
    """Verify that /admin returns 200 with tournament settings and bracket generator for admin."""
    db = SessionLocal()
    admin_user = User(username="admin_tester", is_admin=True, elo=1500)
    admin_user.set_password("adminpass123")
    db.add(admin_user)
    db.commit()
    user_id = admin_user.id
    db.close()

    session_token = "admin_session_token_web"
    ACTIVE_SESSIONS[session_token] = user_id
    client.cookies.set("session_token", session_token)

    res = client.get("/admin")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    text = res.text
    assert "admin" in text.lower() or "quản trị" in text.lower()
    assert "bracket" in text.lower() or "nhánh đấu" in text.lower()
    assert "multiplier" in text.lower() or "hệ số" in text.lower()


def test_bracket_page_returns_200_and_renders_bracket_view(client: TestClient) -> None:
    """Verify that /bracket returns 200 with bracket tree/table components."""
    res = client.get("/bracket")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    text = res.text
    assert "bracket" in text.lower() or "nhánh đấu" in text.lower()


def test_static_files_served_properly(client: TestClient) -> None:
    """Verify that static CSS and JS assets are successfully served."""
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers["content-type"]
    assert "--cell" in css_res.text or "board" in css_res.text

    js_res = client.get("/static/js/visualizer.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers["content-type"] or "text/plain" in js_res.headers["content-type"]
    assert "ReplayVisualizer" in js_res.text


def test_minimalist_css_design_tokens_present(client: TestClient) -> None:
    """Verify that style.css defines Slate/Charcoal design tokens and removes body radial gradients."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.text
    assert "--bg-main: #0d1117" in css
    assert "--bg-surface: #161b22" in css
    assert "--border-subtle: #30363d" in css
    assert "--text-primary: #f0f6fc" in css
    assert "--text-muted: #8b949e" in css
    assert "radial-gradient" not in css.split("body")[1].split("}")[0]


def test_rating_chart_static_asset_served(client: TestClient) -> None:
    """Verify that rating_chart.js is served properly with the RatingChart namespace."""
    res = client.get("/static/js/rating_chart.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"] or "text/plain" in res.headers["content-type"]
    assert "RatingChart" in res.text
    assert "render" in res.text


def test_rating_chart_css_classes_present(client: TestClient) -> None:
    """Verify that style.css includes all required rating chart styling classes."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.text
    assert ".chart-card" in css
    assert ".chart-wrapper" in css
    assert ".chart-svg" in css
    assert ".chart-grid-line" in css
    assert ".chart-axis-text" in css
    assert ".chart-line" in css
    assert ".chart-point" in css
    assert ".chart-tooltip" in css
    assert ".chart-legend" in css
    assert ".legend-item" in css
    assert ".legend-color" in css
    assert ".chart-empty-state" in css


def test_leaderboard_template_contains_rating_chart_elements(client: TestClient) -> None:
    """Verify that index.html contains rating chart container and script integration."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="rating-chart-card"' in res.text
    assert 'id="rating-chart-container"' in res.text
    assert "/static/js/rating_chart.js" in res.text
    assert "/api/leaderboard/rating-history?top=5&limit=30" in res.text
    assert "RatingChart.render" in res.text


def test_profile_template_contains_rating_chart_elements(client: TestClient) -> None:
    """Verify that profile.html contains rating chart container and script for authenticated user."""
    db = SessionLocal()
    user = User(username="chart_user", elo=1450, wins=2, losses=1, draws=0)
    user.set_password("pass123")
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    session_token = "chart_token_abc"
    ACTIVE_SESSIONS[session_token] = user_id
    client.cookies.set("session_token", session_token)

    res = client.get("/profile")
    assert res.status_code == 200
    assert 'id="user-rating-chart-card"' in res.text
    assert 'id="user-rating-chart-container"' in res.text
    assert "/static/js/rating_chart.js" in res.text
    assert f"/api/users/{user_id}/rating-history?limit=50" in res.text
    assert "RatingChart.render" in res.text


def test_profile_template_anonymous_omits_rating_chart(client: TestClient) -> None:
    """Verify that profile.html does not render rating chart card when user is not logged in."""
    res = client.get("/profile")
    assert res.status_code == 200
    assert 'id="user-rating-chart-card"' not in res.text


