"""Tests for Excel UTF-8-SIG CSV score export service."""

from __future__ import annotations

import csv
import io
import pytest
from sqlalchemy.orm import Session

from server.database import SessionLocal, init_db
from server.models import BracketMatch, Game, GameProfile, Tournament, TournamentEnrollment, User


@pytest.fixture
def db() -> Session:
    """Provide clean database session for export testing."""
    init_db()
    session = SessionLocal()
    session.query(BracketMatch).delete()
    session.commit()
    yield session
    session.query(BracketMatch).delete()
    session.commit()
    session.close()


def _make_user(db: Session, username: str, elo: int = 1200) -> User:
    u = db.query(User).filter(User.username == username).first()
    if not u:
        u = User(username=username, is_admin=False, elo=elo)
        u.set_password("pw")
        db.add(u)
        db.flush()
    return u


def test_export_bracket_scores_csv_format_and_bom(db: Session) -> None:
    """Exported CSV must begin with UTF-8 BOM (\ufeff) and contain proper headers and rows."""
    from server.bracket_export import generate_bracket_scores_csv

    p1 = _make_user(db, "export_player1", elo=1500)
    p2 = _make_user(db, "export_player2", elo=1400)
    p3 = _make_user(db, "export_player3", elo=1300)
    p4 = _make_user(db, "export_player4", elo=1200)

    # Semi-Finals: p1 beats p2, p3 beats p4
    m1 = BracketMatch(
        round_name="Semi-Final",
        match_index=0,
        player1_id=p1.id,
        player2_id=p2.id,
        winner_id=p1.id,
        score_p1=2,
        score_p2=0,
        status="completed",
    )
    m2 = BracketMatch(
        round_name="Semi-Final",
        match_index=1,
        player1_id=p3.id,
        player2_id=p4.id,
        winner_id=p3.id,
        score_p1=2,
        score_p2=1,
        status="completed",
    )
    # Final: p1 beats p3
    m3 = BracketMatch(
        round_name="Final",
        match_index=0,
        player1_id=p1.id,
        player2_id=p3.id,
        winner_id=p1.id,
        score_p1=2,
        score_p2=0,
        status="completed",
    )
    db.add_all([m1, m2, m3])
    db.commit()

    csv_data = generate_bracket_scores_csv(db)

    # 1. Must start with UTF-8 BOM
    assert csv_data.startswith("\ufeff")

    # 2. Parse CSV
    reader = list(csv.reader(io.StringIO(csv_data.lstrip("\ufeff"))))
    assert len(reader) >= 5  # 1 header + 4 players

    header = reader[0]
    assert "Thứ hạng" in header[0]
    assert "Tên kỳ thủ" in header[1]
    assert "Điểm Elo" in header[2] or "Elo" in header[2]
    assert "Điểm Bracket" in header[5] or "Bracket" in header[5]
    assert "Tổng điểm" in header[6]

    # Row 1 must be champion (p1)
    row1 = reader[1]
    assert row1[1] == "export_player1"
    # Bracket points for champion is 100
    assert "100" in row1[5]


def test_export_bracket_scores_csv_with_tournament_id(db: Session) -> None:
    """Exporting scores scoped to a specific tournament reads per-game Elo and enrollments."""
    from server.bracket_export import generate_bracket_scores_csv

    game = db.query(Game).first()
    assert game, "Game must exist in DB."

    tourney = Tournament(
        game_id=game.id,
        name="Export Test Tournament",
        status="finished",
        bracket_top_n=2,
    )
    db.add(tourney)
    db.flush()

    p1 = _make_user(db, "tourney_export_p1", elo=1200)
    p2 = _make_user(db, "tourney_export_p2", elo=1200)

    # Per-game profile Elo
    gp1 = GameProfile(user_id=p1.id, game_id=game.id, elo=1650)
    gp2 = GameProfile(user_id=p2.id, game_id=game.id, elo=1350)
    db.add_all([gp1, gp2])

    e1 = TournamentEnrollment(tournament_id=tourney.id, user_id=p1.id)
    e2 = TournamentEnrollment(tournament_id=tourney.id, user_id=p2.id)
    db.add_all([e1, e2])

    m = BracketMatch(
        round_name="Final",
        match_index=0,
        player1_id=p1.id,
        player2_id=p2.id,
        winner_id=p1.id,
        score_p1=2,
        score_p2=0,
        status="completed",
    )
    db.add(m)
    db.commit()

    csv_data = generate_bracket_scores_csv(db, tournament_id=tourney.id)
    assert csv_data.startswith("\ufeff")
    reader = list(csv.reader(io.StringIO(csv_data.lstrip("\ufeff"))))
    assert len(reader) == 3  # header + 2 players
    assert reader[1][1] == "tourney_export_p1"
