"""Tests for idempotent multi-game database migration script."""

from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from server.database import Base
from server.models import Bot, Game, GameProfile, Match, Tournament, TournamentSetting, User


def test_migration_is_idempotent(tmp_path: Path):
    """Verify running migration once and twice leaves database in consistent state."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"
    test_engine = create_engine(db_url)

    # Setup legacy database state with User, Bot, Match, TournamentSetting
    Base.metadata.create_all(bind=test_engine)
    Session = sessionmaker(bind=test_engine)
    db = Session()
    try:
        u_admin = User(username="admin", is_admin=True)
        u1 = User(username="player1", elo=1350, wins=5, losses=2, draws=1)
        u2 = User(username="player2", elo=1100, wins=1, losses=4, draws=0)
        db.add_all([u_admin, u1, u2])
        db.commit()

        b1 = Bot(user_id=u1.id, filename="b1.py", filepath="b1_path")
        db.add(b1)
        db.commit()

        m1 = Match(player1_id=u1.id, player2_id=u2.id)
        db.add(m1)
        db.commit()

        ts = TournamentSetting(key="ffa_start_time", value="20:00")
        db.add(ts)
        db.commit()

        u_admin_id = u_admin.id
        u1_id = u1.id
        u2_id = u2.id
        b1_id = b1.id
        m1_id = m1.id
    finally:
        db.close()

    from scripts.migrate_multi_game import migrate_multi_game

    # Run 1: initial migration
    assert migrate_multi_game(db_url) is True

    # Verify migration results
    db = Session()
    try:
        # Check game seeded
        game = db.query(Game).filter(Game.slug == "rps-chess").first()
        assert game is not None
        assert game.id == 1
        assert game.display_name == "RPS Chess 9x9"

        # Check bot & match updated
        b = db.query(Bot).filter(Bot.id == b1_id).first()
        assert b.game_id == 1

        m = db.query(Match).filter(Match.id == m1_id).first()
        assert m.game_id == 1

        # Check game_profiles populated
        gp1 = db.query(GameProfile).filter(GameProfile.user_id == u1_id, GameProfile.game_id == 1).first()
        assert gp1 is not None
        assert gp1.elo == 1350
        assert gp1.wins == 5
        assert gp1.losses == 2
        assert gp1.draws == 1

        # Admin must not have game_profile
        gp_admin = db.query(GameProfile).filter(GameProfile.user_id == u_admin_id).first()
        assert gp_admin is None


        # Check tournament created
        tourn = db.query(Tournament).filter(Tournament.game_id == 1).first()
        assert tourn is not None
        assert tourn.game_id == 1
    finally:
        db.close()

    # Run 2: idempotent execution must succeed without duplicate key errors
    assert migrate_multi_game(db_url) is True

    db = Session()
    try:
        games_count = db.query(Game).count()
        assert games_count == 1
        profiles_count = db.query(GameProfile).count()
        assert profiles_count == 2  # u1 and u2
    finally:
        db.close()
        test_engine.dispose()
