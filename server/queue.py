"""Asynchronous match execution queue and worker jobs.

This module processes queued matches by executing bot matches in isolated
subprocesses via engine.runner, saving replay logs, updating user Elo ratings
and match statistics, and committing outcomes to the database.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from engine.runner import run_match, save_replay
from server.database import SessionLocal
from server.models import Match, TournamentSetting, User, GameProfile, Game
from server.tournament import apply_elo_change, calculate_elo_delta
from server.tournament_config import load_tournament_config

logger = logging.getLogger(__name__)


def _get_setting_value(db, key: str, default: Any, caster: Callable[[str], Any]) -> Any:
    """Retrieve and cast a tournament setting value from the database with a default fallback."""
    try:
        setting = db.query(TournamentSetting).filter(TournamentSetting.key == key).first()
        if setting and setting.value is not None:
            return caster(setting.value)
    except Exception:
        pass
    return default


def execute_match_job(
    match_id: int,
    bot1_path: str,
    bot2_path: str,
    db_factory: Callable[[], Any] | None = None,
) -> dict[str, Any] | None:
    """Execute a queued match job, calculate Elo changes, and save replay artifacts.

    Args:
        match_id: Primary key of the Match record to execute.
        bot1_path: File system path to the Player 1 Python bot script.
        bot2_path: File system path to the Player 2 Python bot script.
        db_factory: Optional callable yielding a SQLAlchemy Session (defaults to SessionLocal).

    Returns:
        The completed match result dictionary, or None if execution failed.
    """
    session_factory = db_factory or SessionLocal
    db = session_factory()

    try:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            logger.error("Match with id %d not found in database.", match_id)
            return None

        player1 = db.query(User).filter(User.id == match.player1_id).first()
        player2 = db.query(User).filter(User.id == match.player2_id).first()

        if not player1 or not player2:
            logger.error("Players for match %d not found.", match_id)
            return None

        # Load configuration parameters and database overrides
        config = load_tournament_config()
        t_cfg = config.get("tournament", {})
        elo_cfg = t_cfg.get("elo", {})
        rules_cfg = t_cfg.get("match_rules", {})

        multiplier_x = _get_setting_value(
            db, "daily_multiplier_x", elo_cfg.get("daily_multiplier_x", 1.5), float
        )
        k_factor = _get_setting_value(
            db, "k_factor", elo_cfg.get("k_factor", 32), int
        )
        max_turns = _get_setting_value(
            db, "max_turns", rules_cfg.get("max_turns", 200), int
        )
        timeout_seconds = _get_setting_value(
            db, "turn_timeout_seconds", rules_cfg.get("turn_timeout_seconds", 1.0), float
        )

        p1_meta = {
            "id": player1.id,
            "username": player1.username,
            "match_id": match_id,
        }
        p2_meta = {
            "id": player2.id,
            "username": player2.username,
            "match_id": match_id,
        }

        # Select the registered engine rather than silently executing all games as RPS.
        from server.game_registry import GameRegistry
        selected_game = db.get(Game, match.game_id or 1)
        selected_engine = None
        if selected_game and selected_game.slug != "rps-chess":
            selected_engine = GameRegistry.get_instance().load_engine(selected_game.slug, db)
        # Run match in isolated worker processes
        match_result = run_match(
            bot1_path=bot1_path,
            bot2_path=bot2_path,
            max_turns=max_turns,
            timeout_per_turn=timeout_seconds,
            player1_info=p1_meta,
            player2_info=p2_meta,
            engine=selected_engine,
        )

        # Save replay JSON
        replays_dir = Path("replays").resolve()
        replays_dir.mkdir(parents=True, exist_ok=True)
        replay_filepath = str(replays_dir / f"match_{match_id}.json")
        save_replay(match_result, replay_filepath)

        # Update Match record
        winner_code = match_result.get("winner")  # 1, 2, or None
        win_reason = match_result.get("win_reason")
        total_turns = match_result.get("total_turns", 0)

        match.replay_path = replay_filepath
        match.win_reason = win_reason
        match.total_turns = total_turns

        if winner_code == 1:
            match.winner_id = player1.id
        elif winner_code == 2:
            match.winner_id = player2.id
        else:
            match.winner_id = None

        

        # Determine game ID (default to 1) and ensure Game exists
        game_id = match.game_id or 1
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            # Create a minimal placeholder Game with required non-null columns
            game = Game(id=game_id, slug=f"game_{game_id}", display_name=f"Game {game_id}")
            db.add(game)
            db.commit()
        # Retrieve or create per-game profiles for both players
        profile1 = db.query(GameProfile).filter(GameProfile.user_id == player1.id, GameProfile.game_id == game_id).first()
        if not profile1:
            profile1 = GameProfile(user_id=player1.id, game_id=game_id, elo=player1.elo if game_id == 1 else 1200)
            db.add(profile1)
            db.commit()
        profile2 = db.query(GameProfile).filter(GameProfile.user_id == player2.id, GameProfile.game_id == game_id).first()
        if not profile2:
            profile2 = GameProfile(user_id=player2.id, game_id=game_id, elo=player2.elo if game_id == 1 else 1200)
            db.add(profile2)
            db.commit()
        # Set initial Elo values, respecting any pre-set bracket Elo values
        if match.is_bracket:
            r1 = match.p1_elo_before if match.p1_elo_before is not None else profile1.elo
            r2 = match.p2_elo_before if match.p2_elo_before is not None else profile2.elo
        else:
            r1 = profile1.elo
            r2 = profile2.elo
        match.p1_elo_before, match.p2_elo_before = r1, r2
        # Update Elo ratings for non-bracket matches using GameProfile
        if not match.is_bracket:
            if winner_code == 1:
                score_1 = 1.0
            elif winner_code == 2:
                score_1 = 0.0
            else:
                score_1 = 0.5



            delta_1, delta_2 = calculate_elo_delta(
                r1, r2, score=score_1, multiplier=multiplier_x, k=k_factor
            )
            new_r1 = apply_elo_change(r1, delta_1)
            new_r2 = apply_elo_change(r2, delta_2)

            profile1.elo = new_r1
            profile2.elo = new_r2
            # Also update global User Elo for leaderboard
            if game_id == 1:
                player1.elo = new_r1
                player2.elo = new_r2
            match.p1_elo_after = new_r1
            match.p2_elo_after = new_r2
        else:
            match.p1_elo_after = r1
            match.p2_elo_after = r2

        # Update player win/loss/draw records (both global and per-game)
        if winner_code == 1:
            player1.wins += 1
            player2.losses += 1
            profile1.wins += 1
            profile2.losses += 1
        elif winner_code == 2:
            player2.wins += 1
            player1.losses += 1
            profile2.wins += 1
            profile1.losses += 1
        else:
            player1.draws += 1
            player2.draws += 1
            profile1.draws += 1
            profile2.draws += 1

        db.commit()
        return match_result

    except Exception as exc:
        logger.exception("Error executing match %d: %s", match_id, exc)
        try:
            match = db.query(Match).filter(Match.id == match_id).first()
            if match:
                match.win_reason = f"Execution error: {exc}"
                db.commit()
        except Exception:
            pass
        return None
    finally:
        db.close()
