"""Tests for database models, SQLite engine, and tournament configuration."""

import os
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.database import Base, SessionLocal, engine, get_db, init_db
from server.models import Bot, BracketMatch, Match, TournamentSetting, User
from server.tournament_config import DEFAULT_TOURNAMENT_CONFIG, load_tournament_config


@pytest.fixture(autouse=True)
def cleanup_default_db():
    """Ensure a clean database state before and after each test."""
    yield
    # Clean up any session connection to avoid locks on Windows
    engine.dispose()
    for db_artifact in ["app.db", "app.db-shm", "app.db-wal"]:
        if os.path.exists(db_artifact):
            try:
                os.remove(db_artifact)
            except OSError:
                pass


def test_load_tournament_config_default():
    """Verify loading tournament config from the default YAML file."""
    cfg = load_tournament_config("config/tournament.yaml")
    assert cfg["tournament"]["title"] == "Giải Đấu Cờ Oẳn Tù Tì 9x9"
    assert cfg["tournament"]["total_days"] == 7
    assert cfg["tournament"]["current_day"] >= 1
    assert cfg["tournament"]["elo"]["initial_rating"] == 1200
    assert cfg["tournament"]["elo"]["k_factor"] == 32
    assert cfg["tournament"]["elo"]["daily_multiplier_x"] >= 1.0
    assert cfg["tournament"]["match_rules"]["max_turns"] == 200
    assert cfg["tournament"]["final_bracket"]["top_players_count"] == 8


def test_load_tournament_config_missing_file_fallback():
    """Verify fallback defaults when config file does not exist."""
    cfg = load_tournament_config("config/non_existent_path.yaml")
    assert cfg == DEFAULT_TOURNAMENT_CONFIG
    assert cfg["tournament"]["total_days"] == 7
    assert cfg["tournament"]["elo"]["initial_rating"] == 1200


def test_load_tournament_config_custom_file(tmp_path):
    """Verify loading custom tournament config with partial overrides."""
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text(
        """
tournament:
  title: "Custom Championship"
  total_days: 5
  elo:
    initial_rating: 1500
"""
    )
    cfg = load_tournament_config(str(custom_yaml))
    assert cfg["tournament"]["title"] == "Custom Championship"
    assert cfg["tournament"]["total_days"] == 5
    assert cfg["tournament"]["elo"]["initial_rating"] == 1500
    # Unspecified fields should keep default values
    assert cfg["tournament"]["elo"]["k_factor"] == 32
    assert cfg["tournament"]["match_rules"]["max_turns"] == 200


def test_load_tournament_config_invalid_content(tmp_path):
    """Verify fallback defaults when config file contains invalid YAML/non-dict content."""
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("- not a dict\n- just a list")
    cfg = load_tournament_config(str(invalid_yaml))
    assert cfg == DEFAULT_TOURNAMENT_CONFIG


def test_database_crud(tmp_path):
    """Verify basic CRUD on User using the default engine and get_db."""
    init_db()
    db = next(get_db())
    try:
        user = User(username="alice", password_hash="hash123", elo=1200)
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.elo == 1200
        assert user.wins == 0
        assert user.losses == 0
        assert user.draws == 0
        assert user.is_admin is False
        assert isinstance(user.created_at, datetime)
    finally:
        db.close()


def test_user_password_hashing():
    """Verify password hashing and verification helper methods."""
    user = User(username="bob")
    user.set_password("SuperSecret123")

    assert user.password_hash is not None
    assert user.password_hash != "SuperSecret123"
    assert user.verify_password("SuperSecret123") is True
    assert user.verify_password("WrongPassword") is False

    # Direct hash verification fallback
    user.password_hash = "direct_hash"
    assert user.verify_password("direct_hash") is True
    assert user.verify_password("another") is False


def test_bot_model_and_relationship(tmp_path):
    """Verify Bot model creation and relationship with User."""
    db_file = tmp_path / "test_bot.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    db = TestingSession()

    try:
        user = User(username="coder_one")
        user.set_password("pass123")
        db.add(user)
        db.commit()
        db.refresh(user)

        bot = Bot(
            user_id=user.id,
            filename="smart_bot.py",
            filepath="/uploads/bots/smart_bot.py",
            is_active=True,
        )
        db.add(bot)
        db.commit()
        db.refresh(bot)

        assert bot.id is not None
        assert bot.user_id == user.id
        assert bot.is_active is True
        assert isinstance(bot.uploaded_at, datetime)
        assert len(user.bots) == 1
        assert user.bots[0].filename == "smart_bot.py"
        assert bot.user.username == "coder_one"
    finally:
        db.close()
        test_engine.dispose()


def test_match_model_and_relationships(tmp_path):
    """Verify Match model logging and relationship references."""
    db_file = tmp_path / "test_match.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    db = TestingSession()

    try:
        p1 = User(username="player_one", elo=1200)
        p1.set_password("pass1")
        p2 = User(username="player_two", elo=1200)
        p2.set_password("pass2")
        db.add_all([p1, p2])
        db.commit()

        b1 = Bot(user_id=p1.id, filename="p1_bot.py", filepath="path1")
        b2 = Bot(user_id=p2.id, filename="p2_bot.py", filepath="path2")
        db.add_all([b1, b2])
        db.commit()

        match = Match(
            player1_id=p1.id,
            player2_id=p2.id,
            bot1_id=b1.id,
            bot2_id=b2.id,
            winner_id=p1.id,
            win_reason="elimination",
            total_turns=82,
            p1_elo_before=1200,
            p1_elo_after=1216,
            p2_elo_before=1200,
            p2_elo_after=1184,
            replay_path="replays/match_1.json",
            is_bracket=False,
        )
        db.add(match)
        db.commit()
        db.refresh(match)

        assert match.id is not None
        assert match.winner_id == p1.id
        assert match.win_reason == "elimination"
        assert match.total_turns == 82
        assert match.player1.username == "player_one"
        assert match.player2.username == "player_two"
        assert match.winner.username == "player_one"
        assert match.bot1.filename == "p1_bot.py"
        assert match.bot2.filename == "p2_bot.py"
        assert match.is_bracket is False
    finally:
        db.close()
        test_engine.dispose()


def test_tournament_setting_model(tmp_path):
    """Verify TournamentSetting key-value persistence."""
    db_file = tmp_path / "test_settings.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    db = TestingSession()

    try:
        setting = TournamentSetting(key="is_portal_open", value="true")
        db.add(setting)
        db.commit()
        db.refresh(setting)

        assert setting.id is not None
        assert setting.key == "is_portal_open"
        assert setting.value == "true"
        assert isinstance(setting.updated_at, datetime)

        # Update setting
        setting.value = "false"
        db.commit()
        db.refresh(setting)
        assert setting.value == "false"
    finally:
        db.close()
        test_engine.dispose()


def test_bracket_match_model(tmp_path):
    """Verify BracketMatch model fields, defaults, and relationships."""
    db_file = tmp_path / "test_bracket.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    db = TestingSession()

    try:
        p1 = User(username="bracket_p1", elo=1400)
        p1.set_password("p1")
        p2 = User(username="bracket_p2", elo=1350)
        p2.set_password("p2")
        db.add_all([p1, p2])
        db.commit()

        bmatch = BracketMatch(
            round_name="Quarter-Final",
            match_index=1,
            player1_id=p1.id,
            player2_id=p2.id,
            winner_id=p1.id,
            score_p1=2,
            score_p2=1,
            status="completed",
        )
        db.add(bmatch)
        db.commit()
        db.refresh(bmatch)

        assert bmatch.id is not None
        assert bmatch.round_name == "Quarter-Final"
        assert bmatch.match_index == 1
        assert bmatch.score_p1 == 2
        assert bmatch.score_p2 == 1
        assert bmatch.status == "completed"
        assert bmatch.player1.username == "bracket_p1"
        assert bmatch.player2.username == "bracket_p2"
        assert bmatch.winner.username == "bracket_p1"
    finally:
        db.close()
        test_engine.dispose()


def test_sqlite_pragmas_wal(tmp_path):
    """Verify that SQLite connection activates WAL mode and foreign keys."""
    with engine.connect() as conn:
        journal_mode = conn.exec_driver_sql("PRAGMA journal_mode;").scalar()
        # In SQLite, WAL mode for disk files returns 'wal' (or 'memory' for in-memory)
        assert str(journal_mode).lower() in ("wal", "memory")
        foreign_keys = conn.exec_driver_sql("PRAGMA foreign_keys;").scalar()
        assert foreign_keys == 1
