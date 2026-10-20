"""Game-scoped uploads, match dispatch, persistence and registration integration."""

from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from server.database import Base, get_db, seed_default_game
from server.main import app
from server.models import Bot, Game, GameProfile, Match, User
from server.routes.auth import ACTIVE_SESSIONS
from scripts.register_rulebook_games import register_rulebook_games


@pytest.fixture
def context(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "isolated.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        seed_default_game(db_session=db)
        register_rulebook_games(db)
        register_rulebook_games(db)
        assert db.query(Game).count() == 3
        a, b = User(username="rulebook_a", elo=1500), User(username="rulebook_b", elo=1500)
        db.add_all([a, b])
        db.commit()
        ids = a.id, b.id
    def dependency():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = dependency
    ACTIVE_SESSIONS["rulebook-token"] = ids[0]
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    client.cookies.set("session_token", "rulebook-token")
    yield client, factory, ids
    app.dependency_overrides.pop(get_db, None)
    ACTIVE_SESSIONS.pop("rulebook-token", None)
    engine.dispose()


def test_json_upload_and_challenge_game_scope(context, monkeypatch):
    client, factory, (a, b) = context
    with factory() as db:
        game = db.query(Game).filter_by(slug="cyber-grid").one()
        gid = game.id
        db.add(Bot(user_id=b, game_id=1, filename="wrong.py", filepath="wrong.py", is_active=True))
        db.commit()
    monkeypatch.setattr("server.routes.matches._is_portal_open_now", lambda db: True)
    jobs = []
    monkeypatch.setattr("server.routes.matches.execute_match_job", lambda *args: jobs.append(args))
    upload = client.post("/api/bots/upload", data={"game_id": gid}, files={"file": ("bot.py", b"def get_action(state):\n    return {'commands': []}\n")})
    assert upload.status_code == 201, upload.text
    assert client.post("/api/matches/challenge", json={"opponent_id": b, "game_id": gid}).status_code == 400
    with factory() as db:
        db.add(Bot(user_id=b, game_id=gid, filename="correct.py", filepath="correct.py", is_active=True))
        db.commit()
    response = client.post("/api/matches/challenge", json={"opponent_id": b, "game_id": gid})
    assert response.status_code == 201, response.text
    with factory() as db:
        match = db.get(Match, response.json()["match_id"])
        assert match.game_id == gid and match.bot1_id == upload.json()["id"]
    assert len(jobs) == 1
    wrong = client.post("/api/bots/upload", data={"game_id": gid}, files={"file": ("bad.py", b"def get_move(board, team, history):\n    return None\n")})
    assert wrong.status_code == 400


def test_queue_dispatches_engine_and_persists_tick_replay(context, monkeypatch, tmp_path):
    from server.queue import execute_match_job
    from games.cyber_grid.engine import CyberGridEngine
    from server.game_registry import GameRegistry
    client, factory, (a, b) = context
    bot = tmp_path / "idle.py"
    bot.write_text("def get_action(state):\n    return {'commands': []}\n")
    with factory() as db:
        game = db.query(Game).filter_by(slug="cyber-grid").one()
        gid = game.id
        match = Match(player1_id=a, player2_id=b, game_id=gid)
        db.add(match)
        db.commit()
        mid = match.id
    monkeypatch.setattr(GameRegistry, "load_engine", lambda self, slug, db=None: CyberGridEngine(max_ticks=2))
    result = execute_match_job(mid, str(bot), str(bot), db_factory=factory)
    assert result and result["game_slug"] == "cyber-grid" and result["total_ticks"] == 2
    replay = client.get(f"/api/matches/{mid}/replay")
    assert replay.status_code == 200 and replay.json()["replay_version"] == 2
    with factory() as db:
        stored = db.get(Match, mid)
        assert stored.total_turns == 2 and stored.p1_elo_before == 1200
        assert db.query(GameProfile).filter_by(user_id=a, game_id=gid).one().draws == 1
        assert db.get(User, a).elo == 1500
