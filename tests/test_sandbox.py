"""Unit tests for the AST Security Validator and Sandbox (engine/sandbox.py)."""

import pytest
from pathlib import Path
from engine.sandbox import validate_bot_source, validate_bot_file


def test_valid_bot_source():
    """Verify that a compliant, standard bot source string passes validation."""
    valid_code = """
import math
import random

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(valid_code)
    assert is_valid is True
    assert error is None


def test_valid_bot_with_allowed_whitelist_imports():
    """Verify that all allowed whitelist modules can be imported and pass validation."""
    valid_code = """
import math
import random
import copy
import collections
from collections import defaultdict, deque
import heapq
import itertools
import typing
from typing import List, Tuple, Optional
import dataclasses
from dataclasses import dataclass
import engine
from engine.game import GameState, beats

@dataclass
class BotHelper:
    depth: int = 3

def get_move(board, my_player, history):
    moves = list(itertools.islice(range(10), 5))
    q = deque([1, 2, 3])
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(valid_code)
    assert is_valid is True
    assert error is None


def test_valid_bot_file(tmp_path: Path):
    """Verify that a valid bot file on disk passes file validation."""
    bot_file = tmp_path / "valid_bot.py"
    bot_file.write_text(
        """
import random

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
""",
        encoding="utf-8",
    )
    is_valid, error = validate_bot_file(str(bot_file))
    assert is_valid is True
    assert error is None


def test_syntax_error():
    """Verify that invalid Python syntax is rejected with a descriptive error."""
    bad_code = """
def get_move(board, my_player, history):
    return ((0, 0), (1, 0)
"""
    is_valid, error = validate_bot_source(bad_code)
    assert is_valid is False
    assert error is not None
    assert "syntax error" in error.lower()


def test_missing_get_move_function():
    """Verify that bot code without get_move is rejected."""
    bad_code = "x = 10"
    is_valid, error = validate_bot_source(bad_code)
    assert is_valid is False
    assert error is not None
    assert "get_move" in error


def test_get_move_not_top_level():
    """Verify that get_move defined inside a class or nested function is rejected."""
    nested_code = """
def wrapper():
    def get_move(board, my_player, history):
        return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(nested_code)
    assert is_valid is False
    assert "get_move" in error

    class_code = """
class MyBot:
    def get_move(self, board, my_player, history):
        return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(class_code)
    assert is_valid is False
    assert "get_move" in error


def test_get_move_as_variable():
    """Verify that defining get_move as a variable rather than a function is rejected."""
    bad_code = """
get_move = 42
"""
    is_valid, error = validate_bot_source(bad_code)
    assert is_valid is False
    assert "get_move" in error


@pytest.mark.parametrize(
    "module_name",
    [
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
    ],
)
def test_forbidden_imports_direct(module_name: str):
    """Verify that direct imports of forbidden modules are blocked."""
    code = f"""
import {module_name}

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert module_name in error


@pytest.mark.parametrize(
    "stmt,expected_kw",
    [
        ("from os import path", "os"),
        ("from sys import exit", "sys"),
        ("from subprocess import Popen", "subprocess"),
        ("from socket import socket", "socket"),
        ("from shutil import rmtree", "shutil"),
        ("from ctypes import c_int", "ctypes"),
        ("from threading import Thread", "threading"),
        ("from multiprocessing import Process", "multiprocessing"),
        ("from requests import get", "requests"),
        ("from urllib.request import urlopen", "urllib"),
        ("from builtins import open", "builtins"),
        ("from importlib import import_module", "importlib"),
    ],
)
def test_forbidden_imports_from(stmt: str, expected_kw: str):
    """Verify that 'from ... import ...' of forbidden modules is blocked."""
    code = f"""
{stmt}

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert expected_kw in error


def test_unauthorized_import_not_in_whitelist():
    """Verify that importing libraries outside the whitelist (e.g., numpy, pickle) is rejected."""
    numpy_code = """
import numpy as np

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(numpy_code)
    assert is_valid is False
    assert "numpy" in error

    pickle_code = """
import pickle

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(pickle_code)
    assert is_valid is False
    assert "pickle" in error


@pytest.mark.parametrize(
    "builtin_name",
    [
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
    ],
)
def test_forbidden_builtin_calls(builtin_name: str):
    """Verify that calls to prohibited built-ins are blocked."""
    code = f"""
def get_move(board, my_player, history):
    {builtin_name}()
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert builtin_name in error


@pytest.mark.parametrize(
    "builtin_name",
    [
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
    ],
)
def test_forbidden_builtin_references(builtin_name: str):
    """Verify that referencing or aliasing prohibited built-ins is blocked."""
    code = f"""
def get_move(board, my_player, history):
    func = {builtin_name}
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert builtin_name in error


@pytest.mark.parametrize(
    "dunder",
    [
        "__subclasses__",
        "__builtins__",
        "__globals__",
        "__code__",
        "__bases__",
    ],
)
def test_forbidden_dunder_attributes(dunder: str):
    """Verify that accessing prohibited dunder attributes is blocked."""
    code = f"""
def get_move(board, my_player, history):
    x = object.{dunder}
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert dunder in error


@pytest.mark.parametrize(
    "dunder",
    [
        "__subclasses__",
        "__builtins__",
        "__globals__",
        "__code__",
        "__bases__",
    ],
)
def test_forbidden_dunder_subscripts(dunder: str):
    """Verify that accessing prohibited dunder keys via subscript is blocked."""
    code = f"""
def get_move(board, my_player, history):
    d = {{}}
    x = d["{dunder}"]
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert dunder in error


def test_classic_sandbox_escape_subclasses():
    """Verify that classic subclasses-based sandbox escape is blocked."""
    code = """
def get_move(board, my_player, history):
    classes = ().__class__.__bases__[0].__subclasses__()
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert any(term in error for term in ["__bases__", "__subclasses__"])


def test_classic_sandbox_escape_func_globals():
    """Verify that func.__globals__ sandbox escape is blocked."""
    code = """
def get_move(board, my_player, history):
    g = get_move.__globals__
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert error is not None
    assert "__globals__" in error


def test_validate_bot_file_nonexistent():
    """Verify that validate_bot_file reports an error when the file does not exist."""
    is_valid, error = validate_bot_file("nonexistent_bot_file_12345.py")
    assert is_valid is False
    assert error is not None
    assert "not found" in error.lower()


def test_validate_bot_file_with_violations(tmp_path: Path):
    """Verify that validate_bot_file detects violations in a saved bot file."""
    bad_file = tmp_path / "bad_bot.py"
    bad_file.write_text(
        """
import os

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
""",
        encoding="utf-8",
    )
    is_valid, error = validate_bot_file(str(bad_file))
    assert is_valid is False
    assert error is not None
    assert "os" in error


def test_unauthorized_engine_submodule():
    """Verify that unauthorized submodules inside engine package are blocked."""
    code = """
import engine.runner

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "engine.runner" in error


def test_forbidden_alias_name():
    """Verify that aliasing an import to a forbidden name is blocked."""
    code = """
import math as open

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "open" in error


def test_relative_import_rejected():
    """Verify that relative imports are rejected."""
    code = """
from . import helper

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "Relative imports" in error


def test_from_import_forbidden_names():
    """Verify that importing forbidden built-ins or dunders via from-import is blocked."""
    code1 = """
from typing import open

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code1)
    assert is_valid is False
    assert "open" in error

    code2 = """
from typing import __builtins__

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code2)
    assert is_valid is False
    assert "__builtins__" in error

    code3 = """
from math import sqrt as eval

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code3)
    assert is_valid is False
    assert "eval" in error


def test_bare_dunder_reference():
    """Verify that referencing dunder identifiers directly as bare names is blocked."""
    code = """
def get_move(board, my_player, history):
    b = __builtins__
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "__builtins__" in error


def test_attribute_forbidden_builtin():
    """Verify that accessing forbidden built-ins as object attributes is blocked."""
    code = """
def get_move(board, my_player, history):
    f = object.open()
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "open" in error


def test_subscript_forbidden_builtin():
    """Verify that subscripting forbidden built-in names is blocked."""
    code = """
def get_move(board, my_player, history):
    d = {}
    f = d["open"]
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "open" in error


def test_reflection_getattr_forbidden():
    """Verify that dynamic reflection via getattr with prohibited targets is blocked."""
    code = """
def get_move(board, my_player, history):
    g = getattr(object, "__globals__")
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "__globals__" in error


def test_validate_bot_source_non_string():
    """Verify that non-string input to validate_bot_source is rejected gracefully."""
    is_valid, error = validate_bot_source(12345)  # type: ignore[arg-type]
    assert is_valid is False
    assert "must be a string" in error


def test_validate_bot_source_too_large():
    """Verify that source code exceeding maximum size is rejected."""
    huge_code = "x = 1\n" * 200_000
    is_valid, error = validate_bot_source(huge_code)
    assert is_valid is False
    assert "exceeds maximum allowed size" in error


def test_validate_bot_file_directory(tmp_path: Path):
    """Verify that passing a directory path to validate_bot_file fails gracefully."""
    is_valid, error = validate_bot_file(str(tmp_path))
    assert is_valid is False
    assert "not a regular file" in error


def test_validate_bot_file_decoding_error(tmp_path: Path):
    """Verify that non-UTF-8 binary files are rejected gracefully."""
    bin_file = tmp_path / "binary_bot.py"
    bin_file.write_bytes(b"\x80\x81\xff\xfe")
    is_valid, error = validate_bot_file(str(bin_file))
    assert is_valid is False
    assert "cannot be decoded as UTF-8 text" in error


def test_validate_bot_file_too_large(tmp_path: Path):
    """Verify that a bot file exceeding the maximum size limit is rejected."""
    huge_file = tmp_path / "huge_bot.py"
    huge_file.write_text("x = 1\n" * 200_000, encoding="utf-8")
    is_valid, error = validate_bot_file(str(huge_file))
    assert is_valid is False
    assert "exceeds maximum allowed size" in error


def test_from_import_forbidden_module_name():
    """Verify that importing a forbidden module name via from-import is blocked."""
    code = """
from collections import os

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(code)
    assert is_valid is False
    assert "os" in error


