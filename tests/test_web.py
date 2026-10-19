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


def test_bracket_page_normal_user_sees_no_admin_button(client: TestClient) -> None:
    """Verify normal and anonymous users do not see admin button on /bracket."""
    # 1. Anonymous user
    res_anon = client.get("/bracket")
    assert res_anon.status_code == 200
    assert "⚙ Quản trị Admin" not in res_anon.text
    assert 'href="/admin"' not in res_anon.text

    # 2. Authenticated non-admin player
    db = SessionLocal()
    player = User(username="bracket_norm_player", is_admin=False, elo=1300)
    player.set_password("p123")
    db.add(player)
    db.commit()
    p_id = player.id
    db.close()

    token = "player_bracket_token"
    ACTIVE_SESSIONS[token] = p_id
    client.cookies.set("session_token", token)

    res_player = client.get("/bracket")
    assert res_player.status_code == 200
    assert "⚙ Quản trị Admin" not in res_player.text
    assert 'href="/admin"' not in res_player.text

    # 3. Authenticated admin user DOES see admin link
    db2 = SessionLocal()
    admin = User(username="bracket_adm_user", is_admin=True, elo=1500)
    admin.set_password("a123")
    db2.add(admin)
    db2.commit()
    a_id = admin.id
    db2.close()

    adm_token = "admin_bracket_token"
    ACTIVE_SESSIONS[adm_token] = a_id
    client.cookies.set("session_token", adm_token)

    res_admin = client.get("/bracket")
    assert res_admin.status_code == 200
    assert 'href="/admin"' in res_admin.text


def test_admin_ui_navbar_and_profile_separation(client: TestClient) -> None:
    """Verify navbar and profile page treat admin as administrator rather than player."""
    db = SessionLocal()
    admin = User(username="site_super_admin", is_admin=True, elo=1500)
    admin.set_password("adm123")
    db.add(admin)
    db.commit()
    admin_id = admin.id
    db.close()

    token = "site_admin_token"
    ACTIVE_SESSIONS[token] = admin_id
    client.cookies.set("session_token", token)

    # Navbar check
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert "🛡️ Admin" in res_home.text
    assert "⭐ 1500" not in res_home.text

    # Profile check
    res_prof = client.get("/profile")
    assert res_prof.status_code == 200
    assert "Tài khoản Quản trị viên" in res_prof.text
    assert "uploadBotForm" not in res_prof.text


def test_lobby_page_returns_200_and_renders_game_cards(client: TestClient) -> None:
    """Verify that /lobby renders game cards with title, description, and play button."""
    from server.models import Game
    db = SessionLocal()
    g1 = Game(
        slug="rps-chess",
        display_name="RPS Chess 9x9",
        description_md="Chiến thuật Oẳn tù tì trên bàn cờ 9x9",
        is_active=True,
    )
    g2 = Game(
        slug="tictactoe-ultimate",
        display_name="TicTacToe Ultimate",
        description_md="Cờ ca-rô mở rộng đấu trí đỉnh cao",
        is_active=True,
    )
    db.add_all([g1, g2])
    db.commit()
    db.close()

    res = client.get("/lobby")
    assert res.status_code == 200
    assert "game-card" in res.text
    assert "RPS Chess 9x9" in res.text
    assert "TicTacToe Ultimate" in res.text
    assert "/games/rps-chess" in res.text
    assert "/games/tictactoe-ultimate" in res.text


def test_game_detail_page_3_tabs(client: TestClient) -> None:
    """Verify that /games/{slug} returns 200 with Rules, Leaderboard, and Tournaments tabs."""
    from server.models import Game, GameProfile, Tournament
    db = SessionLocal()
    g = Game(
        slug="rps-chess",
        display_name="RPS Chess 9x9",
        description_md="Luật chơi RPS Chess 9x9: Oẳn tù tì trên bàn cờ 9x9.",
        is_active=True,
    )
    db.add(g)
    db.commit()

    u = User(username="chess_master", elo=1600, wins=10, losses=2)
    u.set_password("p123")
    db.add(u)
    db.flush()

    gp = GameProfile(user_id=u.id, game_id=g.id, elo=1650, wins=10, losses=2)
    db.add(gp)

    t = Tournament(game_id=g.id, name="Spring Open 2026", status="open", enrollment_open=True)
    db.add(t)
    db.commit()
    db.close()

    res = client.get("/games/rps-chess")
    assert res.status_code == 200
    assert "RPS Chess 9x9" in res.text
    assert 'id="tab-rules"' in res.text
    assert 'id="tab-leaderboard"' in res.text
    assert 'id="tab-tournaments"' in res.text
    assert "chess_master" in res.text
    assert "Spring Open 2026" in res.text

    # 404 for unknown game
    res_404 = client.get("/games/unknown-nonexistent-game")
    assert res_404.status_code == 404


def test_public_tournament_detail(client: TestClient) -> None:
    """Verify that /games/{slug}/tournaments/{id} returns 200 with enrolled list and bracket tree."""
    from server.models import BracketMatch, Game, Tournament, TournamentEnrollment
    db = SessionLocal()
    g = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    db.add(g)
    db.commit()

    t = Tournament(
        game_id=g.id,
        name="Vô địch Mùa Xuân 2026",
        status="bracket",
        ffa_start_time="19:00",
        ffa_end_time="21:00",
        ffa_day_count=7,
        bracket_top_n=4,
    )
    db.add(t)
    db.commit()

    u1 = User(username="player_alpha", elo=1500)
    u1.set_password("p1")
    u2 = User(username="player_beta", elo=1400)
    u2.set_password("p2")
    db.add_all([u1, u2])
    db.commit()

    e1 = TournamentEnrollment(tournament_id=t.id, user_id=u1.id)
    e2 = TournamentEnrollment(tournament_id=t.id, user_id=u2.id)
    bm = BracketMatch(
        round_name="Final",
        match_index=0,
        player1_id=u1.id,
        player2_id=u2.id,
        status="pending",
    )
    db.add_all([e1, e2, bm])
    db.commit()
    t_id = t.id
    db.close()

    res = client.get(f"/games/rps-chess/tournaments/{t_id}")
    assert res.status_code == 200
    assert "Vô địch Mùa Xuân 2026" in res.text
    assert "player_alpha" in res.text
    assert "player_beta" in res.text
    assert "bracket-container" in res.text or "bracket" in res.text.lower()

    # 404 for nonexistent tournament or mismatched game slug
    res_404 = client.get(f"/games/rps-chess/tournaments/99999")
    assert res_404.status_code == 404
    res_mismatch = client.get(f"/games/other-game/tournaments/{t_id}")
    assert res_mismatch.status_code == 404


def test_profile_game_cards_and_navbar_lobby(client: TestClient) -> None:
    """Verify that user profile displays individual GameProfile cards with game names and Elos."""
    from server.models import Game, GameProfile
    db = SessionLocal()
    u = User(username="multigame_player", elo=1200)
    u.set_password("p123")
    db.add(u)
    db.commit()

    g1 = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    g2 = Game(slug="tictactoe-ultimate", display_name="TicTacToe Ultimate", is_active=True)
    db.add_all([g1, g2])
    db.commit()

    gp1 = GameProfile(user_id=u.id, game_id=g1.id, elo=1620, wins=8, losses=2, draws=1)
    gp2 = GameProfile(user_id=u.id, game_id=g2.id, elo=1410, wins=3, losses=1, draws=0)
    db.add_all([gp1, gp2])
    db.commit()
    user_id = u.id
    db.close()

    token = "multigame_session_tok"
    ACTIVE_SESSIONS[token] = user_id
    client.cookies.set("session_token", token)

    res = client.get("/profile")
    assert res.status_code == 200
    assert "game-profile-card" in res.text
    assert "RPS Chess 9x9" in res.text
    assert "1620" in res.text
    assert "TicTacToe Ultimate" in res.text
    assert "1410" in res.text

    # Navbar check: lobby link is present
    assert 'href="/lobby"' in res.text


def test_admin_portal_routes_unauthenticated_redirect(client: TestClient) -> None:
    """Verify that all /admin/* routes redirect anonymous visitors to login."""
    admin_routes = [
        "/admin/dashboard",
        "/admin/games",
        "/admin/games/upload",
        "/admin/tournaments",
        "/admin/tournaments/1",
        "/admin/users",
    ]
    for route in admin_routes:
        res = client.get(route, follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"].startswith("/login?next=")


def test_admin_portal_routes_forbidden_for_regular_user(client: TestClient) -> None:
    """Verify that normal non-admin users get HTTP 403 Forbidden on all /admin/* routes."""
    db = SessionLocal()
    normal_user = User(username="normal_player", is_admin=False, elo=1200)
    normal_user.set_password("pass123")
    db.add(normal_user)
    db.commit()
    user_id = normal_user.id
    db.close()

    token = "session_normal_user_test"
    ACTIVE_SESSIONS[token] = user_id
    client.cookies.set("session_token", token)

    admin_routes = [
        "/admin/dashboard",
        "/admin/games",
        "/admin/games/upload",
        "/admin/tournaments",
        "/admin/tournaments/1",
        "/admin/users",
    ]
    for route in admin_routes:
        res = client.get(route)
        assert res.status_code == 403
        assert "Administrative privileges required" in res.text


def test_admin_portal_routes_success_for_admin_user(client: TestClient) -> None:
    """Verify that admin user can successfully access all /admin/* subpages."""
    from server.models import Game, Tournament
    db = SessionLocal()
    admin_user = User(username="site_admin", is_admin=True, elo=1500)
    admin_user.set_password("admin_pass_999")
    db.add(admin_user)
    db.commit()

    g = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    db.add(g)
    db.commit()

    t = Tournament(
        game_id=g.id,
        name="Giải Đấu Mùa Thu 2026",
        status="open",
        ffa_start_time="18:00",
        ffa_end_time="20:00",
        ffa_day_count=5,
        bracket_top_n=8,
    )
    db.add(t)
    db.commit()

    admin_id = admin_user.id
    t_id = t.id
    db.close()

    token = "admin_session_valid_portal"
    ACTIVE_SESSIONS[token] = admin_id
    client.cookies.set("session_token", token)

    # 1. /admin/dashboard
    res_dash = client.get("/admin/dashboard")
    assert res_dash.status_code == 200
    assert "Trung Tâm Quản Trị Hệ Thống" in res_dash.text or "Dashboard" in res_dash.text

    # 2. /admin/games
    res_games = client.get("/admin/games")
    assert res_games.status_code == 200
    assert "Danh Mục Bộ Môn Trò Chơi" in res_games.text or "RPS Chess 9x9" in res_games.text

    # 3. /admin/games/upload
    res_upload = client.get("/admin/games/upload")
    assert res_upload.status_code == 200
    assert "Tải Lên Plugin" in res_upload.text

    # 4. /admin/tournaments
    res_tourneys = client.get("/admin/tournaments")
    assert res_tourneys.status_code == 200
    assert "Quản Trị Danh Sách Giải Đấu" in res_tourneys.text or "Giải Đấu Mùa Thu 2026" in res_tourneys.text

    # 5. /admin/tournaments/{id}
    res_tourney_detail = client.get(f"/admin/tournaments/{t_id}")
    assert res_tourney_detail.status_code == 200
    assert "Giải Đấu Mùa Thu 2026" in res_tourney_detail.text
    assert "admin_bracket.js" in res_tourney_detail.text

    # 5b. Nonexistent tournament -> 404
    res_tourney_404 = client.get("/admin/tournaments/99999")
    assert res_tourney_404.status_code == 404

    # 6. /admin/users
    res_users = client.get("/admin/users")
    assert res_users.status_code == 200
    assert "Quản Lý Tài Khoản Người Dùng" in res_users.text
    assert "site_admin" in res_users.text


def test_user_game_profile_page_renders_stats_and_chart(client: TestClient) -> None:
    """Verify that /profile/{user_id}/games/{game_slug} returns 200 with Elo, chart, and matches."""
    from server.models import Game, GameProfile, Match
    db = SessionLocal()
    u1 = User(username="pro_gamer_1", elo=1200)
    u1.set_password("p1")
    u2 = User(username="rival_player", elo=1300)
    u2.set_password("p2")
    db.add_all([u1, u2])
    db.flush()

    game = Game(
        slug="rps-chess",
        display_name="RPS Chess 9x9",
        description_md="Luật chơi RPS Chess 9x9.",
        is_active=True,
    )
    db.add(game)
    db.flush()

    gp = GameProfile(user_id=u1.id, game_id=game.id, elo=1680, wins=12, losses=3, draws=1)
    db.add(gp)

    m = Match(
        game_id=game.id,
        player1_id=u1.id,
        player2_id=u2.id,
        winner_id=u1.id,
        win_reason="goal",
        total_turns=18,
        p1_elo_before=1650,
        p1_elo_after=1680,
        p2_elo_before=1330,
        p2_elo_after=1300,
        replay_path="/replays/match_123.json",
    )
    db.add(m)
    db.commit()

    u1_id = u1.id
    game_slug = game.slug
    db.close()

    res = client.get(f"/profile/{u1_id}/games/{game_slug}")
    assert res.status_code == 200
    assert "pro_gamer_1" in res.text
    assert "RPS Chess 9x9" in res.text
    assert "1680" in res.text
    assert "user-game-rating-chart" in res.text
    assert "rival_player" in res.text
    assert "goal" in res.text


def test_user_game_profile_page_returns_404_for_unknown(client: TestClient) -> None:
    """Verify that nonexistent user ID or game slug returns HTTP 404."""
    from server.models import Game
    db = SessionLocal()
    u = User(username="known_user", elo=1200)
    u.set_password("pass")
    g = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    db.add_all([u, g])
    db.commit()
    u_id = u.id
    db.close()

    # Unknown user
    res_unknown_user = client.get("/profile/99999/games/rps-chess")
    assert res_unknown_user.status_code == 404

    # Unknown game slug
    res_unknown_game = client.get(f"/profile/{u_id}/games/nonexistent-slug")
    assert res_unknown_game.status_code == 404


def test_user_profile_by_id_page_renders_profile(client: TestClient) -> None:
    """Verify that /profile/{user_id} renders user's profile with game cards."""
    from server.models import Game, GameProfile
    db = SessionLocal()
    u = User(username="spectated_player", elo=1200)
    u.set_password("pass")
    db.add(u)
    db.flush()

    g = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
    db.add(g)
    db.flush()

    gp = GameProfile(user_id=u.id, game_id=g.id, elo=1550, wins=5, losses=1, draws=0)
    db.add(gp)
    db.commit()

    u_id = u.id
    db.close()

    res = client.get(f"/profile/{u_id}")
    assert res.status_code == 200
    assert "spectated_player" in res.text
    assert "RPS Chess 9x9" in res.text
    assert "1550" in res.text


def test_bracket_replay_page_returns_200_for_string_identifier(client: TestClient) -> None:
    """Verify that /replay/{match_id} accepts string identifiers such as bracket_1_game_1."""
    res = client.get("/replay/bracket_1_game_1")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "bracket_1_game_1" in res.text
    assert "visualizer.js" in res.text
    assert 'const matchId = "bracket_1_game_1";' in res.text


def test_bracket_replay_api_endpoint_returns_json_for_bracket_match(client: TestClient) -> None:
    """Verify that /api/matches/{match_id}/replay reads directly from replays/ directory for bracket matches."""
    import json
    from pathlib import Path

    replays_dir = Path("replays")
    replays_dir.mkdir(parents=True, exist_ok=True)
    sample_file = replays_dir / "bracket_99_game_1.json"
    dummy_payload = {
        "winner": 1,
        "win_reason": "goal",
        "total_turns": 15,
        "player1": {"id": 10, "username": "alpha_contender"},
        "player2": {"id": 11, "username": "beta_contender"},
        "initial_board": [],
        "moves": [],
    }
    sample_file.write_text(json.dumps(dummy_payload), encoding="utf-8")

    try:
        res = client.get("/api/matches/bracket_99_game_1/replay")
        assert res.status_code == 200
        data = res.json()
        assert data["winner"] == 1
        assert data["player1"]["username"] == "alpha_contender"

        res_detail = client.get("/api/matches/bracket_99_game_1")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["id"] == "bracket_99_game_1"
        assert detail["player1"]["username"] == "alpha_contender"
    finally:
        if sample_file.exists():
            sample_file.unlink()










