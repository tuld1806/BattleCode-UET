"""Unit tests for the automated BO3 playoff bracket runner service.

Tests cover:
- Running one pending round: score fields, winner_id, status update.
- Walkover when one player has no active bot (automatic 2-0 win).
- Winner promotion to the next bracket stage.
- run_all_bracket_rounds terminates when a champion is determined.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from typing import Any, Dict

import pytest
from sqlalchemy.orm import Session

from server.database import SessionLocal, init_db
from server.models import Bot, BracketMatch, Game as GameModel, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db() -> Session:
    """Provide a fresh database session, rolling back at teardown."""
    init_db()
    session = SessionLocal()
    session.query(BracketMatch).delete()
    session.commit()
    yield session
    session.query(BracketMatch).delete()
    session.commit()
    session.close()


def _make_user(db: Session, username: str, elo: int = 1200) -> User:
    """Create (or fetch) a non-admin test user."""
    u = db.query(User).filter(User.username == username).first()
    if not u:
        u = User(username=username, is_admin=False, elo=elo)
        u.set_password("pw")
        db.add(u)
        db.flush()
    return u


def _make_bot(db: Session, user: User, active: bool = True) -> Bot:
    """Create (or fetch) an active bot for the given user."""
    game = db.query(GameModel).first()
    assert game, "No game registered in DB; seed it first."
    b = db.query(Bot).filter(Bot.user_id == user.id, Bot.game_id == game.id).first()
    if not b:
        b = Bot(
            user_id=user.id,
            game_id=game.id,
            filename="bot_template.py",
            filepath="starter_kit/bot_template.py",
            is_active=active,
        )
        db.add(b)
        db.flush()
    else:
        b.is_active = active
    return b


def _make_bracket_match(
    db: Session, p1: User, p2: User, round_name: str = "Quarter-Final", index: int = 0
) -> BracketMatch:
    """Persist a pending bracket matchup."""
    m = BracketMatch(
        round_name=round_name,
        match_index=index,
        player1_id=p1.id,
        player2_id=p2.id,
        status="pending",
    )
    db.add(m)
    db.flush()
    return m


# ---------------------------------------------------------------------------
# Fake match result to avoid subprocess calls during unit tests
# ---------------------------------------------------------------------------


def _fake_run_match_win_p1(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Simulate run_match returning a decisive P1 win."""
    return {
        "winner": 1,
        "score_p1": 1,
        "score_p2": 0,
        "replay": [],
        "total_turns": 10,
    }


def _fake_run_match_win_p2(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Simulate run_match returning a decisive P2 win."""
    return {
        "winner": 2,
        "score_p1": 0,
        "score_p2": 1,
        "replay": [],
        "total_turns": 10,
    }


# ---------------------------------------------------------------------------
# Task B2 Tests
# ---------------------------------------------------------------------------


def test_run_bracket_round_updates_match_fields(db: Session) -> None:
    """Running a pending round updates score, winner_id, and status to completed."""
    from server import bracket_runner

    p1 = _make_user(db, "br_runner_p1")
    p2 = _make_user(db, "br_runner_p2")
    _make_bot(db, p1)
    _make_bot(db, p2)
    match = _make_bracket_match(db, p1, p2)
    db.commit()

    with patch("server.bracket_runner.run_match", side_effect=_fake_run_match_win_p1):
        result = bracket_runner.run_bracket_round(db)

    db.refresh(match)
    assert match.status == "completed"
    assert match.winner_id in (p1.id, p2.id)
    assert match.score_p1 is not None
    assert match.score_p2 is not None
    assert "matches_played" in result


def test_run_bracket_round_walkover_no_bot(db: Session) -> None:
    """If one player has no active bot, the opponent receives a 2-0 walkover win."""
    from server import bracket_runner

    p1 = _make_user(db, "br_walkover_p1")
    p2 = _make_user(db, "br_walkover_p2")
    _make_bot(db, p1, active=False)  # p1 has no active bot
    _make_bot(db, p2, active=True)
    match = _make_bracket_match(db, p1, p2, index=1)
    db.commit()

    # Should NOT call run_match at all (walkover)
    with patch("server.bracket_runner.run_match") as mock_rm:
        result = bracket_runner.run_bracket_round(db)
        mock_rm.assert_not_called()

    db.refresh(match)
    assert match.status == "completed"
    assert match.winner_id == p2.id
    assert match.score_p1 == 0
    assert match.score_p2 == 2


def test_run_bracket_round_walkover_both_no_bot(db: Session) -> None:
    """If neither player has an active bot, player1 wins by default walkover."""
    from server import bracket_runner

    p1 = _make_user(db, "br_both_no_bot_p1")
    p2 = _make_user(db, "br_both_no_bot_p2")
    # No bots at all
    match = _make_bracket_match(db, p1, p2, index=2)
    db.commit()

    with patch("server.bracket_runner.run_match") as mock_rm:
        bracket_runner.run_bracket_round(db)
        mock_rm.assert_not_called()

    db.refresh(match)
    assert match.status == "completed"
    assert match.winner_id in (p1.id, p2.id)


def test_run_all_bracket_rounds_terminates_with_champion(db: Session) -> None:
    """run_all_bracket_rounds completes all rounds and returns a champion."""
    from server import bracket_runner

    # Create a clean 2-player bracket (1 match = instant champion)
    p1 = _make_user(db, "br_all_champ_p1")
    p2 = _make_user(db, "br_all_champ_p2")
    _make_bot(db, p1)
    _make_bot(db, p2)
    match = _make_bracket_match(db, p1, p2, round_name="Final", index=0)
    db.commit()

    with patch("server.bracket_runner.run_match", side_effect=_fake_run_match_win_p1):
        result = bracket_runner.run_all_bracket_rounds(db)

    assert "champion_id" in result
    assert result["champion_id"] is not None


def test_run_bracket_round_advances_to_next_stage(db: Session) -> None:
    """When a round finishes, winners are paired into the next round."""
    from server import bracket_runner

    users = [_make_user(db, f"br_adv_u{i}") for i in range(4)]
    for u in users:
        _make_bot(db, u)

    # 4 players -> 2 Semi-Final matches
    m1 = _make_bracket_match(db, users[0], users[1], round_name="Semi-Final", index=0)
    m2 = _make_bracket_match(db, users[2], users[3], round_name="Semi-Final", index=1)
    db.commit()

    with patch("server.bracket_runner.run_match", side_effect=_fake_run_match_win_p1):
        result = bracket_runner.run_bracket_round(db)

    assert result["matches_played"] == 2

    # Check that a pending Final match was created
    finals = db.query(BracketMatch).filter(BracketMatch.round_name == "Final").all()
    assert len(finals) == 1
    assert finals[0].status == "pending"
    assert finals[0].player1_id == users[0].id
    assert finals[0].player2_id == users[2].id


def test_bo3_side_alternation(db: Session) -> None:
    """Verify Game 1 assigns P1 Red/P2 Blue and Game 2 alternates P2 Red/P1 Blue."""
    from server import bracket_runner

    p1 = _make_user(db, "br_alt_p1")
    p2 = _make_user(db, "br_alt_p2")
    b1 = _make_bot(db, p1)
    b2 = _make_bot(db, p2)
    match = _make_bracket_match(db, p1, p2, round_name="Final", index=0)
    db.commit()

    calls = []

    def mock_run_match(bot1_path, bot2_path, **kwargs):
        calls.append((bot1_path, bot2_path))
        # Return 1 so game 1 goes to caller's bot1 (p1), game 2 goes to caller's bot1 (p2), triggering game 3
        return {"winner": 1, "score_p1": 1, "score_p2": 0}

    with patch("server.bracket_runner.run_match", side_effect=mock_run_match):
        bracket_runner.run_bracket_round(db)

    # Game 1: P1 as bot1, P2 as bot2
    assert calls[0] == (b1.filepath, b2.filepath)
    # Game 2: P2 as bot1, P1 as bot2 (alternation!)
    assert calls[1] == (b2.filepath, b1.filepath)
    # Game 3: P1 as bot1, P2 as bot2
    assert calls[2] == (b1.filepath, b2.filepath)

