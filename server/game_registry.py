"""Central Game Plugin Registry and Engine Cache Service.

Provides a thread-safe singleton GameRegistry to load, dynamically instantiate,
and cache GameEngine implementations via Python's importlib machinery, as well
as register and manage game plugins in the database.
"""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Dict, List, Optional
import yaml
from sqlalchemy.orm import Session

from engine.base import GameEngine
from engine.plugin_loader import load_plugin_engine, unpack_plugin, validate_plugin_zip
from server.models import Game


class GameRegistry:
    """Singleton service for loading, caching, and managing game plugins."""

    _instance: Optional[GameRegistry] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._engine_cache: Dict[str, GameEngine] = {}

    @classmethod
    def get_instance(cls) -> GameRegistry:
        """Retrieve the singleton instance of GameRegistry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load_engine(self, slug: str, db: Optional[Session] = None) -> GameEngine:
        """Dynamically load and cache the GameEngine for a given slug.

        Args:
            slug: URL-safe game slug identifier (e.g. 'rps-chess').
            db: Optional active database session to lookup registered plugin paths.

        Returns:
            Cached or newly loaded GameEngine instance.

        Raises:
            ValueError: If game plugin cannot be located or loaded.
        """
        with self._lock:
            if slug in self._engine_cache:
                return self._engine_cache[slug]

        # Locate plugin directory
        plugin_dir: Optional[Path] = None

        # 1. Check database if db session provided
        if db is not None:
            game = db.query(Game).filter(Game.slug == slug).first()
            if game and game.plugin_path:
                candidate = Path(game.plugin_path).resolve()
                if candidate.is_dir() and (candidate / "engine.py").is_file():
                    plugin_dir = candidate

        # 2. Check conventional directory path: games/<slug> or games/<slug_with_underscores>
        if plugin_dir is None:
            candidates = [
                Path("games") / slug,
                Path("games") / slug.replace("-", "_"),
            ]
            for candidate in candidates:
                if candidate.is_dir() and (candidate / "engine.py").is_file():
                    plugin_dir = candidate.resolve()
                    break

        # 3. Fallback: scan games/* directory for matching config.yaml slug
        if plugin_dir is None and Path("games").is_dir():
            for sub in Path("games").iterdir():
                if sub.is_dir() and (sub / "config.yaml").is_file() and (sub / "engine.py").is_file():
                    try:
                        with open(sub / "config.yaml", "r", encoding="utf-8") as f:
                            cfg = yaml.safe_load(f)
                        if isinstance(cfg, dict) and cfg.get("slug") == slug:
                            plugin_dir = sub.resolve()
                            break
                    except Exception:
                        continue

        if plugin_dir is None:
            raise ValueError(f"Game plugin directory for slug '{slug}' not found.")

        # Load engine instance dynamically
        engine_instance = load_plugin_engine(plugin_dir)

        with self._lock:
            self._engine_cache[slug] = engine_instance

        return engine_instance

    def register_from_zip(
        self,
        zip_path: str | Path,
        db: Session,
        target_dir: Optional[str | Path] = None,
    ) -> Game:
        """Scan, unpack, and register a new game plugin archive in database.

        Args:
            zip_path: File system path to the uploaded plugin zip.
            db: Active database session.
            target_dir: Target parent directory where plugin will be unpacked (defaults to 'games').

        Returns:
            Created or updated Game model entity.
        """
        parent_dir = Path(target_dir or "games")
        dest_dir = unpack_plugin(zip_path, parent_dir)

        # Read configuration metadata
        config_file = dest_dir / "config.yaml"
        if not config_file.is_file():
            raise ValueError("Plugin missing config.yaml after unpacking.")

        with open(config_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        slug = config_data["slug"]
        display_name = config_data.get("display_name", slug)
        description_md = config_data.get("description_md", "")
        config_json = json.dumps(config_data)

        # Invalidate any cached engine for this slug
        self.invalidate_cache(slug)

        # Upsert Game record in database
        existing_game = db.query(Game).filter(Game.slug == slug).first()
        if existing_game:
            existing_game.display_name = display_name
            existing_game.description_md = description_md
            existing_game.plugin_path = str(dest_dir)
            existing_game.config_json = config_json
            existing_game.is_active = True
            db.commit()
            db.refresh(existing_game)
            return existing_game

        new_game = Game(
            slug=slug,
            display_name=display_name,
            description_md=description_md,
            plugin_path=str(dest_dir),
            config_json=config_json,
            is_active=True,
        )
        db.add(new_game)
        db.commit()
        db.refresh(new_game)
        return new_game

    def list_active_games(self, db: Session) -> List[Game]:
        """Return all active game entities registered in the database."""
        return db.query(Game).filter(Game.is_active == True).order_by(Game.id.asc()).all()  # noqa: E712

    def deactivate_game(self, slug: str, db: Session) -> None:
        """Deactivate a game record by slug."""
        game = db.query(Game).filter(Game.slug == slug).first()
        if game:
            game.is_active = False
            db.commit()

    def activate_game(self, slug: str, db: Session) -> None:
        """Activate a game record by slug."""
        game = db.query(Game).filter(Game.slug == slug).first()
        if game:
            game.is_active = True
            db.commit()

    def invalidate_cache(self, slug: Optional[str] = None) -> None:
        """Evict cached GameEngine instances.

        Args:
            slug: Specific game slug to evict, or None to clear all.
        """
        with self._lock:
            if slug is None:
                self._engine_cache.clear()
            else:
                self._engine_cache.pop(slug, None)
