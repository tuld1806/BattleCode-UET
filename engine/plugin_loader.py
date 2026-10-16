"""Plugin Loader and Security Validator for Multi-Game Plugins.

This module validates game plugin zip packages, enforces strict ZipSlip path
traversal defense, scans all embedded Python files using the sandbox AST security
engine (74 forbidden patterns), and dynamically loads concrete GameEngine subclasses
using Python's importlib machinery.
"""

from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
from typing import Any
import zipfile
import yaml

from engine.base import GameEngine
from engine.sandbox import (
    ALLOWED_MODULES,
    FORBIDDEN_BUILTINS,
    FORBIDDEN_DUNDERS,
    FORBIDDEN_MODULES,
    SecurityVisitor,
)


class PluginSecurityError(Exception):
    """Raised when a plugin violates security policies (ZipSlip or AST rules)."""
    pass


class PluginValidationError(Exception):
    """Raised when a plugin is missing mandatory files or valid specifications."""
    pass


class PluginSecurityVisitor(SecurityVisitor):
    """AST Security visitor for game plugins, extending sandbox rules with engine.base and abc."""

    ALLOWED_PLUGIN_ENGINE_SUBMODULES = frozenset({"engine", "engine.base", "engine.game"})
    ALLOWED_PLUGIN_EXTRA_MODULES = frozenset({"abc", "typing", "copy", "math", "random"})

    def _check_module_name(self, module_name: str, lineno: int) -> None:
        root_module = module_name.split(".")[0]
        if root_module in FORBIDDEN_MODULES:
            self.errors.append(
                f"Forbidden import '{module_name}' at line {lineno}: "
                f"'{root_module}' is disallowed for security reasons."
            )
            return

        if root_module == "engine":
            if module_name not in self.ALLOWED_PLUGIN_ENGINE_SUBMODULES:
                self.errors.append(
                    f"Unauthorized engine submodule import '{module_name}' at line {lineno}."
                )
            return

        if root_module in self.ALLOWED_PLUGIN_EXTRA_MODULES or root_module in ALLOWED_MODULES:
            return

        super()._check_module_name(module_name, lineno)


def validate_plugin_python_code(code_str: str) -> tuple[bool, str | None]:
    """Validate a plugin Python source string against security rules."""
    try:
        tree = ast.parse(code_str)
    except SyntaxError as exc:
        return False, f"Syntax error at line {exc.lineno}: {exc.msg}"
    except Exception as exc:
        return False, f"Failed to parse source code: {exc}"

    visitor = PluginSecurityVisitor()
    visitor.visit(tree)
    if visitor.errors:
        return False, visitor.errors[0]
    return True, None


def validate_plugin_zip(zip_path: str | Path) -> dict[str, Any]:
    """Inspect and validate a plugin zip archive for structure and security.

    Args:
        zip_path: Path to the uploaded zip file.

    Returns:
        Parsed configuration dictionary from config.yaml.

    Raises:
        PluginSecurityError: If path traversal or forbidden AST patterns are detected.
        PluginValidationError: If required files (engine.py, config.yaml) or schema are missing.
    """
    path = Path(zip_path).resolve()
    if not path.is_file():
        raise PluginValidationError(f"Plugin archive not found: {path}")

    try:
        with zipfile.ZipFile(path, "r") as zf:
            members = zf.infolist()
            filenames = [m.filename for m in members]

            # 1. Check for ZipSlip path traversal vulnerability
            for m in members:
                raw_name = m.filename.replace("\\", "/")
                parts = Path(raw_name).parts
                if ".." in parts or raw_name.startswith("/") or os.path.isabs(raw_name):
                    raise PluginSecurityError(f"Path traversal detected in zip member: {m.filename}")

            # 2. Check for mandatory files: engine.py and config.yaml
            engine_member = next((m for m in members if m.filename == "engine.py" or m.filename.endswith("/engine.py")), None)
            config_member = next((m for m in members if m.filename == "config.yaml" or m.filename.endswith("/config.yaml")), None)

            if engine_member is None:
                raise PluginValidationError("Missing mandatory plugin file: engine.py")
            if config_member is None:
                raise PluginValidationError("Missing mandatory plugin file: config.yaml")

            # 3. Scan all Python source files in the zip with the 74-pattern AST validator
            for m in members:
                if m.filename.endswith(".py") and not m.is_dir():
                    try:
                        code_bytes = zf.read(m)
                        code_str = code_bytes.decode("utf-8")
                    except Exception as err:
                        raise PluginSecurityError(f"Failed to read Python file {m.filename}: {err}") from err

                    ok, err_msg = validate_plugin_python_code(code_str)
                    if not ok:
                        raise PluginSecurityError(
                            f"Forbidden AST pattern in plugin file '{m.filename}': {err_msg}"
                        )


            # 4. Parse and validate config.yaml
            try:
                config_content = zf.read(config_member).decode("utf-8")
                config_data = yaml.safe_load(config_content)
            except Exception as err:
                raise PluginValidationError(f"Invalid YAML in config.yaml: {err}") from err

            if not isinstance(config_data, dict):
                raise PluginValidationError("config.yaml root must be a mapping dictionary")

            if "slug" not in config_data or not str(config_data["slug"]).strip():
                raise PluginValidationError("config.yaml missing required field: 'slug'")

            return config_data

    except zipfile.BadZipFile as err:
        raise PluginValidationError(f"Invalid zip archive: {err}") from err


def unpack_plugin(zip_path: str | Path, target_parent_dir: str | Path) -> Path:
    """Safely unpack a validated plugin zip into the target directory.

    Args:
        zip_path: Path to the validated zip file.
        target_parent_dir: Parent directory (e.g., 'games/').

    Returns:
        Path to the unpacked plugin directory.
    """
    config_data = validate_plugin_zip(zip_path)
    slug = config_data["slug"]
    dest_dir = (Path(target_parent_dir) / slug).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Secure path extraction preventing traversal
            member_path = Path(member.filename.replace("\\", "/"))
            target_file = (dest_dir / member_path).resolve()

            # Ensure resolved path is strictly within dest_dir
            if not str(target_file).startswith(str(dest_dir)):
                raise PluginSecurityError(f"Path traversal detected during extraction: {member.filename}")

            if member.is_dir():
                target_file.mkdir(parents=True, exist_ok=True)
            else:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target_file, "wb") as dst:
                    dst.write(src.read())

    return dest_dir


def load_plugin_engine(plugin_dir: str | Path) -> GameEngine:
    """Dynamically load and instantiate the GameEngine subclass from an unpacked plugin.

    Args:
        plugin_dir: Directory containing unpacked plugin files including engine.py.

    Returns:
        Instantiated GameEngine object.

    Raises:
        PluginValidationError: If engine.py is missing or does not define a concrete GameEngine subclass.
    """
    plugin_path = Path(plugin_dir).resolve()
    engine_file = plugin_path / "engine.py"
    if not engine_file.is_file():
        raise PluginValidationError(f"Missing engine.py in plugin directory: {plugin_path}")

    module_name = f"game_plugin_{plugin_path.name}_{abs(hash(str(plugin_path)))}"
    spec = importlib.util.spec_from_file_location(module_name, str(engine_file))
    if spec is None or spec.loader is None:
        raise PluginValidationError(f"Failed to load spec for {engine_file}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as err:
        raise PluginValidationError(f"Error executing engine.py: {err}") from err

    # Find concrete subclass of GameEngine
    engine_class = None
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, GameEngine)
            and attr is not GameEngine
        ):
            engine_class = attr
            break

    if engine_class is None:
        raise PluginValidationError("No concrete GameEngine subclass found in engine.py")

    try:
        instance = engine_class()
    except Exception as err:
        raise PluginValidationError(f"Failed to instantiate GameEngine subclass {engine_class.__name__}: {err}") from err

    return instance
