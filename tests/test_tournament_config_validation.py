"""Comprehensive edge-case tests for tournament configuration validation.

Tests the _validate_and_sanitize_config function in server/tournament_config.py,
covering boundary conditions, type mismatches, negative values, missing keys,
and malformed sub-sections that the validator must handle gracefully.
"""

import copy
import pytest
from pathlib import Path
from server.tournament_config import (
    DEFAULT_TOURNAMENT_CONFIG,
    _deep_merge_dict,
    _validate_and_sanitize_config,
    load_tournament_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_config():
    """Return a fresh deep copy of the default tournament configuration."""
    return copy.deepcopy(DEFAULT_TOURNAMENT_CONFIG)


@pytest.fixture
def defaults():
    """Return the inner tournament defaults for assertion comparisons."""
    return DEFAULT_TOURNAMENT_CONFIG["tournament"]


# ---------------------------------------------------------------------------
# Tests: _validate_and_sanitize_config boundary cases
# ---------------------------------------------------------------------------

class TestValidateAndSanitize:
    """Tests for _validate_and_sanitize_config validator correctness."""

    def test_negative_total_days_falls_back(self, default_config, defaults):
        """Negative total_days must reset to default."""
        default_config["tournament"]["total_days"] = -5
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["total_days"] == defaults["total_days"]

    def test_zero_total_days_falls_back(self, default_config, defaults):
        """Zero total_days must reset to default (must be > 0)."""
        default_config["tournament"]["total_days"] = 0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["total_days"] == defaults["total_days"]

    def test_string_total_days_falls_back(self, default_config, defaults):
        """Non-integer total_days must reset to default."""
        default_config["tournament"]["total_days"] = "seven"
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["total_days"] == defaults["total_days"]

    def test_negative_current_day_falls_back(self, default_config, defaults):
        """Negative current_day must reset to default."""
        default_config["tournament"]["current_day"] = -1
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["current_day"] == defaults["current_day"]

    def test_zero_current_day_falls_back(self, default_config, defaults):
        """Zero current_day must reset to default (must be > 0)."""
        default_config["tournament"]["current_day"] = 0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["current_day"] == defaults["current_day"]

    def test_negative_initial_rating_falls_back(self, default_config, defaults):
        """Negative initial_rating must reset to default."""
        default_config["tournament"]["elo"]["initial_rating"] = -100
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["initial_rating"] == defaults["elo"]["initial_rating"]

    def test_float_initial_rating_casts_to_int(self, default_config):
        """Float initial_rating must be cast to int."""
        default_config["tournament"]["elo"]["initial_rating"] = 1500.7
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["initial_rating"] == 1500
        assert isinstance(result["tournament"]["elo"]["initial_rating"], int)

    def test_string_initial_rating_falls_back(self, default_config, defaults):
        """String initial_rating must reset to default."""
        default_config["tournament"]["elo"]["initial_rating"] = "high"
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["initial_rating"] == defaults["elo"]["initial_rating"]

    def test_negative_k_factor_falls_back(self, default_config, defaults):
        """Negative k_factor must reset to default."""
        default_config["tournament"]["elo"]["k_factor"] = -32
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["k_factor"] == defaults["elo"]["k_factor"]

    def test_zero_k_factor_falls_back(self, default_config, defaults):
        """Zero k_factor must reset to default (must be > 0)."""
        default_config["tournament"]["elo"]["k_factor"] = 0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["k_factor"] == defaults["elo"]["k_factor"]

    def test_float_k_factor_casts_to_int(self, default_config):
        """Float k_factor must be cast to int."""
        default_config["tournament"]["elo"]["k_factor"] = 48.9
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["k_factor"] == 48
        assert isinstance(result["tournament"]["elo"]["k_factor"], int)

    def test_negative_multiplier_falls_back(self, default_config, defaults):
        """Negative daily_multiplier_x must reset to default."""
        default_config["tournament"]["elo"]["daily_multiplier_x"] = -2.0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["daily_multiplier_x"] == defaults["elo"]["daily_multiplier_x"]

    def test_zero_multiplier_falls_back(self, default_config, defaults):
        """Zero daily_multiplier_x must reset to default (must be > 0)."""
        default_config["tournament"]["elo"]["daily_multiplier_x"] = 0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["daily_multiplier_x"] == defaults["elo"]["daily_multiplier_x"]

    def test_int_multiplier_casts_to_float(self, default_config):
        """Integer daily_multiplier_x must be cast to float."""
        default_config["tournament"]["elo"]["daily_multiplier_x"] = 2
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"]["daily_multiplier_x"] == 2.0
        assert isinstance(result["tournament"]["elo"]["daily_multiplier_x"], float)

    def test_negative_max_turns_falls_back(self, default_config, defaults):
        """Negative max_turns must reset to default."""
        default_config["tournament"]["match_rules"]["max_turns"] = -10
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["match_rules"]["max_turns"] == defaults["match_rules"]["max_turns"]

    def test_zero_max_turns_falls_back(self, default_config, defaults):
        """Zero max_turns must reset to default (must be > 0)."""
        default_config["tournament"]["match_rules"]["max_turns"] = 0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["match_rules"]["max_turns"] == defaults["match_rules"]["max_turns"]

    def test_negative_timeout_falls_back(self, default_config, defaults):
        """Negative turn_timeout_seconds must reset to default."""
        default_config["tournament"]["match_rules"]["turn_timeout_seconds"] = -0.5
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["match_rules"]["turn_timeout_seconds"] == defaults["match_rules"]["turn_timeout_seconds"]

    def test_zero_timeout_falls_back(self, default_config, defaults):
        """Zero turn_timeout_seconds must reset to default."""
        default_config["tournament"]["match_rules"]["turn_timeout_seconds"] = 0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["match_rules"]["turn_timeout_seconds"] == defaults["match_rules"]["turn_timeout_seconds"]

    def test_int_timeout_casts_to_float(self, default_config):
        """Integer turn_timeout_seconds must be cast to float."""
        default_config["tournament"]["match_rules"]["turn_timeout_seconds"] = 2
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["match_rules"]["turn_timeout_seconds"] == 2.0
        assert isinstance(result["tournament"]["match_rules"]["turn_timeout_seconds"], float)

    def test_top_players_count_below_minimum_falls_back(self, default_config, defaults):
        """top_players_count < 2 must reset to default."""
        default_config["tournament"]["final_bracket"]["top_players_count"] = 1
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["final_bracket"]["top_players_count"] == defaults["final_bracket"]["top_players_count"]

    def test_top_players_count_zero_falls_back(self, default_config, defaults):
        """Zero top_players_count must reset to default."""
        default_config["tournament"]["final_bracket"]["top_players_count"] = 0
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["final_bracket"]["top_players_count"] == defaults["final_bracket"]["top_players_count"]

    def test_top_players_count_negative_falls_back(self, default_config, defaults):
        """Negative top_players_count must reset to default."""
        default_config["tournament"]["final_bracket"]["top_players_count"] = -4
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["final_bracket"]["top_players_count"] == defaults["final_bracket"]["top_players_count"]

    def test_missing_elo_section_restores_defaults(self, default_config, defaults):
        """Entirely missing elo sub-section must be restored from defaults."""
        del default_config["tournament"]["elo"]
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"] == defaults["elo"]

    def test_missing_match_rules_restores_defaults(self, default_config, defaults):
        """Missing match_rules sub-section must be restored from defaults."""
        del default_config["tournament"]["match_rules"]
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["match_rules"] == defaults["match_rules"]

    def test_missing_final_bracket_restores_defaults(self, default_config, defaults):
        """Missing final_bracket sub-section must be restored from defaults."""
        del default_config["tournament"]["final_bracket"]
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["final_bracket"] == defaults["final_bracket"]

    def test_missing_daily_schedule_restores_defaults(self, default_config, defaults):
        """Missing daily_schedule sub-section must be restored from defaults."""
        del default_config["tournament"]["daily_schedule"]
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["daily_schedule"] == defaults["daily_schedule"]

    def test_non_dict_tournament_section_replaces_with_defaults(self, defaults):
        """If tournament section is a scalar instead of dict, replace entirely."""
        config = {"tournament": "invalid_string"}
        result = _validate_and_sanitize_config(config)
        assert isinstance(result["tournament"], dict)
        assert result["tournament"]["total_days"] == defaults["total_days"]

    def test_non_dict_elo_section_replaces_with_defaults(self, default_config, defaults):
        """If elo sub-section is a scalar instead of dict, replace entirely."""
        default_config["tournament"]["elo"] = "broken"
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["elo"] == defaults["elo"]

    def test_missing_tournament_key_creates_defaults(self, defaults):
        """If tournament key is missing entirely, defaults must be created."""
        config = {}
        result = _validate_and_sanitize_config(config)
        assert "tournament" in result
        assert result["tournament"]["total_days"] == defaults["total_days"]

    def test_valid_config_passes_through_unchanged(self, default_config):
        """A valid configuration must not be mutated by the validator."""
        default_config["tournament"]["total_days"] = 14
        default_config["tournament"]["elo"]["k_factor"] = 64
        default_config["tournament"]["match_rules"]["max_turns"] = 300
        result = _validate_and_sanitize_config(default_config)
        assert result["tournament"]["total_days"] == 14
        assert result["tournament"]["elo"]["k_factor"] == 64
        assert result["tournament"]["match_rules"]["max_turns"] == 300


# ---------------------------------------------------------------------------
# Tests: _deep_merge_dict correctness
# ---------------------------------------------------------------------------

class TestDeepMergeDict:
    """Tests for _deep_merge_dict recursive merge function."""

    def test_override_scalar_values(self):
        """Scalar values in override must replace base values."""
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        result = _deep_merge_dict(base, override)
        assert result == {"a": 1, "b": 99}

    def test_recursive_nested_merge(self):
        """Nested dicts must merge recursively, not replace the whole sub-dict."""
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 99, "c": 3}}
        result = _deep_merge_dict(base, override)
        assert result == {"outer": {"a": 1, "b": 99, "c": 3}}

    def test_does_not_mutate_base(self):
        """Deep merge must not mutate the original base dictionary."""
        base = {"x": {"y": 1}}
        override = {"x": {"y": 2}}
        original_base = copy.deepcopy(base)
        _deep_merge_dict(base, override)
        assert base == original_base

    def test_override_dict_with_scalar(self):
        """If override replaces a dict with a scalar, the scalar wins."""
        base = {"x": {"nested": True}}
        override = {"x": "replaced"}
        result = _deep_merge_dict(base, override)
        assert result["x"] == "replaced"


# ---------------------------------------------------------------------------
# Tests: load_tournament_config YAML edge cases
# ---------------------------------------------------------------------------

class TestLoadTournamentConfig:
    """Tests for load_tournament_config YAML loader resilience."""

    def test_yaml_with_only_partial_overrides(self, tmp_path):
        """YAML with partial overrides must merge with defaults cleanly."""
        yaml_file = tmp_path / "partial.yaml"
        yaml_file.write_text("tournament:\n  total_days: 14\n", encoding="utf-8")
        cfg = load_tournament_config(str(yaml_file))
        assert cfg["tournament"]["total_days"] == 14
        # Defaults for unspecified keys must survive the merge
        assert cfg["tournament"]["elo"]["k_factor"] == 32
        assert cfg["tournament"]["match_rules"]["max_turns"] == 200

    def test_yaml_with_empty_document(self, tmp_path):
        """An empty YAML document must not crash and should return defaults."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("", encoding="utf-8")
        cfg = load_tournament_config(str(yaml_file))
        # yaml.safe_load("") returns None which is not a dict
        assert cfg["tournament"]["total_days"] == DEFAULT_TOURNAMENT_CONFIG["tournament"]["total_days"]

    def test_yaml_with_list_root(self, tmp_path):
        """A YAML list at root level must be rejected and return defaults."""
        yaml_file = tmp_path / "list.yaml"
        yaml_file.write_text("- item1\n- item2\n", encoding="utf-8")
        cfg = load_tournament_config(str(yaml_file))
        assert cfg["tournament"]["total_days"] == DEFAULT_TOURNAMENT_CONFIG["tournament"]["total_days"]

    def test_yaml_with_invalid_syntax(self, tmp_path):
        """Malformed YAML must not crash and should return defaults."""
        yaml_file = tmp_path / "broken.yaml"
        yaml_file.write_text("tournament:\n  total_days: [unclosed", encoding="utf-8")
        cfg = load_tournament_config(str(yaml_file))
        assert cfg["tournament"]["total_days"] == DEFAULT_TOURNAMENT_CONFIG["tournament"]["total_days"]
