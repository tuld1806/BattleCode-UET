"""Registry and metadata for server-side boss benchmark bots.

Provides standardized configuration for the five graduated AI benchmark bots
used in FFA seeding, tournament calibration, and admin match testing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_CURRENT_DIR = Path(__file__).resolve().parent

BOSS_REGISTRY: dict[str, dict[str, Any]] = {
    "novice": {
        "slug": "novice",
        "name": "Novice",
        "display_name": "[Boss] Level 1: Novice",
        "level": 1,
        "default_elo": 1000,
        "description": "Opportunistic beginner bot that takes immediate goal wins and favorable captures, otherwise moving randomly.",
        "file_path": str(_CURRENT_DIR / "novice_bot.py"),
    },
    "rusher": {
        "slug": "rusher",
        "name": "Rusher",
        "display_name": "[Boss] Level 2: Rusher",
        "level": 2,
        "default_elo": 1200,
        "description": "Aggressive sprinter bot that rushes directly towards the enemy goal while evading obvious traps.",
        "file_path": str(_CURRENT_DIR / "rusher_bot.py"),
    },
    "sentinel": {
        "slug": "sentinel",
        "name": "Sentinel",
        "display_name": "[Boss] Level 3: Sentinel",
        "level": 3,
        "default_elo": 1400,
        "description": "Defensive tactician that protects its home goal perimeter and targets the opponent's scarce piece type for wipeout.",
        "file_path": str(_CURRENT_DIR / "sentinel_bot.py"),
    },
    "tactician": {
        "slug": "tactician",
        "name": "Tactician",
        "display_name": "[Boss] Level 4: Tactician",
        "level": 4,
        "default_elo": 1600,
        "description": "Strategic engine running 2-ply Minimax search with Alpha-Beta pruning, balancing material, threats, and goal distance.",
        "file_path": str(_CURRENT_DIR / "tactician_bot.py"),
    },
    "apex": {
        "slug": "apex",
        "name": "Apex Master",
        "display_name": "[Boss] Level 5: Apex Master",
        "level": 5,
        "default_elo": 1800,
        "description": "Grandmaster bot running adaptive dynamic-depth Minimax with tactical piece baiting, threat response, and endgame convergence.",
        "file_path": str(_CURRENT_DIR / "apex_bot.py"),
    },
}


def get_boss(slug: str) -> dict[str, Any] | None:
    """Retrieve metadata dictionary for a specific boss slug.

    Args:
        slug: Boss identifier ('novice', 'rusher', 'sentinel', 'tactician', 'apex').

    Returns:
        Boss metadata dictionary if found, None otherwise.
    """
    return BOSS_REGISTRY.get(slug)


def get_all_bosses() -> list[dict[str, Any]]:
    """Retrieve list of all boss configurations ordered by level (1 to 5).

    Returns:
        List of boss metadata dictionaries.
    """
    return sorted(BOSS_REGISTRY.values(), key=lambda b: b["level"])
