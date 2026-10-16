"""Tests for multi-game plugin loader, ZipSlip validation, AST scanning, and dynamic engine loading."""

import io
from pathlib import Path
import zipfile
import pytest

from engine.base import GameEngine
from engine.plugin_loader import (
    PluginSecurityError,
    PluginValidationError,
    load_plugin_engine,
    unpack_plugin,
    validate_plugin_zip,
)


def _create_zip(files: dict[str, str | bytes]) -> io.BytesIO:
    """Helper to create an in-memory zip archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if isinstance(content, str):
                zf.writestr(name, content.encode("utf-8"))
            else:
                zf.writestr(name, content)
    buf.seek(0)
    return buf


VALID_CONFIG = """slug: "test-game"
display_name: "Test Game"
bot_interface: "python_function"
max_turns: 100
"""

VALID_ENGINE_CODE = """from engine.base import GameEngine

class TestEngine(GameEngine):
    def get_initial_state(self, p1: int, p2: int) -> dict:
        return {"turn": 1}
    def get_player_view(self, state: dict, player_id: int) -> dict:
        return state
    def apply_action(self, state: dict, player_id: int, action: dict) -> dict:
        return {"turn": state["turn"] + 1}
    def check_winner(self, state: dict) -> tuple[int | None, str]:
        return None, ""
    def is_action_valid(self, state: dict, player_id: int, action: dict) -> bool:
        return True
    def get_max_turns(self) -> int:
        return 100
    def score_for_tiebreak(self, state: dict, player_id: int) -> float:
        return 0.0
"""


def test_valid_plugin_zip_validation_and_loading(tmp_path: Path):
    """Case 1: Valid plugin zip unpacks and dynamically instantiates GameEngine."""
    zip_bytes = _create_zip({
        "engine.py": VALID_ENGINE_CODE,
        "config.yaml": VALID_CONFIG,
    })
    zip_path = tmp_path / "valid_game.zip"
    zip_path.write_bytes(zip_bytes.getvalue())

    meta = validate_plugin_zip(zip_path)
    assert meta["slug"] == "test-game"
    assert meta["display_name"] == "Test Game"

    unpacked_dir = unpack_plugin(zip_path, tmp_path / "games")
    assert (unpacked_dir / "engine.py").exists()
    assert (unpacked_dir / "config.yaml").exists()

    engine_instance = load_plugin_engine(unpacked_dir)
    assert isinstance(engine_instance, GameEngine)
    assert engine_instance.get_max_turns() == 100


def test_malicious_plugin_rejected_by_ast_scan(tmp_path: Path):
    """Case 2: Malicious Python file containing forbidden imports is rejected by AST scanner."""
    malicious_code = """import os
from engine.base import GameEngine

class EvilEngine(GameEngine):
    def get_initial_state(self, p1, p2):
        os.system("echo evil")
        return {}
"""
    zip_bytes = _create_zip({
        "engine.py": malicious_code,
        "config.yaml": VALID_CONFIG,
    })
    zip_path = tmp_path / "evil.zip"
    zip_path.write_bytes(zip_bytes.getvalue())

    with pytest.raises(PluginSecurityError) as exc_info:
        validate_plugin_zip(zip_path)
    assert "Forbidden AST pattern" in str(exc_info.value) or "import" in str(exc_info.value).lower()


def test_missing_required_files_rejected(tmp_path: Path):
    """Case 3: Zip missing engine.py or config.yaml is rejected with PluginValidationError."""
    # Missing engine.py
    zip_bytes = _create_zip({"config.yaml": VALID_CONFIG})
    zip_path = tmp_path / "missing_engine.zip"
    zip_path.write_bytes(zip_bytes.getvalue())

    with pytest.raises(PluginValidationError) as exc_info:
        validate_plugin_zip(zip_path)
    assert "engine.py" in str(exc_info.value)

    # Missing config.yaml
    zip_bytes2 = _create_zip({"engine.py": VALID_ENGINE_CODE})
    zip_path2 = tmp_path / "missing_config.zip"
    zip_path2.write_bytes(zip_bytes2.getvalue())

    with pytest.raises(PluginValidationError) as exc_info2:
        validate_plugin_zip(zip_path2)
    assert "config.yaml" in str(exc_info2.value)


def test_zip_slip_path_traversal_rejected(tmp_path: Path):
    """Case 4: Zip with ZipSlip path traversal vulnerability is caught and rejected."""
    zip_bytes = _create_zip({
        "../../evil.py": "print('traversal')",
        "engine.py": VALID_ENGINE_CODE,
        "config.yaml": VALID_CONFIG,
    })
    zip_path = tmp_path / "zip_slip.zip"
    zip_path.write_bytes(zip_bytes.getvalue())

    with pytest.raises(PluginSecurityError) as exc_info:
        validate_plugin_zip(zip_path)
    assert "Path traversal" in str(exc_info.value) or "traversal" in str(exc_info.value).lower()


def test_engine_py_without_concrete_game_engine_rejected(tmp_path: Path):
    """Case 5: engine.py without a concrete subclass of GameEngine is rejected."""
    no_engine_code = """# Just helper functions, no GameEngine class
def helper():
    return 42
"""
    zip_bytes = _create_zip({
        "engine.py": no_engine_code,
        "config.yaml": VALID_CONFIG,
    })
    zip_path = tmp_path / "no_engine_class.zip"
    zip_path.write_bytes(zip_bytes.getvalue())

    unpacked_dir = unpack_plugin(zip_path, tmp_path / "games")
    with pytest.raises(PluginValidationError) as exc_info:
        load_plugin_engine(unpacked_dir)
    assert "GameEngine subclass" in str(exc_info.value)
