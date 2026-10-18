"""Database connection, SQLite engine configuration, and session management."""

import os
from typing import Generator, Optional
from sqlalchemy import create_engine, event
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
        existing = db.query(Game).filter(Game.slug == "rps-chess").first()
        if not existing:
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
    except Exception:
        db.rollback()
        raise
    finally:
        if close_after:
            db.close()


def init_db(target_engine=None) -> None:
    """Create all database tables registered on Base metadata and seed default game."""
    from server import models  # noqa: F401
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    seed_default_game(target_engine=eng)

