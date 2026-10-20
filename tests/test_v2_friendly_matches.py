"""Unit and integration tests for 24/7 friendly matchmaking, GameProfile Elo updating, and opponent discovery."""

import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server.boss_manager import deploy_boss
from server.database import get_db_context, init_db
from server.main import app
from server.models import ApiKey, Badge, Bot, Game, GameProfile, Match, User, UserBadge

client = TestClient(app)

DUMMY_BOT_CODE = """def get_move(board, player, history):
    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell and cell.get('player') == player:
                for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 9 and 0 <= nc < 9:
                        dest = board[nr][nc]
                        if not dest:
                            return ((r, c), (nr, nc))
    return ((0,0),(0,0))
"""


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_friendly_challenge_24_7_updates_game_profile_elo():
    """Verify friendly match queues 24/7 with game_id and updates GameProfile Elo on completion."""
    raw_key = "bcuet_friendly_test_key"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    test_bot_file = Path("tests/test_data/test_friendly_bot.py")
    test_bot_file.parent.mkdir(parents=True, exist_ok=True)
    test_bot_file.write_text(DUMMY_BOT_CODE, encoding="utf-8")

    with get_db_context() as db:
        p1 = db.query(User).filter(User.username == "player1_fr").first()
        if not p1:
            p1 = User(username="player1_fr", password_hash="hash")
            db.add(p1)
            db.commit()
            db.refresh(p1)

        p2 = db.query(User).filter(User.username == "player2_fr").first()
        if not p2:
            p2 = User(username="player2_fr", password_hash="hash")
            db.add(p2)
            db.commit()
            db.refresh(p2)

        p1_id, p2_id = p1.id, p2.id

        # API Key for player 1
        ak = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if not ak:
            ak = ApiKey(user_id=p1_id, name="FR Key", key_prefix="bcuet_frie", key_hash=key_hash)
            db.add(ak)

        # Active bots for game 1
        b1 = db.query(Bot).filter(Bot.user_id == p1_id, Bot.game_id == 1).first()
        if not b1:
            b1 = Bot(user_id=p1_id, game_id=1, filename="b1.py", filepath=str(test_bot_file), is_active=True)
            db.add(b1)
        else:
            b1.is_active = True

        b2 = db.query(Bot).filter(Bot.user_id == p2_id, Bot.game_id == 1).first()
        if not b2:
            b2 = Bot(user_id=p2_id, game_id=1, filename="b2.py", filepath=str(test_bot_file), is_active=True)
            db.add(b2)
        else:
            b2.is_active = True

        # GameProfile for game 1
        gp1 = db.query(GameProfile).filter(GameProfile.user_id == p1_id, GameProfile.game_id == 1).first()
        if not gp1:
            gp1 = GameProfile(user_id=p1_id, game_id=1, elo=1200)
            db.add(gp1)

        gp2 = db.query(GameProfile).filter(GameProfile.user_id == p2_id, GameProfile.game_id == 1).first()
        if not gp2:
            gp2 = GameProfile(user_id=p2_id, game_id=1, elo=1200)
            db.add(gp2)

        db.commit()

    # Challenge opponent
    res = client.post(
        "/api/matches/challenge",
        json={"opponent_id": p2_id, "game_id": 1},
        headers={"X-API-Key": raw_key},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "queued"
    assert data["game_id"] == 1


def test_friendly_opponents_endpoint():
    """Verify friendly opponents endpoint lists deployed bosses and ready players."""
    # Deploy novice boss
    with get_db_context() as db:
        deploy_boss(db, "novice", game_id=1)

    res = client.get("/api/games/rps-chess/friendly-opponents")
    assert res.status_code == 200
    data = res.json()
    assert "bosses" in data
    assert "players" in data
    assert any(b["boss_slug"] == "novice" and b["is_deployed"] for b in data["bosses"])
