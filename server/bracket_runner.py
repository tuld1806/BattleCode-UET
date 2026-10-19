"""Automated Playoff Bracket Best-of-3 (BO3) Match Runner Service.

Executes playoff bracket series between active player bots with side alternation
(Red/Blue), persists scores and replays, and advances winners through single
elimination stages until a tournament champion is crowned.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from engine.runner import run_match, save_replay
from server.game_registry import GameRegistry
from server.models import Bot, BracketMatch, Game, Tournament, User

logger = logging.getLogger(__name__)

NEXT_ROUND_MAP: Dict[str, str] = {
    "Round of 64": "Round of 32",
    "Round of 32": "Round of 16",
    "Round of 16": "Quarter-Final",
    "Quarter-Final": "Semi-Final",
    "Quarterfinal": "Semi-Final",
    "Quarterfinals": "Semi-Final",
    "Semi-Final": "Final",
    "Semifinal": "Final",
    "Semifinals": "Final",
}


def _get_active_bot(db: Session, user_id: int, game_id: Optional[int] = None) -> Optional[Bot]:
    """Retrieve the primary active bot for a given user."""
    query = db.query(Bot).filter(Bot.user_id == user_id, Bot.is_active == True)  # noqa: E712
    if game_id is not None:
        bot = query.filter(Bot.game_id == game_id).first()
        if bot:
            return bot
    return query.first()


def _resolve_game_engine(db: Session, tournament_id: Optional[int] = None) -> Any:
    """Resolve GameEngine instance for the active tournament or default game."""
    try:
        registry = GameRegistry.get_instance()
        if tournament_id is not None:
            tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
            if tourney and tourney.game_id:
                game = db.query(Game).filter(Game.id == tourney.game_id).first()
                if game and game.slug:
                    return registry.load_engine(game.slug, db=db)
        return registry.load_engine("rps-chess", db=db)
    except Exception as exc:
        logger.warning(f"Could not dynamically load engine: {exc}. Falling back to default.")
        return None


def execute_bo3_series(
    match: BracketMatch,
    bot1_path: str,
    bot2_path: str,
    engine: Any = None,
    replay_dir: str = "replays",
) -> tuple[int, int, int]:
    """Execute a Best-of-3 series between two bot scripts with side alternation.

    Game 1: Player 1 (Red) vs Player 2 (Blue)
    Game 2: Player 2 (Red) vs Player 1 (Blue)
    Game 3 (if needed): Player 1 (Red) vs Player 2 (Blue)

    Returns:
        (score_p1, score_p2, winner_id)
    """
    os.makedirs(replay_dir, exist_ok=True)
    score_p1 = 0
    score_p2 = 0

    # Game 1: P1 (Red) vs P2 (Blue)
    res1 = run_match(
        bot1_path=bot1_path,
        bot2_path=bot2_path,
        max_turns=200,
        timeout_per_turn=1.0,
        engine=engine,
    )
    try:
        save_replay(res1, os.path.join(replay_dir, f"bracket_{match.id}_game_1.json"))
    except Exception:
        pass

    if res1.get("winner") == 1:
        score_p1 += 1
    elif res1.get("winner") == 2:
        score_p2 += 1

    # Check if series concluded early (not typical for BO3, but handle 2-0)
    if score_p1 >= 2 or score_p2 >= 2:
        winner_id = match.player1_id if score_p1 > score_p2 else match.player2_id
        return score_p1, score_p2, winner_id

    # Game 2: P2 (Red) vs P1 (Blue) - Alternate sides
    res2 = run_match(
        bot1_path=bot2_path,
        bot2_path=bot1_path,
        max_turns=200,
        timeout_per_turn=1.0,
        engine=engine,
    )
    try:
        save_replay(res2, os.path.join(replay_dir, f"bracket_{match.id}_game_2.json"))
    except Exception:
        pass

    # Here bot1 was P2, bot2 was P1
    if res2.get("winner") == 1:
        score_p2 += 1
    elif res2.get("winner") == 2:
        score_p1 += 1

    if score_p1 >= 2 or score_p2 >= 2:
        winner_id = match.player1_id if score_p1 > score_p2 else match.player2_id
        return score_p1, score_p2, winner_id

    # Game 3: P1 (Red) vs P2 (Blue) - Decider
    res3 = run_match(
        bot1_path=bot1_path,
        bot2_path=bot2_path,
        max_turns=200,
        timeout_per_turn=1.0,
        engine=engine,
    )
    try:
        save_replay(res3, os.path.join(replay_dir, f"bracket_{match.id}_game_3.json"))
    except Exception:
        pass

    if res3.get("winner") == 1:
        score_p1 += 1
    elif res3.get("winner") == 2:
        score_p2 += 1

    if score_p1 > score_p2:
        winner_id = match.player1_id
    elif score_p2 > score_p1:
        winner_id = match.player2_id
    else:
        # Tiebreak fallback: Seed 1 / Player 1 default
        winner_id = match.player1_id

    return score_p1, score_p2, winner_id


def run_bracket_round(db: Session, tournament_id: Optional[int] = None) -> Dict[str, Any]:
    """Execute all pending matches in the active bracket round and advance winners.

    Args:
        db: SQLAlchemy database session.
        tournament_id: Optional ID of the tournament context.

    Returns:
        Summary dict containing round_name, matches_played, champion_id, and status.
    """
    pending_matches = (
        db.query(BracketMatch)
        .filter(BracketMatch.status == "pending")
        .order_by(BracketMatch.id.asc())
        .all()
    )

    if not pending_matches:
        # Check if the tournament has concluded
        final_match = (
            db.query(BracketMatch)
            .filter(BracketMatch.round_name.ilike("%final%"), BracketMatch.status == "completed")
            .order_by(BracketMatch.id.desc())
            .first()
        )
        champion_id = final_match.winner_id if final_match else None
        return {
            "message": "No pending bracket matches found.",
            "matches_played": 0,
            "champion_id": champion_id,
            "status": "finished" if champion_id else "idle",
        }

    # Execute all pending matches in the first available round stage
    current_round_name = pending_matches[0].round_name
    active_matches = [m for m in pending_matches if m.round_name == current_round_name]
    active_matches.sort(key=lambda m: m.match_index)

    # Determine game_id if tournament_id is given
    game_id: Optional[int] = None
    if tournament_id is not None:
        tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if tourney:
            game_id = tourney.game_id

    engine = _resolve_game_engine(db, tournament_id=tournament_id)

    matches_played = 0
    for match in active_matches:
        bot1 = _get_active_bot(db, match.player1_id, game_id=game_id)
        bot2 = _get_active_bot(db, match.player2_id, game_id=game_id)

        # Walkover scenario 1: neither player has an active bot
        if not bot1 and not bot2:
            match.score_p1 = 2
            match.score_p2 = 0
            match.winner_id = match.player1_id
            match.status = "completed"
            matches_played += 1
            continue

        # Walkover scenario 2: player 1 missing active bot
        if not bot1 and bot2:
            match.score_p1 = 0
            match.score_p2 = 2
            match.winner_id = match.player2_id
            match.status = "completed"
            matches_played += 1
            continue

        # Walkover scenario 3: player 2 missing active bot
        if bot1 and not bot2:
            match.score_p1 = 2
            match.score_p2 = 0
            match.winner_id = match.player1_id
            match.status = "completed"
            matches_played += 1
            continue

        # Both have active bots: run BO3
        assert bot1 is not None and bot2 is not None
        s1, s2, winner_id = execute_bo3_series(
            match=match,
            bot1_path=bot1.filepath,
            bot2_path=bot2.filepath,
            engine=engine,
        )
        match.score_p1 = s1
        match.score_p2 = s2
        match.winner_id = winner_id
        match.status = "completed"
        matches_played += 1

    db.commit()

    # Check whether the current round has fully completed
    remaining_pending = (
        db.query(BracketMatch)
        .filter(BracketMatch.round_name == current_round_name, BracketMatch.status == "pending")
        .count()
    )

    champion_id: Optional[int] = None

    if remaining_pending == 0:
        # Check next round transition
        next_round_name = NEXT_ROUND_MAP.get(current_round_name)
        if next_round_name:
            completed_matches = (
                db.query(BracketMatch)
                .filter(BracketMatch.round_name == current_round_name)
                .order_by(BracketMatch.match_index.asc())
                .all()
            )
            # Pair consecutive winners into the next round
            for i in range(0, len(completed_matches), 2):
                p1_id = completed_matches[i].winner_id
                p2_id = (
                    completed_matches[i + 1].winner_id
                    if i + 1 < len(completed_matches)
                    else None
                )
                if p1_id and p2_id:
                    next_match = BracketMatch(
                        round_name=next_round_name,
                        match_index=i // 2,
                        player1_id=p1_id,
                        player2_id=p2_id,
                        status="pending",
                    )
                    db.add(next_match)
            db.commit()
        elif "final" in current_round_name.lower():
            # Concluded tournament champion
            final_match = active_matches[-1]
            champion_id = final_match.winner_id
            if tournament_id is not None:
                tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
                if tourney:
                    tourney.status = "finished"
                    db.commit()

    return {
        "round_name": current_round_name,
        "matches_played": matches_played,
        "champion_id": champion_id,
        "status": "finished" if champion_id else "in_progress",
    }


def run_all_bracket_rounds(db: Session, tournament_id: Optional[int] = None) -> Dict[str, Any]:
    """Sequentially execute all remaining bracket rounds until the Finals conclude.

    Args:
        db: SQLAlchemy database session.
        tournament_id: Optional ID of the tournament context.

    Returns:
        Summary dict containing total_matches_played, rounds_executed, champion_id, and status.
    """
    total_played = 0
    rounds_executed: List[str] = []
    champion_id: Optional[int] = None

    for _ in range(10):  # Maximum 10 rounds to avoid runaway loops
        result = run_bracket_round(db, tournament_id=tournament_id)
        matches = result.get("matches_played", 0)
        if matches == 0:
            champion_id = result.get("champion_id")
            break
        total_played += matches
        rnd = result.get("round_name")
        if rnd and rnd not in rounds_executed:
            rounds_executed.append(rnd)
        champion_id = result.get("champion_id")
        if champion_id is not None:
            break

    return {
        "total_matches_played": total_played,
        "rounds_executed": rounds_executed,
        "champion_id": champion_id,
        "status": "finished" if champion_id else "in_progress",
    }
