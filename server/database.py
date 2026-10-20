"""Database connection, SQLite engine configuration, and session management."""

from contextlib import contextmanager
import os
from typing import Generator, Optional
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Database URL defaulting to SQLite app.db, configurable via DATABASE_URL environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configure SQLite connections with WAL mode and foreign key support.

    Executes PRAGMA journal_mode=WAL and PRAGMA synchronous=NORMAL for concurrent
    performance and reliability, and enables foreign keys for relational integrity.
    """
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        # Silently pass if connected to non-SQLite database
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency generator that yields a database session and ensures clean closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager yielding a Session and ensuring clean closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_default_game(db_session: Optional[Session] = None, target_engine=None) -> None:
    """Ensure baseline RPS Chess game (id=1, slug='rps-chess') exists for relational integrity."""
    from server.models import Game
    close_after = False
    if db_session is not None:
        db = db_session
    else:
        eng = target_engine or engine
        scoped_session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = scoped_session()
        close_after = True

    try:
        from server.models import Game, Tournament
        from sqlalchemy import or_
        existing = db.query(Game).filter(or_(Game.id == 1, Game.slug == "rps-chess")).first()
        if existing:
            if existing.slug != "rps-chess":
                existing.slug = "rps-chess"
                db.commit()
            existing_t = db.query(Tournament).filter(Tournament.game_id == existing.id).first()
            if not existing_t:
                default_t = Tournament(
                    id=1,
                    game_id=existing.id,
                    name="RPS Chess Championship",
                    status="open",
                    ffa_start_time="19:00",
                    ffa_end_time="21:00",
                    ffa_day_count=7,
                    bracket_top_n=8,
                    elo_multiplier=1.5,
                    enrollment_open=True,
                )
                db.add(default_t)
                db.commit()
            return

        default_game = Game(
            id=1,
            slug="rps-chess",
            display_name="RPS Chess 9x9",
            description_md="Two players battle on a 9x9 grid using Rock, Paper, Scissors pieces.",
            plugin_path="games/rps_chess",
            config_json='{"max_turns": 200, "bot_interface": "python_function", "timeout_ms": 1000}',
            is_active=True,
        )
        db.add(default_game)
        db.commit()
        db.refresh(default_game)

        default_t = Tournament(
            id=1,
            game_id=default_game.id,
            name="RPS Chess Championship",
            status="open",
            ffa_start_time="19:00",
            ffa_end_time="21:00",
            ffa_day_count=7,
            bracket_top_n=8,
            elo_multiplier=1.5,
            enrollment_open=True,
        )
        db.add(default_t)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        if close_after:
            db.close()


def auto_discover_and_seed_games(
    db_session: Optional[Session] = None, target_engine=None
):
    """Scan the games/ directory and idempotently register all discovered games in the database.

    For every subdirectory in games/ containing config.yaml and engine.py:
    1. Parse config.yaml manifest safely
    2. Upsert Game record in DB
    3. Ensure an active default Tournament exists for the game
    """
    from pathlib import Path
    import json
    import yaml
    from server.models import Game, Tournament

    close_after = False
    if db_session is not None:
        db = db_session
    else:
        eng = target_engine or engine
        scoped_session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = scoped_session()
        close_after = True

    discovered_games = []
    try:
        repo_root = Path(__file__).resolve().parent.parent
        games_dir = repo_root / "games"

        if games_dir.exists() and games_dir.is_dir():
            for entry in sorted(games_dir.iterdir(), key=lambda p: p.name):
                if entry.is_dir() and not entry.name.startswith((".", "_")):
                    config_file = entry / "config.yaml"
                    engine_file = entry / "engine.py"
                    if config_file.is_file() and engine_file.is_file():
                        try:
                            with open(config_file, "r", encoding="utf-8") as f:
                                config_data = yaml.safe_load(f) or {}
                        except Exception:
                            # Skip malformed YAML manifests safely
                            continue

                        slug = str(config_data.get("slug", entry.name)).strip()
                        display_name = str(config_data.get("display_name", slug.replace("-", " ").title())).strip()
                        description_md = str(config_data.get("description_md", f"Rules and information for {display_name}"))
                        plugin_rel_path = f"games/{entry.name}"

                        cfg_copy = {
                            k: v for k, v in config_data.items()
                            if k not in ("slug", "display_name", "description_md")
                        }
                        config_json = json.dumps(cfg_copy)

                        existing_game = db.query(Game).filter(Game.slug == slug).first()
                        if existing_game:
                            existing_game.display_name = display_name
                            existing_game.description_md = description_md
                            existing_game.plugin_path = plugin_rel_path
                            existing_game.config_json = config_json
                            existing_game.is_active = True
                            target_game = existing_game
                        else:
                            target_game = Game(
                                slug=slug,
                                display_name=display_name,
                                description_md=description_md,
                                plugin_path=plugin_rel_path,
                                config_json=config_json,
                                is_active=True,
                            )
                            db.add(target_game)
                            db.flush()

                        existing_t = db.query(Tournament).filter(Tournament.game_id == target_game.id).first()
                        if not existing_t:
                            default_t = Tournament(
                                game_id=target_game.id,
                                name=f"{display_name} Championship",
                                status="open",
                                ffa_start_time="19:00",
                                ffa_end_time="21:00",
                                ffa_day_count=7,
                                bracket_top_n=8,
                                elo_multiplier=1.5,
                                enrollment_open=True,
                            )
                            db.add(default_t)

                        discovered_games.append(target_game)

        db.commit()
        for g in discovered_games:
            db.refresh(g)
        return discovered_games
    except Exception:
        db.rollback()
        return []
    finally:
        if close_after:
            db.close()


def seed_default_badges(db_session: Optional[Session] = None, target_engine=None) -> None:
    """Idempotently seed default platform achievement badges."""
    from server.models import Badge
    close_after = False
    if db_session is not None:
        db = db_session
    else:
        eng = target_engine or engine
        scoped_session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        db = scoped_session()
        close_after = True

    default_badges = [
        {
            "slug": "top_1_champion",
            "name": "Top 1 Giải Đấu",
            "description": "Vô địch vòng chung kết playoff giải đấu.",
            "icon": "👑",
        },
        {
            "slug": "boss_slayer",
            "name": "Kẻ Hủy Diệt Boss",
            "description": "Đánh bại Boss cấp cao nhất (Apex Master).",
            "icon": "⚔️",
        },
        {
            "slug": "active_player",
            "name": "Kỳ Thủ Tích Cực",
            "description": "Đã tham gia thi đấu từ 10 trận trở lên.",
            "icon": "🔥",
        },
    ]

    try:
        for b_data in default_badges:
            existing = db.query(Badge).filter(Badge.slug == b_data["slug"]).first()
            if not existing:
                b = Badge(**b_data)
                db.add(b)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        if close_after:
            db.close()


def init_db(target_engine=None) -> None:
    """Create all database tables registered on Base metadata and seed discovered games."""
    from server import models  # noqa: F401
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    # Safe auto-migration for SQLite to ensure bracket_matches has tournament_id column
    try:
        with eng.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(bracket_matches)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "tournament_id" not in columns:
                conn.execute(
                    text("ALTER TABLE bracket_matches ADD COLUMN tournament_id INTEGER REFERENCES tournaments(id)")
                )
                conn.commit()
    except Exception:
        pass

    seed_default_game(target_engine=eng)
    auto_discover_and_seed_games(target_engine=eng)
    seed_default_badges(target_engine=eng)



