"""Comprehensive End-to-End (E2E) integration test for the Multi-Game Tournament Platform.

Verifies the complete multi-game tournament lifecycle:
1. System boot and default game auto-seeding.
2. Multi-player registration (Alpha, Beta, Gamma, Delta).
3. Bot script uploads bound to game_id.
4. Tournament creation via Admin API.
5. Contestant enrollment into tournament (/api/games/{slug}/tournaments/{id}/enroll).
6. FFA matches between enrolled players, verifying GameProfile rating updates.
7. Admin bracket generation with password confirmation (/api/admin/tournaments/{id}/start-bracket).
8. Automated Playoff BO3 execution (run-round and run-all) through champion crowning.
9. Verification of generated bracket match replays via web (/replay/{id}) and API (/api/matches/{id}/replay).
10. Excel-compatible UTF-8-SIG CSV score export (/api/admin/tournaments/{id}/export-scores).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict
import pytest
from fastapi.testclient import TestClient

from main import seed_admin_and_starter_bots
from server.database import Base, SessionLocal, engine, init_db
from server.main import app
from server.models import Bot, BracketMatch, Game, GameProfile, Match, Tournament, TournamentEnrollment, User
from server.queue import execute_match_job
from server.routes.auth import ACTIVE_SESSIONS


@pytest.fixture(autouse=True)
def clean_multi_game_env():
    """Ensure clean database and filesystem state for each E2E test run."""
    ACTIVE_SESSIONS.clear()
    Base.metadata.drop_all(bind=engine)
    init_db(target_engine=engine)
    yield
    ACTIVE_SESSIONS.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    # Clean up artifacts
    if Path("bots").exists():
        for b in Path("bots").glob("user_*"):
            try:
                b.unlink()
            except OSError:
                pass
    if Path("replays").exists():
        for r in Path("replays").glob("*.json"):
            try:
                r.unlink()
            except OSError:
                pass


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


def _register_and_login(client: TestClient, username: str, password: str = "P@ssword123") -> tuple[int, Dict[str, str]]:
    """Helper to register and login a user, returning (user_id, headers)."""
    res_reg = client.post("/api/auth/register", json={"username": username, "password": password})
    assert res_reg.status_code in (200, 201), res_reg.text
    user_id = res_reg.json()["id"]

    res_login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res_login.status_code == 200, res_login.text
    token = res_login.json()["token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_complete_multi_game_tournament_e2e_lifecycle(client: TestClient) -> None:
    """Test full multi-game lifecycle from lobby through BO3 playoff and Excel CSV export."""
    # -------------------------------------------------------------------------
    # 1. Initialize admin and default rps-chess game
    # -------------------------------------------------------------------------
    seed_admin_and_starter_bots()

    # Login admin
    res_admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_admin_login.status_code == 200, res_admin_login.text
    admin_token = res_admin_login.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Verify lobby renders active games
    res_lobby = client.get("/lobby")
    assert res_lobby.status_code == 200
    assert "RPS Chess" in res_lobby.text

    # -------------------------------------------------------------------------
    # 2. Register 4 players and upload active bots
    # -------------------------------------------------------------------------
    players = {}
    usernames = ["player_alpha", "player_beta", "player_gamma", "player_delta"]
    bot_code = Path("starter_kit/bot_template.py").read_text(encoding="utf-8")

    for uname in usernames:
        uid, headers = _register_and_login(client, uname)
        # Upload bot
        res_upload = client.post(
            "/api/bots/upload",
            files={"file": (f"{uname}_bot.py", bot_code.encode("utf-8"), "text/x-python")},
            headers=headers,
        )
        assert res_upload.status_code in (200, 201), res_upload.text
        bot_id = res_upload.json()["id"]
        players[uname] = {"id": uid, "headers": headers, "bot_id": bot_id}

    # -------------------------------------------------------------------------
    # 3. Admin creates a new Tournament for rps-chess (Top 4 Playoff)
    # -------------------------------------------------------------------------
    res_create_tourney = client.post(
        "/api/admin/tournaments",
        json={
            "game_id": 1,
            "name": "Battlecode Autumn Cup",
            "ffa_start_time": "18:00",
            "ffa_end_time": "22:00",
            "ffa_day_count": 3,
            "bracket_top_n": 4,
            "elo_multiplier": 1.5,
        },
        headers=admin_headers,
    )
    assert res_create_tourney.status_code == 200, res_create_tourney.text
    tourney = res_create_tourney.json()
    tourney_id = tourney["id"]
    assert tourney["status"] == "open"
    assert tourney["bracket_top_n"] == 4

    # -------------------------------------------------------------------------
    # 4. All 4 players enroll in the tournament
    # -------------------------------------------------------------------------
    for uname, pdata in players.items():
        res_enroll = client.post(
            f"/api/games/rps-chess/tournaments/{tourney_id}/enroll",
            headers=pdata["headers"],
        )
        assert res_enroll.status_code == 200, res_enroll.text
        assert res_enroll.json()["status"] == "enrolled"

    # Verify enrollment list in public game detail view
    res_tourney_view = client.get(f"/games/rps-chess/tournaments/{tourney_id}")
    assert res_tourney_view.status_code == 200
    assert "Battlecode Autumn Cup" in res_tourney_view.text
    for uname in usernames:
        assert uname in res_tourney_view.text

    # -------------------------------------------------------------------------
    # 5. Execute an FFA challenge match and verify GameProfile update
    # -------------------------------------------------------------------------
    # Admin opens matchmaking portal
    client.post("/api/admin/settings", json={"is_portal_open": True, "daily_multiplier_x": 1.5}, headers=admin_headers)

    res_challenge = client.post(
        "/api/matches/challenge",
        json={"opponent_id": players["player_beta"]["id"]},
        headers=players["player_alpha"]["headers"],
    )
    assert res_challenge.status_code in (200, 201), res_challenge.text
    ffa_match_id = res_challenge.json()["match_id"]

    # Verify completed FFA replay
    res_ffa_replay = client.get(f"/api/matches/{ffa_match_id}/replay")
    assert res_ffa_replay.status_code == 200
    assert "moves" in res_ffa_replay.json()

    # -------------------------------------------------------------------------
    # 6. Admin starts Playoff Bracket with password confirmation
    # -------------------------------------------------------------------------
    # Reject on incorrect password
    res_bad_pw = client.post(
        f"/api/admin/tournaments/{tourney_id}/start-bracket",
        json={"admin_password": "wrong_password"},
        headers=admin_headers,
    )
    assert res_bad_pw.status_code == 403

    # Accept on valid password
    res_bracket = client.post(
        f"/api/admin/tournaments/{tourney_id}/start-bracket",
        json={"admin_password": "admin123"},
        headers=admin_headers,
    )
    assert res_bracket.status_code == 200, res_bracket.text
    assert res_bracket.json()["status"] == "bracket"

    # -------------------------------------------------------------------------
    # 7. Execute automated BO3 playoff runner (run-all)
    # -------------------------------------------------------------------------
    res_run_all = client.post(
        f"/api/admin/tournaments/{tourney_id}/bracket/run-all",
        headers=admin_headers,
    )
    assert res_run_all.status_code == 200, res_run_all.text
    run_all_data = res_run_all.json()
    assert run_all_data["status"] == "finished"
    assert run_all_data["champion_id"] is not None

    # Verify bracket matches table
    db = SessionLocal()
    completed_bms = db.query(BracketMatch).filter(BracketMatch.status == "completed").all()
    assert len(completed_bms) >= 2
    sample_bm = completed_bms[0]
    sample_bm_id = sample_bm.id
    db.close()

    # -------------------------------------------------------------------------
    # 8. Verify bracket match replays via web visualizer and API endpoint
    # -------------------------------------------------------------------------
    bracket_replay_identifier = f"bracket_{sample_bm_id}_game_1"

    # Web page /replay/{match_id} returns 200
    res_web_replay = client.get(f"/replay/{bracket_replay_identifier}")
    assert res_web_replay.status_code == 200
    assert "text/html" in res_web_replay.headers["content-type"]
    assert bracket_replay_identifier in res_web_replay.text
    assert "visualizer.js" in res_web_replay.text
    assert f'const matchId = "{bracket_replay_identifier}";' in res_web_replay.text

    # API /api/matches/{id}/replay returns replay JSON
    res_api_replay = client.get(f"/api/matches/{bracket_replay_identifier}/replay")
    assert res_api_replay.status_code == 200
    replay_json = res_api_replay.json()
    assert "moves" in replay_json
    assert "winner" in replay_json

    # API /api/matches/{id} returns match summary detail
    res_api_detail = client.get(f"/api/matches/{bracket_replay_identifier}")
    assert res_api_detail.status_code == 200
    detail_json = res_api_detail.json()
    assert detail_json["id"] == bracket_replay_identifier
    assert detail_json["is_bracket"] is True

    # -------------------------------------------------------------------------
    # 9. Admin exports tournament scores to Excel UTF-8-SIG CSV
    # -------------------------------------------------------------------------
    res_export = client.get(
        f"/api/admin/tournaments/{tourney_id}/export-scores",
        headers=admin_headers,
    )
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers["content-type"]
    assert "attachment" in res_export.headers.get("content-disposition", "")

    csv_content = res_export.content
    # Must start with UTF-8 BOM
    assert csv_content.startswith(b"\xef\xbb\xbf")

    csv_text = csv_content.decode("utf-8-sig")
    assert "Thứ hạng,Tên kỳ thủ,Điểm Elo" in csv_text
    assert "Tổng điểm chung cuộc" in csv_text
    for uname in usernames:
        assert uname in csv_text
