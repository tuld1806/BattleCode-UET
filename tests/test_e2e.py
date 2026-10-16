"""End-to-End (E2E) integration tests for Battlecode 9x9 RPS Platform.

Verifies the complete tournament lifecycle and system entrypoint:
1. User registration and authentication (Alice & Bob).
2. Bot script uploads (starter_kit/bot_template.py & starter_kit/heuristic_bot.py).
3. Admin authentication, dynamic configuration (portal open, multiplier x = 2.0).
4. Direct challenge match execution, background worker handling, and replay logging.
5. Replay payload inspection (/api/matches/{id}/replay).
6. Leaderboard updates with Elo rating deltas and match statistics.
7. Single-elimination tournament bracket generation and status retrieval.
8. Root entrypoint (main.py) CLI arguments, database initialization, and admin seeding.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from main import main, parse_args, print_banner, seed_admin_and_starter_bots
from server.database import Base, SessionLocal, engine, init_db
from server.main import app
from server.models import Bot, BracketMatch, Match, TournamentSetting, User
from server.routes.auth import ACTIVE_SESSIONS


@pytest.fixture(autouse=True)
def setup_and_teardown_e2e_env():
    """Ensure a pristine database and clean filesystem for every test run."""
    ACTIVE_SESSIONS.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    ACTIVE_SESSIONS.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    # Clean up test artifacts
    if Path("bots").exists():
        for bot_file in Path("bots").glob("user_*"):
            try:
                bot_file.unlink()
            except OSError:
                pass
    if Path("replays").exists():
        for replay_file in Path("replays").glob("match_*.json"):
            try:
                replay_file.unlink()
            except OSError:
                pass


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_full_tournament_e2e_lifecycle(client: TestClient) -> None:
    """Test the complete user journey from registration to tournament bracket generation.

    Journey steps:
    1. Seed admin and verify credentials.
    2. Register 2 users (Alice & Bob) and obtain session tokens.
    3. Alice uploads starter_kit/bot_template.py; Bob uploads starter_kit/heuristic_bot.py.
    4. Admin logs in and opens the FFA challenge portal with daily_multiplier_x = 2.0.
    5. Alice challenges Bob; match executes in background queue.
    6. Replay JSON is verified via /api/matches/{match_id}/replay.
    7. Leaderboard reflects updated Elo ratings and match records.
    8. Admin triggers playoff bracket generation and verifies pairings.
    """
    # -------------------------------------------------------------
    # Step 1: Seed default admin and starter bots
    # -------------------------------------------------------------
    seed_admin_and_starter_bots()

    # -------------------------------------------------------------
    # Step 2: Register Alice and Bob
    # -------------------------------------------------------------
    res_reg_alice = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "AliceSecretPassword123!"},
    )
    assert res_reg_alice.status_code in (200, 201), res_reg_alice.text
    alice_data = res_reg_alice.json()
    alice_id = alice_data["id"]

    res_login_alice = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "AliceSecretPassword123!"},
    )
    assert res_login_alice.status_code == 200, res_login_alice.text
    alice_token = res_login_alice.json()["token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    res_reg_bob = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "BobSecretPassword123!"},
    )
    assert res_reg_bob.status_code in (200, 201), res_reg_bob.text
    bob_data = res_reg_bob.json()
    bob_id = bob_data["id"]

    res_login_bob = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "BobSecretPassword123!"},
    )
    assert res_login_bob.status_code == 200, res_login_bob.text
    bob_token = res_login_bob.json()["token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Verify /me endpoints for both players
    assert client.get("/api/auth/me", headers=alice_headers).json()["username"] == "alice"
    assert client.get("/api/auth/me", headers=bob_headers).json()["username"] == "bob"

    # -------------------------------------------------------------
    # Step 3: Alice & Bob upload starter kit bots
    # -------------------------------------------------------------
    bot_template_path = Path("starter_kit/bot_template.py")
    heuristic_bot_path = Path("starter_kit/heuristic_bot.py")
    assert bot_template_path.exists(), "starter_kit/bot_template.py must exist"
    assert heuristic_bot_path.exists(), "starter_kit/heuristic_bot.py must exist"

    alice_bot_code = bot_template_path.read_text(encoding="utf-8")
    bob_bot_code = heuristic_bot_path.read_text(encoding="utf-8")

    res_up_alice = client.post(
        "/api/bots/upload",
        files={"file": ("bot_template.py", alice_bot_code.encode("utf-8"), "text/x-python")},
        headers=alice_headers,
    )
    assert res_up_alice.status_code in (200, 201), res_up_alice.text
    alice_bot_info = res_up_alice.json()
    assert alice_bot_info["is_active"] is True
    assert alice_bot_info["filename"] == "bot_template.py"

    res_up_bob = client.post(
        "/api/bots/upload",
        files={"file": ("heuristic_bot.py", bob_bot_code.encode("utf-8"), "text/x-python")},
        headers=bob_headers,
    )
    assert res_up_bob.status_code in (200, 201), res_up_bob.text
    bob_bot_info = res_up_bob.json()
    assert bob_bot_info["is_active"] is True
    assert bob_bot_info["filename"] == "heuristic_bot.py"

    # Verify both players have active bots listed
    assert client.get("/api/bots/active", headers=alice_headers).status_code == 200
    assert client.get("/api/bots/active", headers=bob_headers).status_code == 200

    # -------------------------------------------------------------
    # Step 4: Admin logs in, opens portal with daily_multiplier_x = 2.0
    # -------------------------------------------------------------
    res_admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert res_admin_login.status_code == 200, res_admin_login.text
    admin_token = res_admin_login.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res_settings = client.post(
        "/api/admin/settings",
        json={"is_portal_open": True, "daily_multiplier_x": 2.0},
        headers=admin_headers,
    )
    assert res_settings.status_code == 200, res_settings.text
    settings = res_settings.json()
    assert settings["is_portal_open"] is True
    assert settings["daily_multiplier_x"] == 2.0

    # -------------------------------------------------------------
    # Step 5: Alice challenges Bob -> Match executes
    # -------------------------------------------------------------
    res_challenge = client.post(
        "/api/matches/challenge",
        json={"opponent_id": bob_id},
        headers=alice_headers,
    )
    assert res_challenge.status_code in (200, 201), res_challenge.text
    match_payload = res_challenge.json()
    match_id = match_payload["match_id"]
    assert match_id is not None

    # Retrieve completed match details
    res_match_info = client.get(f"/api/matches/{match_id}")
    assert res_match_info.status_code == 200, res_match_info.text
    match_data = res_match_info.json()

    assert match_data["id"] == match_id
    assert match_data["player1_id"] == alice_id
    assert match_data["player2_id"] == bob_id
    assert match_data["total_turns"] > 0
    assert match_data["win_reason"] is not None
    assert match_data["replay_path"] is not None
    assert Path(match_data["replay_path"]).exists()

    # -------------------------------------------------------------
    # Step 6: Verify replay payload from /api/matches/{match_id}/replay
    # -------------------------------------------------------------
    res_replay = client.get(f"/api/matches/{match_id}/replay")
    assert res_replay.status_code == 200, res_replay.text
    replay_json = res_replay.json()

    assert "initial_board" in replay_json
    assert len(replay_json["initial_board"]) == 9
    assert len(replay_json["initial_board"][0]) == 9
    assert "moves" in replay_json
    assert isinstance(replay_json["moves"], list)
    assert len(replay_json["moves"]) > 0
    assert "winner" in replay_json
    assert "win_reason" in replay_json
    assert "total_turns" in replay_json
    assert replay_json["total_turns"] == len(replay_json["moves"])
    assert "player1" in replay_json
    assert "player2" in replay_json
    assert replay_json["player1"]["id"] == alice_id
    assert replay_json["player2"]["id"] == bob_id

    # -------------------------------------------------------------
    # Step 7: Leaderboard shows updated Elo ratings and match records
    # -------------------------------------------------------------
    res_lb = client.get("/api/leaderboard")
    assert res_lb.status_code == 200, res_lb.text
    lb_list = res_lb.json()
    lb_by_id = {u["id"]: u for u in lb_list}

    assert alice_id in lb_by_id
    assert bob_id in lb_by_id

    alice_lb = lb_by_id[alice_id]
    bob_lb = lb_by_id[bob_id]

    # Total games for both players must equal 1
    total_games_alice = alice_lb["wins"] + alice_lb["losses"] + alice_lb["draws"]
    total_games_bob = bob_lb["wins"] + bob_lb["losses"] + bob_lb["draws"]
    assert total_games_alice == 1
    assert total_games_bob == 1

    winner_id = match_data["winner_id"]
    if winner_id == alice_id:
        assert alice_lb["wins"] == 1
        assert bob_lb["losses"] == 1
        assert alice_lb["elo"] > 1200
        assert bob_lb["elo"] < 1200
    elif winner_id == bob_id:
        assert bob_lb["wins"] == 1
        assert alice_lb["losses"] == 1
        assert bob_lb["elo"] > 1200
        assert alice_lb["elo"] < 1200
    else:
        assert alice_lb["draws"] == 1
        assert bob_lb["draws"] == 1
        assert alice_lb["elo"] == 1200
        assert bob_lb["elo"] == 1200

    # -------------------------------------------------------------
    # Step 8: Playoff bracket generation and retrieval
    # -------------------------------------------------------------
    res_bracket_gen = client.post(
        "/api/admin/bracket/generate",
        headers=admin_headers,
    )
    assert res_bracket_gen.status_code == 200, res_bracket_gen.text
    bracket_matchups = res_bracket_gen.json()
    assert len(bracket_matchups) >= 1

    # Verify bracket retrieval endpoint
    res_bracket_list = client.get("/api/admin/bracket", headers=admin_headers)
    assert res_bracket_list.status_code == 200, res_bracket_list.text
    saved_bracket = res_bracket_list.json()
    assert len(saved_bracket) == len(bracket_matchups)

    # All generated bracket matches start in 'pending' status
    for bm in saved_bracket:
        assert bm["status"] == "pending"
        assert bm["player1"] is not None
        assert bm["player2"] is not None


def test_main_cli_arg_parser() -> None:
    """Verify that CLI flags parse correctly with appropriate defaults."""
    # Default parameters
    args_default = parse_args([])
    assert args_default.host == "0.0.0.0"
    assert args_default.port == 8000
    assert args_default.reload is False
    assert args_default.seed_admin is True

    # Custom parameters
    custom_flags = [
        "--host",
        "127.0.0.1",
        "--port",
        "9000",
        "--reload",
        "--no-seed-admin",
    ]
    args_custom = parse_args(custom_flags)
    assert args_custom.host == "127.0.0.1"
    assert args_custom.port == 9000
    assert args_custom.reload is True
    assert args_custom.seed_admin is False

    # Explicit --seed-admin flag
    args_seeded = parse_args(["--seed-admin"])
    assert args_seeded.seed_admin is True


def test_main_banner_output() -> None:
    """Verify that print_banner outputs clean URLs for local web and docs."""
    buffer = io.StringIO()
    with patch("sys.stdout", buffer):
        print_banner("0.0.0.0", 8000)

    output = buffer.getvalue()
    assert "http://localhost:8000" in output
    assert "http://localhost:8000/docs" in output
    assert "8000" in output


def test_seed_admin_and_starter_bots_idempotency() -> None:
    """Verify that seed_admin_and_starter_bots safely creates admin and starter bots."""
    db = SessionLocal()
    try:
        # Run seeding twice to guarantee idempotency
        seed_admin_and_starter_bots(db)
        seed_admin_and_starter_bots(db)

        # Verify admin exists and has is_admin=True
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None
        assert admin.is_admin is True
        assert admin.verify_password("admin123") is True

        # Verify admin has starter bots
        admin_bots = db.query(Bot).filter(Bot.user_id == admin.id).all()
        bot_names = {b.filename for b in admin_bots}
        assert "bot_template.py" in bot_names or "heuristic_bot.py" in bot_names
        assert any(b.is_active for b in admin_bots)
    finally:
        db.close()


def test_main_execution_flow() -> None:
    """Verify that main() invokes init_db, seeding, banner, and uvicorn.run correctly."""
    with patch("main.init_db") as mock_init_db, \
         patch("main.seed_admin_and_starter_bots") as mock_seed, \
         patch("main.print_banner") as mock_banner, \
         patch("uvicorn.run") as mock_uvicorn:
        main(["--host", "127.0.0.1", "--port", "8888"])
        mock_init_db.assert_called_once()
        mock_seed.assert_called_once()
        mock_banner.assert_called_once_with("127.0.0.1", 8888)
        mock_uvicorn.assert_called_once_with(
            "server.main:app",
            host="127.0.0.1",
            port=8888,
            reload=False,
        )


def test_main_execution_flow_without_seed() -> None:
    """Verify that main() skips seeding when --no-seed-admin is supplied."""
    with patch("main.init_db") as mock_init_db, \
         patch("main.seed_admin_and_starter_bots") as mock_seed, \
         patch("main.print_banner") as mock_banner, \
         patch("uvicorn.run") as mock_uvicorn:
        main(["--no-seed-admin"])
        mock_init_db.assert_called_once()
        mock_seed.assert_not_called()
        mock_banner.assert_called_once_with("0.0.0.0", 8000)
        mock_uvicorn.assert_called_once_with(
            "server.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
        )

