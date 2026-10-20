"""Unit tests for V2 database models, schema auto-migration, and seed badges."""

import pytest
from server.database import get_db_context, init_db, seed_default_badges
from server.models import ApiKey, Badge, BracketMatch, Tournament, User, UserBadge


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database schema is initialized and up to date."""
    init_db()



def test_bracket_match_has_tournament_id_column():
    """Verify BracketMatch records persist and associate with tournament_id."""
    with get_db_context() as db:
        tourney = db.query(Tournament).filter(Tournament.id == 1).first()
        if not tourney:
            tourney = Tournament(game_id=1, name="Test Tourney", status="open")
            db.add(tourney)
            db.commit()
            db.refresh(tourney)

        match = BracketMatch(
            round_name="Quarterfinals",
            match_index=1,
            tournament_id=tourney.id,
        )
        db.add(match)
        db.commit()
        db.refresh(match)

        assert match.id is not None
        assert match.tournament_id == tourney.id
        assert match.round_name == "Quarterfinals"


def test_api_key_model_and_hashing():
    """Verify ApiKey creation and properties."""
    with get_db_context() as db:
        user = db.query(User).filter(User.username == "test_user_v2_models").first()
        if not user:
            user = User(username="test_user_v2_models", password_hash="dummy_hash")
            db.add(user)
            db.commit()
            db.refresh(user)

        key = ApiKey(
            user_id=user.id,
            name="Test CLI Key",
            key_prefix="bcuet_1234",
            key_hash="testhash1234567890abcdef",
        )
        db.add(key)
        db.commit()
        db.refresh(key)

        assert key.id is not None
        assert key.user_id == user.id
        assert key.name == "Test CLI Key"
        assert key.key_prefix == "bcuet_1234"
        assert key.created_at is not None


def test_seed_default_badges():
    """Verify default badges are seeded idempotently."""
    with get_db_context() as db:
        seed_default_badges(db)
        badges = db.query(Badge).all()
        slugs = {b.slug for b in badges}
        assert "top_1_champion" in slugs
        assert "boss_slayer" in slugs
        assert "active_player" in slugs

        # Running seed again must not duplicate or raise IntegrityError
        seed_default_badges(db)
        badges_after = db.query(Badge).all()
        assert len(badges_after) == len(badges)
