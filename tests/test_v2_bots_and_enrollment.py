"""Unit and integration tests for multi-bot management, CLI API key upload, and tournament bot pinning."""

import hashlib
import pytest
from fastapi.testclient import TestClient

from server.database import get_db_context, init_db
from server.main import app
from server.models import ApiKey, Bot, Game, Tournament, TournamentEnrollment, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_bot_upload_with_cli_api_key_and_game_isolation():
    """Verify bot upload using X-API-Key and that active status is scoped per game."""
    raw_key = "bcuet_secrettoken12345"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    with get_db_context() as db:
        user = db.query(User).filter(User.username == "test_cli_user").first()
        if not user:
            user = User(username="test_cli_user", password_hash="dummy")
            db.add(user)
            db.commit()
            db.refresh(user)

        api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if not api_key:
            api_key = ApiKey(
                user_id=user.id,
                name="Test CLI Key",
                key_prefix="bcuet_secr",
                key_hash=key_hash,
            )
            db.add(api_key)
            db.commit()

    code1 = "def get_move(board, player, history):\n    return ((0,0),(0,1))\n"
    # Upload Bot 1 for game 1
    res1 = client.post(
        "/api/bots/upload",
        files={"file": ("bot1.py", code1.encode("utf-8"), "text/x-python")},
        data={"game_id": 1},
        headers={"X-API-Key": raw_key},
    )
    assert res1.status_code == 201
    bot1_id = res1.json()["id"]

    # Upload Bot 2 for game 1
    code2 = "def get_move(board, player, history):\n    return ((0,0),(1,1))\n"
    res2 = client.post(
        "/api/bots/upload",
        files={"file": ("bot2.py", code2.encode("utf-8"), "text/x-python")},
        data={"game_id": 1},
        headers={"X-API-Key": raw_key},
    )
    assert res2.status_code == 201
    bot2_id = res2.json()["id"]

    # In database, bot2 should be is_active=True and bot1 should be is_active=False
    with get_db_context() as db:
        b1 = db.query(Bot).filter(Bot.id == bot1_id).first()
        b2 = db.query(Bot).filter(Bot.id == bot2_id).first()
        assert b1.is_active is False
        assert b2.is_active is True

    # Re-activate bot 1 as Friendly Bot
    res_act = client.post(f"/api/bots/{bot1_id}/activate", headers={"X-API-Key": raw_key})
    assert res_act.status_code == 200
    with get_db_context() as db:
        assert db.query(Bot).filter(Bot.id == bot1_id).first().is_active is True
        assert db.query(Bot).filter(Bot.id == bot2_id).first().is_active is False


def test_tournament_enroll_with_specific_bot_selection():
    """Verify enrolling in a tournament pins the chosen bot_id independently of friendly is_active."""
    raw_key = "bcuet_tourney_pin_token"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    with get_db_context() as db:
        user = db.query(User).filter(User.username == "test_tourney_pinner").first()
        if not user:
            user = User(username="test_tourney_pinner", password_hash="dummy")
            db.add(user)
            db.commit()
            db.refresh(user)

        api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if not api_key:
            api_key = ApiKey(
                user_id=user.id,
                name="Tourney Pin Key",
                key_prefix="bcuet_tour",
                key_hash=key_hash,
            )
            db.add(api_key)
            db.commit()

        # Create two bots: Bot A (Friendly) and Bot B (Tournament)
        bot_a = Bot(user_id=user.id, game_id=1, filename="bot_a.py", filepath="tests/test_data/dummy_bot.py", is_active=True)
        bot_b = Bot(user_id=user.id, game_id=1, filename="bot_b.py", filepath="tests/test_data/dummy_bot.py", is_active=False)
        db.add_all([bot_a, bot_b])
        db.commit()
        db.refresh(bot_a)
        db.refresh(bot_b)
        bot_a_id, bot_b_id, user_id = bot_a.id, bot_b.id, user.id

        # Ensure a tournament exists for game 1
        tourney = db.query(Tournament).filter(Tournament.game_id == 1, Tournament.status == "open").first()
        if not tourney:
            tourney = Tournament(game_id=1, name="Open Championship", status="open", enrollment_open=True)
            db.add(tourney)
            db.commit()
            db.refresh(tourney)
        tourney_id = tourney.id

        # Clean existing enrollment if any
        db.query(TournamentEnrollment).filter(
            TournamentEnrollment.tournament_id == tourney_id,
            TournamentEnrollment.user_id == user.id,
        ).delete()
        db.commit()

    # Enroll in tournament explicitly selecting Bot B
    res = client.post(
        f"/api/games/rps-chess/tournaments/{tourney_id}/enroll",
        json={"bot_id": bot_b_id},
        headers={"X-API-Key": raw_key},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "enrolled"
    assert res.json()["bot_id"] == bot_b_id

    # Verify database: enrollment has bot_b, but bot_a is still friendly active
    with get_db_context() as db:
        enr = db.query(TournamentEnrollment).filter(
            TournamentEnrollment.tournament_id == tourney_id,
            TournamentEnrollment.user_id == user_id,
        ).first()
        assert enr is not None
        assert enr.bot_id == bot_b_id

        b_a = db.query(Bot).filter(Bot.id == bot_a_id).first()
        b_b = db.query(Bot).filter(Bot.id == bot_b_id).first()
        assert b_a.is_active is True
        assert b_b.is_active is False
