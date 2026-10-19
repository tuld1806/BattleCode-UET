"""Tests for automatic discovery and seeding of games from the filesystem."""
from typing import Set
import pytest
from server.database import init_db, SessionLocal, auto_discover_and_seed_games
from server.models import Game, Tournament


def test_auto_discover_and_seed_games_registers_sample_game():
    """Verify that auto_discover_and_seed_games registers both rps-chess and sample-game."""
    init_db()
    db = SessionLocal()
    try:
        discovered = auto_discover_and_seed_games(db)
        slugs: Set[str] = {g.slug for g in discovered}
        assert "rps-chess" in slugs
        assert "sample-game" in slugs

        # Verify sample-game record fields
        sample = db.query(Game).filter(Game.slug == "sample-game").first()
        assert sample is not None
        assert sample.is_active is True
        assert sample.display_name == "Sample Game Plugin"

        # Verify a default tournament was seeded for sample-game
        t = db.query(Tournament).filter(Tournament.game_id == sample.id).first()
        assert t is not None
        assert t.name == "Sample Game Plugin Championship"
    finally:
        db.close()


def test_auto_discover_and_seed_games_handles_malformed_plugins_gracefully(tmp_path, monkeypatch):
    """Ensure auto-discovery gracefully ignores malformed plugin dirs without raising exceptions."""
    from pathlib import Path
    import server.database as sdb

    # Create temporary games folder with various broken plugins
    fake_games = tmp_path / "games"
    fake_games.mkdir()

    # 1. Missing engine.py
    d1 = fake_games / "missing_engine"
    d1.mkdir()
    (d1 / "config.yaml").write_text("slug: missing-engine\n")

    # 2. Missing config.yaml
    d2 = fake_games / "missing_config"
    d2.mkdir()
    (d2 / "engine.py").write_text("# dummy\n")

    # 3. Invalid YAML
    d3 = fake_games / "bad_yaml"
    d3.mkdir()
    (d3 / "engine.py").write_text("# dummy\n")
    (d3 / "config.yaml").write_text(": : bad yaml [[\n")

    # 4. Valid plugin
    d4 = fake_games / "valid_plugin"
    d4.mkdir()
    (d4 / "engine.py").write_text("# dummy\n")
    (d4 / "config.yaml").write_text("slug: valid-plugin\ndisplay_name: Valid Plugin\n")

    # Monkeypatch repo_root lookup
    fake_root = tmp_path
    monkeypatch.setattr(Path, "resolve", lambda self: fake_root / "server" / "database.py")

    db = sdb.SessionLocal()
    try:
        discovered = sdb.auto_discover_and_seed_games(db)
        slugs = {g.slug for g in discovered}
        assert "valid-plugin" in slugs
        assert "missing-engine" not in slugs
        assert "missing-config" not in slugs
        assert "bad-yaml" not in slugs
    finally:
        db.close()

