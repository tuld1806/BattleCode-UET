"""Idempotent Multi-Game Database Migration Script.

Performs safe, idempotent schema and data migration to upgrade the platform
database to multi-game support:
1. Ensures all new tables (games, game_profiles, tournaments, tournament_enrollments) exist.
2. Seeds default Game(id=1, slug='rps-chess', display_name='RPS Chess 9x9') if not present.
3. Backfills bot.game_id = 1 and match.game_id = 1 for unassigned records.
4. Migrates non-admin User rating stats into GameProfile(game_id=1).
5. Converts TournamentSetting configurations into a default Tournament row.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from server.database import Base, DATABASE_URL, engine as default_engine
from server.models import (
    Bot,
    Game,
    GameProfile,
    Match,
    Tournament,
    TournamentSetting,
    User,
)


def migrate_multi_game(db_url: Optional[str] = None) -> bool:
    """Execute idempotent database migration for multi-game platform support.

    Args:
        db_url: Optional database connection string. Defaults to active server DATABASE_URL.

    Returns:
        True upon successful completion.
    """
    engine = create_engine(db_url) if db_url else default_engine

    # Step 1: Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        # Step 2: Seed default RPS Chess game (id=1, slug='rps-chess')
        default_game = db.query(Game).filter(Game.slug == "rps-chess").first()
        if not default_game:
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

        game_id = default_game.id

        # Step 3: Backfill bot.game_id = 1 for any bots missing game_id
        db.query(Bot).filter((Bot.game_id == None) | (Bot.game_id == 0)).update(  # noqa: E711
            {"game_id": game_id}, synchronize_session=False
        )
        db.commit()

        # Step 4: Backfill match.game_id = 1 for any matches missing game_id
        db.query(Match).filter((Match.game_id == None) | (Match.game_id == 0)).update(  # noqa: E711
            {"game_id": game_id}, synchronize_session=False
        )
        db.commit()

        # Step 5: Migrate non-admin users to game_profile(game_id=1)
        users = db.query(User).filter(User.is_admin == False).all()  # noqa: E712
        for u in users:
            existing_profile = (
                db.query(GameProfile)
                .filter(GameProfile.user_id == u.id, GameProfile.game_id == game_id)
                .first()
            )
            if not existing_profile:
                # Copy statistics from user record
                profile = GameProfile(
                    user_id=u.id,
                    game_id=game_id,
                    elo=getattr(u, "elo", 1200) or 1200,
                    wins=getattr(u, "wins", 0) or 0,
                    losses=getattr(u, "losses", 0) or 0,
                    draws=getattr(u, "draws", 0) or 0,
                )
                db.add(profile)
        db.commit()

        # Step 6: Convert TournamentSetting into default Tournament if none exists
        existing_tourn = db.query(Tournament).filter(Tournament.game_id == game_id).first()
        if not existing_tourn:
            # Query any existing settings
            settings_map = {
                s.key: s.value
                for s in db.query(TournamentSetting).all()
            }
            start_time = settings_map.get("start_time", settings_map.get("ffa_start_time", "19:00"))
            end_time = settings_map.get("end_time", settings_map.get("ffa_end_time", "21:00"))
            try:
                multiplier = float(settings_map.get("elo_multiplier", "1.0"))
            except ValueError:
                multiplier = 1.0

            tourn = Tournament(
                id=1,
                game_id=game_id,
                name="RPS Chess Championship",
                status="open",
                ffa_start_time=start_time,
                ffa_end_time=end_time,
                ffa_day_count=7,
                bracket_top_n=8,
                elo_multiplier=multiplier,
                enrollment_open=True,
            )
            db.add(tourn)
            db.commit()

        return True
    finally:
        db.close()
        if db_url:
            engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Game Platform Database Migration")
    parser.add_argument("--db-url", type=str, default=None, help="Database connection URL")
    args = parser.parse_args()

    success = migrate_multi_game(args.db_url)
    if success:
        print("Multi-game database migration completed successfully.")
        sys.exit(0)
    else:
        print("Migration failed.", file=sys.stderr)
        sys.exit(1)
