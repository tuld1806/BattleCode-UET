"""Domain 2 Deep Testing: AST Sandbox hardening, evasion techniques, and attack vector audits."""

import pytest
from engine.sandbox import validate_bot_source, validate_bot_file


def test_escape_via_class_and_mro():
    """Verify that accessing __class__, __base__, or __mro__ is strictly blocked."""
    code = """
def get_move(board, my_player, history):
    cls = ().__class__
    base = cls.__base__
    mro = cls.__mro__
    return ((0, 0), (1, 1))
"""
    valid, err = validate_bot_source(code)
    assert valid is False
    assert err is not None
    assert "__class__" in err or "__base__" in err or "__mro__" in err


def test_escape_via_dict_dunder():
    """Verify that accessing __dict__ on any object is strictly blocked."""
    code = """
def get_move(board, my_player, history):
    d = board.__dict__
    return ((0, 0), (1, 1))
"""
    valid, err = validate_bot_source(code)
    assert valid is False
    assert err is not None
    assert "__dict__" in err


def test_banned_setattr_and_delattr_builtins():
    """Verify that calling setattr or delattr is rejected as forbidden built-in."""
    code = """
def get_move(board, my_player, history):
    setattr(board, "hack", 123)
    return ((0, 0), (1, 1))
"""
    valid, err = validate_bot_source(code)
    assert valid is False
    assert "setattr" in err


def test_ast_recursion_nesting_bomb():
    """Verify handling of deeply nested parenthesis or expressions without crashing the parser."""
    # 200 nested parens
    nested = "("*200 + "1" + ")"*200
    code = f"""
def get_move(board, my_player, history):
    x = {nested}
    return ((0, 0), (1, 1))
"""
    # Should either parse safely or reject cleanly, but NEVER raise unhandled exception
    try:
        valid, err = validate_bot_source(code)
        assert isinstance(valid, bool)
    except Exception as exc:
        pytest.fail(f"validate_bot_source crashed on nested AST: {exc}")


def test_byte_escaped_strings_do_not_bypass():
    """Verify that octal or hex escaped string literals cannot bypass dunder checks."""
    code = """
def get_move(board, my_player, history):
    # \\x5f\\x5fsubclasses\\x5f\\x5f is '__subclasses__'
    sub = getattr(object, "\\x5f\\x5fsubclasses\\x5f\\x5f")
    return ((0, 0), (1, 1))
"""
    valid, err = validate_bot_source(code)
    assert valid is False
    assert "__subclasses__" in err


def test_banned_fileio_builtins():
    """Verify that attempting to access FileIO or raw streams is blocked."""
    code = """
import io
def get_move(board, my_player, history):
    f = io.FileIO("test.txt")
    return ((0, 0), (1, 1))
"""
    valid, err = validate_bot_source(code)
    # io is not in the approved whitelist modules!
    assert valid is False
    assert "io" in err
