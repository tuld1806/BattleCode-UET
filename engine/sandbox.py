"""AST security validator and sandbox for user-submitted bot code.

This module inspects Python bot source code before execution to ensure
safety within the competition environment. It performs static analysis
using the Python AST (Abstract Syntax Tree) to reject dangerous operations,
such as unauthorized imports, forbidden built-in functions, reflection exploits,
and sandbox escapes.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

# Modules that are strictly forbidden from being imported
FORBIDDEN_MODULES: Final[frozenset[str]] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "shutil",
        "ctypes",
        "threading",
        "multiprocessing",
        "requests",
        "urllib",
        "builtins",
        "importlib",
    }
)

# Root modules that bots are explicitly allowed to import
ALLOWED_MODULES: Final[frozenset[str]] = frozenset(
    {
        "math",
        "random",
        "copy",
        "collections",
        "heapq",
        "itertools",
        "typing",
        "dataclasses",
        "engine",
    }
)

# Allowed submodules within the engine package
ALLOWED_ENGINE_SUBMODULES: Final[frozenset[str]] = frozenset(
    {
        "engine",
        "engine.game",
    }
)

# Prohibited built-in functions and identifiers
FORBIDDEN_BUILTINS: Final[frozenset[str]] = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
        "setattr",
        "delattr",
    }
)

# Prohibited dunder attributes and keys associated with sandbox exploits
FORBIDDEN_DUNDERS: Final[frozenset[str]] = frozenset(
    {
        "__subclasses__",
        "__builtins__",
        "__globals__",
        "__code__",
        "__bases__",
        "__base__",
        "__class__",
        "__mro__",
        "__dict__",
        "__subclasshook__",
        "__init_subclass__",
        "__reduce__",
        "__reduce_ex__",
    }
)

# Maximum permitted bot file size in bytes (1 megabyte)
MAX_BOT_CODE_SIZE_BYTES: Final[int] = 1_000_000


class SecurityVisitor(ast.NodeVisitor):
    """AST visitor that enforces security constraints on bot source code.

    Traverses the parsed syntax tree to inspect imports, function calls,
    identifier references, attribute lookups, subscripts, and dynamic reflection.
    """

    def __init__(self) -> None:
        """Initialize security visitor with an empty list of detected errors."""
        self.errors: list[str] = []

    def _check_module_name(self, module_name: str, lineno: int) -> None:
        """Check whether an imported module or submodule is authorized.

        Args:
            module_name: Full module path (e.g., 'math', 'os.path', 'engine.game').
            lineno: Source code line number where the import occurs.
        """
        root_module = module_name.split(".")[0]
        if root_module in FORBIDDEN_MODULES:
            self.errors.append(
                f"Forbidden import '{module_name}' at line {lineno}: "
                f"'{root_module}' is disallowed for security reasons."
            )
            return

        if root_module not in ALLOWED_MODULES:
            self.errors.append(
                f"Unauthorized import '{module_name}' at line {lineno}: "
                f"'{root_module}' is not in the allowed modules whitelist."
            )
            return

        if root_module == "engine" and module_name not in ALLOWED_ENGINE_SUBMODULES:
            self.errors.append(
                f"Unauthorized engine submodule import '{module_name}' at line {lineno}: "
                "only 'engine' and 'engine.game' are permitted."
            )

    def visit_Import(self, node: ast.Import) -> None:
        """Validate standard import statements (e.g., 'import math, os')."""
        for alias in node.names:
            self._check_module_name(alias.name, node.lineno)
            if alias.asname in FORBIDDEN_BUILTINS or alias.asname in FORBIDDEN_DUNDERS:
                self.errors.append(
                    f"Forbidden alias name '{alias.asname}' at line {node.lineno}."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Validate from-import statements (e.g., 'from sys import exit')."""
        if (node.level is not None and node.level > 0) or not node.module:
            self.errors.append(
                f"Relative imports are forbidden at line {node.lineno}."
            )
            return

        self._check_module_name(node.module, node.lineno)

        for alias in node.names:
            if alias.name in FORBIDDEN_MODULES:
                self.errors.append(
                    f"Forbidden import name '{alias.name}' at line {node.lineno}."
                )
            elif alias.name in FORBIDDEN_BUILTINS:
                self.errors.append(
                    f"Forbidden imported built-in '{alias.name}' at line {node.lineno}."
                )
            elif alias.name in FORBIDDEN_DUNDERS:
                self.errors.append(
                    f"Forbidden imported dunder '{alias.name}' at line {node.lineno}."
                )
            if alias.asname in FORBIDDEN_BUILTINS or alias.asname in FORBIDDEN_DUNDERS:
                self.errors.append(
                    f"Forbidden alias name '{alias.asname}' at line {node.lineno}."
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Validate identifier names to prevent references to forbidden built-ins and dunders."""
        if node.id in FORBIDDEN_BUILTINS:
            self.errors.append(
                f"Forbidden reference to built-in '{node.id}' at line {node.lineno}."
            )
        elif node.id in FORBIDDEN_DUNDERS:
            self.errors.append(
                f"Forbidden reference to dunder identifier '{node.id}' at line {node.lineno}."
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Validate attribute access to prevent dunder reflection and banned method calls."""
        if node.attr in FORBIDDEN_DUNDERS:
            self.errors.append(
                f"Forbidden attribute access '{node.attr}' at line {node.lineno}."
            )
        elif node.attr in FORBIDDEN_BUILTINS:
            self.errors.append(
                f"Forbidden attribute access to built-in '{node.attr}' at line {node.lineno}."
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Validate subscript access to block dictionary-based dunder exploits."""
        slice_node = node.slice
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            key = slice_node.value
            if key in FORBIDDEN_DUNDERS:
                self.errors.append(
                    f"Forbidden subscript access '{key}' at line {node.lineno}."
                )
            elif key in FORBIDDEN_BUILTINS:
                self.errors.append(
                    f"Forbidden subscript access '{key}' at line {node.lineno}."
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Inspect calls to prevent indirect reflection attempts via getattr/hasattr."""
        if isinstance(node.func, ast.Name) and node.func.id in ("getattr", "hasattr", "setattr", "delattr"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value in FORBIDDEN_DUNDERS or arg.value in FORBIDDEN_BUILTINS:
                        self.errors.append(
                            f"Forbidden reflection access to '{arg.value}' via '{node.func.id}' at line {node.lineno}."
                        )
        self.generic_visit(node)


def validate_bot_source(code: str) -> tuple[bool, str | None]:
    """Validate Python bot source code against security and structural rules.

    The validation ensures:
    1. The source code is valid Python syntax.
    2. The code defines a top-level function named 'get_move'.
    3. The code only imports modules from the approved whitelist.
    4. Prohibited modules, built-in calls, and dunder exploit attributes are rejected.

    Args:
        code: The Python source code string to validate.

    Returns:
        tuple[bool, str | None]: (True, None) if the code is valid and safe;
        otherwise (False, error_message).
    """
    if not isinstance(code, str):
        return False, "Bot source code must be a string."

    if len(code) > MAX_BOT_CODE_SIZE_BYTES:
        return False, f"Bot source code exceeds maximum allowed size ({MAX_BOT_CODE_SIZE_BYTES} bytes)."

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        line_info = f"line {exc.lineno}" if exc.lineno is not None else "unknown line"
        return False, f"Syntax error at {line_info}: {exc.msg}"
    except Exception as exc:
        return False, f"Failed to parse source code: {exc}"

    # Verify presence of top-level get_move function entrypoint
    has_get_move = any(
        isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == "get_move"
        for stmt in tree.body
    )
    if not has_get_move:
        return False, "Bot must define a top-level function 'def get_move(...)'."

    visitor = SecurityVisitor()
    visitor.visit(tree)

    if visitor.errors:
        return False, visitor.errors[0]

    return True, None


def validate_bot_file(file_path: str | Path) -> tuple[bool, str | None]:
    """Validate a Python bot file on disk.

    Reads the specified file and runs security and syntax validation.

    Args:
        file_path: File system path to the Python bot file.

    Returns:
        tuple[bool, str | None]: (True, None) if the file is valid and safe;
        otherwise (False, error_message).
    """
    path = Path(file_path)
    if not path.exists():
        return False, f"Bot file not found: {file_path}"
    if not path.is_file():
        return False, f"Path is not a regular file: {file_path}"

    try:
        file_size = path.stat().st_size
        if file_size > MAX_BOT_CODE_SIZE_BYTES:
            return False, f"Bot file exceeds maximum allowed size ({MAX_BOT_CODE_SIZE_BYTES} bytes): {file_path}"
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, f"Bot file cannot be decoded as UTF-8 text: {file_path}"
    except Exception as exc:
        return False, f"Failed to read bot file: {exc}"

    return validate_bot_source(source)
