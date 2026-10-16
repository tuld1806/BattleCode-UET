"""Battlecode RPS tournament platform server package."""

from server.database import Base, SessionLocal, engine, get_db, init_db
from server.models import Bot, BracketMatch, Match, TournamentSetting, User
from server.tournament import (
    apply_elo_change,
    calculate_elo_delta,
    calculate_final_scores,
    generate_bracket,
    is_ffa_portal_open,
)
from server.tournament_config import DEFAULT_TOURNAMENT_CONFIG, load_tournament_config

__all__ = [
    "Base",
    "Bot",
    "BracketMatch",
    "DEFAULT_TOURNAMENT_CONFIG",
    "Match",
    "SessionLocal",
    "TournamentSetting",
    "User",
    "apply_elo_change",
    "calculate_elo_delta",
    "calculate_final_scores",
    "engine",
    "generate_bracket",
    "get_db",
    "init_db",
    "is_ffa_portal_open",
    "load_tournament_config",
]
