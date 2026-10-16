"""Unit and integration tests for background match queue execution (server/queue.py).

Tests error resilience, missing entity fallbacks, player stat updates,
Elo rating mutations, bracket match exceptions, and tournament settings overrides.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from server.database import SessionLocal, init_db
from server.models import Bot, Match, TournamentSetting, User
from server.queue import _get_setting_value, execute_match_job


@pytest.fixture(autouse=True)
def setup_clean_db():
    """Ensure database schema is initialized before every queue test."""
    init_db()


import uuid

def _create_test_pair(prefix: str = "q"):
    """Helper creating two test users and dummy bot records."""
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:8]
        u1 = User(username=f"{prefix}_alice_{tag}", elo=1200, wins=0, losses=0, draws=0)
        u1.set_password("pass123")
        u2 = User(username=f"{prefix}_bob_{tag}", elo=1200, wins=0, losses=0, draws=0)
        u2.set_password("pass123")
        db.add_all([u1, u2])
        db.commit()

        b1_path = str(Path("starter_kit/bot_template.py").resolve())
        b2_path = str(Path("starter_kit/heuristic_bot.py").resolve())

        bot1 = Bot(user_id=u1.id, filename="b1.py", filepath=b1_path, is_active=True)
        bot2 = Bot(user_id=u2.id, filename="b2.py", filepath=b2_path, is_active=True)
        db.add_all([bot1, bot2])
        db.commit()

        return u1.id, u2.id, bot1.id, bot2.id, b1_path, b2_path
    finally:
        db.close()


def test_execute_match_job_nonexistent_match():
    """Verify execute_match_job returns None cleanly when match_id does not exist."""
    res = execute_match_job(
        match_id=9999999,
        bot1_path="dummy1.py",
        bot2_path="dummy2.py",
        db_factory=SessionLocal,
    )
    assert res is None


def test_execute_match_job_missing_player():
    """Verify execute_match_job returns None when a participant user record is missing."""
    u1_id, u2_id, b1_id, b2_id, b1_path, b2_path = _create_test_pair("miss")

    db = SessionLocal()
    try:
        match = Match(
            player1_id=u1_id,
            player2_id=u2_id,
            bot1_id=b1_id,
            bot2_id=b2_id,
            p1_elo_before=1200,
            p2_elo_before=1200,
        )
        db.add(match)
        db.commit()
        match_id = match.id
    finally:
        db.close()

    # Simulate player lookup returning None
    with patch("sqlalchemy.orm.Query.first", side_effect=[
        Match(id=match_id, player1_id=u1_id, player2_id=u2_id),  # match lookup
        None,  # player1 lookup fails
    ]):
        res = execute_match_job(
            match_id=match_id,
            bot1_path=b1_path,
            bot2_path=b2_path,
            db_factory=SessionLocal,
        )
    assert res is None


def test_execute_match_job_player2_wins():
    """Verify match outcome and stats when player 2 is victorious."""
    u1_id, u2_id, b1_id, b2_id, b1_path, b2_path = _create_test_pair("p2win")

    db = SessionLocal()
    try:
        match = Match(
            player1_id=u1_id,
            player2_id=u2_id,
            bot1_id=b1_id,
            bot2_id=b2_id,
            p1_elo_before=1200,
            p2_elo_before=1200,
            is_bracket=False,
        )
        db.add(match)
        db.commit()
        match_id = match.id
    finally:
        db.close()

    fake_result = {
        "winner": 2,
        "win_reason": "wipeout",
        "total_turns": 42,
        "moves": [],
        "board_history": [],
    }

    with patch("server.queue.run_match", return_value=fake_result), \
         patch("server.queue.save_replay", return_value=None):
        outcome = execute_match_job(
            match_id=match_id,
            bot1_path=b1_path,
            bot2_path=b2_path,
            db_factory=SessionLocal,
        )

    assert outcome == fake_result

    db_check = SessionLocal()
    try:
        m = db_check.query(Match).filter(Match.id == match_id).first()
        assert m.winner_id == u2_id
        assert m.win_reason == "wipeout"
        assert m.total_turns == 42
        assert m.p2_elo_after > 1200
        assert m.p1_elo_after < 1200

        p1 = db_check.query(User).filter(User.id == u1_id).first()
        p2 = db_check.query(User).filter(User.id == u2_id).first()
        assert p1.losses == 1
        assert p1.wins == 0
        assert p2.wins == 1
        assert p2.losses == 0
    finally:
        db_check.close()


def test_execute_match_job_draw_outcome():
    """Verify match outcome and stats when the match concludes in a draw."""
    u1_id, u2_id, b1_id, b2_id, b1_path, b2_path = _create_test_pair("draw")

    db = SessionLocal()
    try:
        match = Match(
            player1_id=u1_id,
            player2_id=u2_id,
            bot1_id=b1_id,
            bot2_id=b2_id,
            p1_elo_before=1200,
            p2_elo_before=1200,
            is_bracket=False,
        )
        db.add(match)
        db.commit()
        match_id = match.id
    finally:
        db.close()

    fake_result = {
        "winner": None,
        "win_reason": "max_turns",
        "total_turns": 200,
        "moves": [],
        "board_history": [],
    }

    with patch("server.queue.run_match", return_value=fake_result), \
         patch("server.queue.save_replay", return_value=None):
        outcome = execute_match_job(
            match_id=match_id,
            bot1_path=b1_path,
            bot2_path=b2_path,
            db_factory=SessionLocal,
        )

    assert outcome == fake_result

    db_check = SessionLocal()
    try:
        m = db_check.query(Match).filter(Match.id == match_id).first()
        assert m.winner_id is None
        assert m.win_reason == "max_turns"

        p1 = db_check.query(User).filter(User.id == u1_id).first()
        p2 = db_check.query(User).filter(User.id == u2_id).first()
        assert p1.draws == 1
        assert p2.draws == 1
    finally:
        db_check.close()


def test_execute_match_job_is_bracket_freezes_elo():
    """Verify bracket tournament matches do NOT alter user Elo ratings."""
    u1_id, u2_id, b1_id, b2_id, b1_path, b2_path = _create_test_pair("bracket")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == u1_id).first()
        u2 = db.query(User).filter(User.id == u2_id).first()
        u1.elo = 1450
        u2.elo = 1300
        db.commit()

        match = Match(
            player1_id=u1_id,
            player2_id=u2_id,
            bot1_id=b1_id,
            bot2_id=b2_id,
            p1_elo_before=1450,
            p2_elo_before=1300,
            is_bracket=True,
        )
        db.add(match)
        db.commit()
        match_id = match.id
    finally:
        db.close()

    fake_result = {
        "winner": 1,
        "win_reason": "goal",
        "total_turns": 18,
        "moves": [],
        "board_history": [],
    }

    with patch("server.queue.run_match", return_value=fake_result), \
         patch("server.queue.save_replay", return_value=None):
        outcome = execute_match_job(
            match_id=match_id,
            bot1_path=b1_path,
            bot2_path=b2_path,
            db_factory=SessionLocal,
        )

    assert outcome == fake_result

    db_check = SessionLocal()
    try:
        m = db_check.query(Match).filter(Match.id == match_id).first()
        assert m.winner_id == u1_id
        # Elo ratings must remain unchanged for bracket matches
        assert m.p1_elo_after == 1450
        assert m.p2_elo_after == 1300

        p1 = db_check.query(User).filter(User.id == u1_id).first()
        p2 = db_check.query(User).filter(User.id == u2_id).first()
        assert p1.elo == 1450  # Bracket match leaves user elo unchanged
        assert p2.elo == 1300
        assert p1.wins == 1
        assert p2.losses == 1
    finally:
        db_check.close()


def test_execute_match_job_runner_exception_handling():
    """Verify execution exception in runner writes failure message to match and returns None."""
    u1_id, u2_id, b1_id, b2_id, b1_path, b2_path = _create_test_pair("err")

    db = SessionLocal()
    try:
        match = Match(
            player1_id=u1_id,
            player2_id=u2_id,
            bot1_id=b1_id,
            bot2_id=b2_id,
            p1_elo_before=1200,
            p2_elo_before=1200,
        )
        db.add(match)
        db.commit()
        match_id = match.id
    finally:
        db.close()

    with patch("server.queue.run_match", side_effect=RuntimeError("Subprocess timeout crashed")):
        res = execute_match_job(
            match_id=match_id,
            bot1_path=b1_path,
            bot2_path=b2_path,
            db_factory=SessionLocal,
        )

    assert res is None

    db_check = SessionLocal()
    try:
        m = db_check.query(Match).filter(Match.id == match_id).first()
        assert m.win_reason is not None
        assert "Execution error:" in m.win_reason
        assert "Subprocess timeout crashed" in m.win_reason
    finally:
        db_check.close()


def test_get_setting_value_helper():
    """Verify _get_setting_value queries existing values, typecasts, and falls back gracefully."""
    db = SessionLocal()
    try:
        # 1. Non-existent key returns default
        val = _get_setting_value(db, "non_existent_key_xyz", 99.9, float)
        assert val == 99.9

        # 2. Existing key returns parsed value
        test_key = f"mult_{uuid.uuid4().hex[:8]}"
        setting = db.query(TournamentSetting).filter(TournamentSetting.key == test_key).first()
        if setting:
            setting.value = "2.75"
        else:
            db.add(TournamentSetting(key=test_key, value="2.75"))
        db.commit()

        val2 = _get_setting_value(db, test_key, 1.0, float)
        assert val2 == 2.75
        assert isinstance(val2, float)

        # 3. Exception in query or caster returns default
        val3 = _get_setting_value(db, test_key, 10, lambda _: int("not_an_int"))
        assert val3 == 10
    finally:
        db.close()


def test_execute_match_job_honors_database_setting_overrides():
    """Verify execute_match_job reads and passes database setting overrides to run_match."""
    u1_id, u2_id, b1_id, b2_id, b1_path, b2_path = _create_test_pair("override")

    db = SessionLocal()
    try:
        # Override tournament parameters in DB
        for k, v in [
            ("daily_multiplier_x", "2.5"),
            ("k_factor", "48"),
            ("max_turns", "150"),
            ("turn_timeout_seconds", "0.75"),
        ]:
            s = db.query(TournamentSetting).filter(TournamentSetting.key == k).first()
            if s:
                s.value = v
            else:
                db.add(TournamentSetting(key=k, value=v))
        db.commit()

        match = Match(
            player1_id=u1_id,
            player2_id=u2_id,
            bot1_id=b1_id,
            bot2_id=b2_id,
            p1_elo_before=1200,
            p2_elo_before=1200,
            is_bracket=False,
        )
        db.add(match)
        db.commit()
        match_id = match.id
    finally:
        db.close()

    fake_result = {
        "winner": 1,
        "win_reason": "goal",
        "total_turns": 25,
        "moves": [],
        "board_history": [],
    }

    with patch("server.queue.run_match", return_value=fake_result) as mock_run, \
         patch("server.queue.save_replay", return_value=None):
        outcome = execute_match_job(
            match_id=match_id,
            bot1_path=b1_path,
            bot2_path=b2_path,
            db_factory=SessionLocal,
        )

    assert outcome == fake_result
    # Assert run_match received the database overridden max_turns and timeout
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["max_turns"] == 150
    assert kwargs["timeout_per_turn"] == 0.75

