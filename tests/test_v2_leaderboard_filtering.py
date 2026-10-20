"""Unit tests for strict game leaderboard filtering based on submitted bots."""

import pytest
from fastapi.testclient import TestClient

from server.database import get_db_context, init_db
from server.main import app
from server.models import Bot, Game, GameProfile, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_leaderboard_strictly_excludes_users_without_bots():
    """Verify that only players with at least 1 bot for that game appear on its leaderboard."""
    with get_db_context() as db:
        user_with_bot = db.query(User).filter(User.username == "user_has_bot").first()
        if not user_with_bot:
            user_with_bot = User(username="user_has_bot", password_hash="h", is_admin=False)
            db.add(user_with_bot)
            db.commit()
            db.refresh(user_with_bot)

        user_no_bot = db.query(User).filter(User.username == "user_no_bot").first()
        if not user_no_bot:
            user_no_bot = User(username="user_no_bot", password_hash="h", is_admin=False)
            db.add(user_no_bot)
            db.commit()
            db.refresh(user_no_bot)

        # Ensure user_with_bot has an active bot for game 1
        b = db.query(Bot).filter(Bot.user_id == user_with_bot.id, Bot.game_id == 1).first()
        if not b:
            b = Bot(user_id=user_with_bot.id, game_id=1, filename="bot.py", filepath="tests/test_data/dummy_bot.py", is_active=True)
            db.add(b)

        # Ensure user_no_bot has ZERO bots for game 1
        db.query(Bot).filter(Bot.user_id == user_no_bot.id).delete()

        # Both have GameProfiles
        gp1 = db.query(GameProfile).filter(GameProfile.user_id == user_with_bot.id, GameProfile.game_id == 1).first()
        if not gp1:
            gp1 = GameProfile(user_id=user_with_bot.id, game_id=1, elo=1350)
            db.add(gp1)

        gp2 = db.query(GameProfile).filter(GameProfile.user_id == user_no_bot.id, GameProfile.game_id == 1).first()
        if not gp2:
            gp2 = GameProfile(user_id=user_no_bot.id, game_id=1, elo=1200)
            db.add(gp2)

        db.commit()

    res = client.get("/api/games/rps-chess/leaderboard")
    assert res.status_code == 200
    entries = res.json()
    usernames = [entry["username"] for entry in entries]

    assert "user_has_bot" in usernames
    assert "user_no_bot" not in usernames
