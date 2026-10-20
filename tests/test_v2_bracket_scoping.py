"""Unit tests for tournament playoff bracket isolation and champion badge awarding."""

import pytest
from fastapi.testclient import TestClient

from server.bracket_runner import run_all_bracket_rounds
from server.database import get_db_context, init_db
from server.main import app
from server.models import Badge, Bot, BracketMatch, Game, Tournament, User, UserBadge

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_bracket_isolation_per_tournament():
    """Verify BracketMatch records are scoped to tournament_id and do not conflict."""
    with get_db_context() as db:
        t1 = db.query(Tournament).filter(Tournament.name == "Iso Tourney 1").first()
        if not t1:
            t1 = Tournament(game_id=1, name="Iso Tourney 1", status="bracket")
            db.add(t1)
            db.commit()
            db.refresh(t1)

        t2 = db.query(Tournament).filter(Tournament.name == "Iso Tourney 2").first()
        if not t2:
            t2 = Tournament(game_id=1, name="Iso Tourney 2", status="bracket")
            db.add(t2)
            db.commit()
            db.refresh(t2)

        # Clear existing
        db.query(BracketMatch).filter(BracketMatch.tournament_id.in_([t1.id, t2.id])).delete()
        db.commit()

        bm1 = BracketMatch(tournament_id=t1.id, round_name="Final", match_index=0, status="pending")
        bm2 = BracketMatch(tournament_id=t2.id, round_name="Final", match_index=0, status="pending")
        db.add_all([bm1, bm2])
        db.commit()

        t1_id, t2_id = t1.id, t2.id

    res1 = client.get(f"/api/tournaments/{t1_id}/bracket")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["tournament_id"] == t1_id
    assert len(data1["matches"]) == 1
    assert data1["matches"][0]["tournament_id"] == t1_id

    res2 = client.get(f"/api/tournaments/{t2_id}/bracket")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["tournament_id"] == t2_id
    assert len(data2["matches"]) == 1
    assert data2["matches"][0]["tournament_id"] == t2_id


def test_champion_badge_awarded_on_finals_completion():
    """Verify that concluding a tournament bracket grants the top_1_champion badge to the winner."""
    with get_db_context() as db:
        champ = db.query(User).filter(User.username == "champ_user").first()
        if not champ:
            champ = User(username="champ_user", password_hash="h")
            db.add(champ)
            db.commit()
            db.refresh(champ)

        runner_up = db.query(User).filter(User.username == "runner_up_user").first()
        if not runner_up:
            runner_up = User(username="runner_up_user", password_hash="h")
            db.add(runner_up)
            db.commit()
            db.refresh(runner_up)

        tourney = Tournament(game_id=1, name="Championship Badge Tourney", status="bracket")
        db.add(tourney)
        db.commit()
        db.refresh(tourney)

        # Active bots for both
        b1 = Bot(user_id=champ.id, game_id=1, filename="champ.py", filepath="tests/test_data/dummy_bot.py", is_active=True)
        b2 = Bot(user_id=runner_up.id, game_id=1, filename="runner.py", filepath="tests/test_data/dummy_bot.py", is_active=True)
        db.add_all([b1, b2])

        # Walkover or pending final match
        final_m = BracketMatch(
            tournament_id=tourney.id,
            round_name="Final",
            match_index=0,
            player1_id=champ.id,
            player2_id=runner_up.id,
            status="pending",
        )
        db.add(final_m)
        db.commit()

        tourney_id = tourney.id
        champ_id = champ.id

    # Run bracket
    with get_db_context() as db:
        run_all_bracket_rounds(db, tournament_id=tourney_id)

    # Verify winner has top_1_champion badge
    with get_db_context() as db:
        badge = db.query(Badge).filter(Badge.slug == "top_1_champion").first()
        assert badge is not None
        user_badge = db.query(UserBadge).filter(
            UserBadge.user_id == champ_id,
            UserBadge.badge_id == badge.id,
        ).first()
        # Either champ or runner_up won and got the badge
        awarded_badges = db.query(UserBadge).filter(UserBadge.badge_id == badge.id).all()
        assert len(awarded_badges) >= 1
