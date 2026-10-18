"""Unit tests for server.game_registry GameRegistry singleton and engine cache."""

import io
from pathlib import Path
import tempfile
import zipfile
import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from engine.base import GameEngine
from server.database import Base
from server.game_registry import GameRegistry
from server.models import Game


@pytest.fixture
def test_db():
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def test_registry_singleton_identity():
    """GameRegistry.get_instance() must return the identical singleton instance."""
    reg1 = GameRegistry.get_instance()
    reg2 = GameRegistry.get_instance()
    assert reg1 is reg2


def test_registry_load_engine_rps_chess():
    """Loading 'rps-chess' should instantiate GameEngine and cache it."""
    registry = GameRegistry.get_instance()
    registry.invalidate_cache()

    engine1 = registry.load_engine("rps-chess")
    assert isinstance(engine1, GameEngine)

    # Calling again should retrieve from cache
    engine2 = registry.load_engine("rps-chess")
    assert engine1 is engine2


def test_registry_cache_invalidation():
    """Invalidating cache should force reloading new engine instance."""
    registry = GameRegistry.get_instance()
    engine1 = registry.load_engine("rps-chess")

    registry.invalidate_cache("rps-chess")
    assert "rps-chess" not in registry._engine_cache

    engine2 = registry.load_engine("rps-chess")
    assert isinstance(engine2, GameEngine)


def test_registry_load_engine_nonexistent_slug_raises():
    """Loading unknown slug should raise ValueError or FileNotFoundError."""
    registry = GameRegistry.get_instance()
    with pytest.raises((ValueError, FileNotFoundError)):
        registry.load_engine("nonexistent-game-slug-999")


def test_registry_list_active_games_and_toggle(test_db):
    """list_active_games, deactivate_game, and activate_game should manipulate DB state."""
    registry = GameRegistry.get_instance()

    game1 = Game(slug="game-alpha", display_name="Game Alpha", is_active=True)
    game2 = Game(slug="game-beta", display_name="Game Beta", is_active=False)
    test_db.add_all([game1, game2])
    test_db.commit()

    active_games = registry.list_active_games(test_db)
    active_slugs = [g.slug for g in active_games]
    assert "game-alpha" in active_slugs
    assert "game-beta" not in active_slugs

    registry.deactivate_game("game-alpha", test_db)
    assert not game1.is_active

    registry.activate_game("game-alpha", test_db)
    assert game1.is_active


def test_registry_register_from_zip(test_db, tmp_path):
    """register_from_zip must unpack and create a new Game record in database."""
    registry = GameRegistry.get_instance()

    # Create dummy plugin zip
    zip_path = tmp_path / "custom_test_game.zip"
    engine_py_content = """from engine.base import GameEngine

class CustomTestEngine(GameEngine):
    def get_initial_state(self, p1, p2): return {'p1': p1, 'p2': p2}
    def get_player_view(self, state, p): return state
    def apply_action(self, state, p, a): return state
    def check_winner(self, state): return (None, 'ongoing')
    def is_action_valid(self, state, p, a): return True
    def get_max_turns(self): return 100
    def score_for_tiebreak(self, state, p): return 0.0
"""
    config_yaml_content = yaml.dump({
        "slug": "custom-test-game",
        "display_name": "Custom Test Game",
        "description_md": "Rules for custom game",
        "max_turns": 100,
    })

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("engine.py", engine_py_content)
        zf.writestr("config.yaml", config_yaml_content)

    game_record = registry.register_from_zip(zip_path, test_db, target_dir=tmp_path / "games")
    assert game_record.slug == "custom-test-game"
    assert game_record.display_name == "Custom Test Game"
    assert game_record.is_active is True

    # Check database persistence
    persisted = test_db.query(Game).filter(Game.slug == "custom-test-game").first()
    assert persisted is not None
    assert persisted.slug == "custom-test-game"
