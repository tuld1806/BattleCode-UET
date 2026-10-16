"""Tournament configuration loader and validator."""

import copy
import os
from typing import Any, Dict
import yaml

DEFAULT_TOURNAMENT_CONFIG: Dict[str, Any] = {
    "tournament": {
        "title": "Giải Đấu Cờ Oẳn Tù Tì 9x9",
        "total_days": 7,
        "current_day": 1,
        "daily_schedule": {
            "start_time": "19:00",
            "end_time": "21:00",
            "is_portal_open": False,
        },
        "elo": {
            "initial_rating": 1200,
            "k_factor": 32,
            "daily_multiplier_x": 1.5,
        },
        "match_rules": {
            "max_turns": 200,
            "turn_timeout_seconds": 1.0,
        },
        "final_bracket": {
            "top_players_count": 8,
            "match_format": "BO3",
            "weight_elo": 0.5,
            "weight_bracket": 0.5,
        },
    }
}


def _deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override dictionary into a copy of base dictionary.

    Args:
        base: Baseline default configuration dictionary.
        override: Specific user-provided override mappings.

    Returns:
        Merged configuration dictionary.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _validate_and_sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate tournament configuration values and fallback to defaults on anomalies.

    Args:
        config: Raw parsed and merged configuration.

    Returns:
        Sanitized and validated configuration dictionary.
    """
    defaults = DEFAULT_TOURNAMENT_CONFIG["tournament"]
    t_cfg = config.setdefault("tournament", copy.deepcopy(defaults))

    if not isinstance(t_cfg, dict):
        config["tournament"] = copy.deepcopy(defaults)
        return config

    # Ensure required sub-sections exist
    for section in ["daily_schedule", "elo", "match_rules", "final_bracket"]:
        if section not in t_cfg or not isinstance(t_cfg[section], dict):
            t_cfg[section] = copy.deepcopy(defaults[section])

    # Validate integer / numerical bounds
    if not isinstance(t_cfg.get("total_days"), int) or t_cfg["total_days"] <= 0:
        t_cfg["total_days"] = defaults["total_days"]

    if not isinstance(t_cfg.get("current_day"), int) or t_cfg["current_day"] <= 0:
        t_cfg["current_day"] = defaults["current_day"]

    elo = t_cfg["elo"]
    if not isinstance(elo.get("initial_rating"), (int, float)) or elo["initial_rating"] < 0:
        elo["initial_rating"] = defaults["elo"]["initial_rating"]
    else:
        elo["initial_rating"] = int(elo["initial_rating"])

    if not isinstance(elo.get("k_factor"), (int, float)) or elo["k_factor"] <= 0:
        elo["k_factor"] = defaults["elo"]["k_factor"]
    else:
        elo["k_factor"] = int(elo["k_factor"])

    if not isinstance(elo.get("daily_multiplier_x"), (int, float)) or elo["daily_multiplier_x"] <= 0:
        elo["daily_multiplier_x"] = defaults["elo"]["daily_multiplier_x"]
    else:
        elo["daily_multiplier_x"] = float(elo["daily_multiplier_x"])

    rules = t_cfg["match_rules"]
    if not isinstance(rules.get("max_turns"), int) or rules["max_turns"] <= 0:
        rules["max_turns"] = defaults["match_rules"]["max_turns"]

    if not isinstance(rules.get("turn_timeout_seconds"), (int, float)) or rules["turn_timeout_seconds"] <= 0:
        rules["turn_timeout_seconds"] = defaults["match_rules"]["turn_timeout_seconds"]
    else:
        rules["turn_timeout_seconds"] = float(rules["turn_timeout_seconds"])

    bracket = t_cfg["final_bracket"]
    if not isinstance(bracket.get("top_players_count"), int) or bracket["top_players_count"] < 2:
        bracket["top_players_count"] = defaults["final_bracket"]["top_players_count"]

    return config


def load_tournament_config(config_path: str = "config/tournament.yaml") -> Dict[str, Any]:
    """Load tournament configuration from YAML file with validation and fallback defaults.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated dictionary containing complete tournament configuration.
    """
    if not os.path.isfile(config_path):
        return copy.deepcopy(DEFAULT_TOURNAMENT_CONFIG)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return copy.deepcopy(DEFAULT_TOURNAMENT_CONFIG)

    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_TOURNAMENT_CONFIG)

    merged = _deep_merge_dict(DEFAULT_TOURNAMENT_CONFIG, data)
    return _validate_and_sanitize_config(merged)
