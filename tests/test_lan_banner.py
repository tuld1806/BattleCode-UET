"""Tests for LAN IP detection and multi-machine connection banner."""

import io
import sys
from main import get_lan_ip, print_banner


def test_get_lan_ip_returns_valid_string():
    """Verify get_lan_ip returns a non-empty IPv4 string."""
    ip = get_lan_ip()
    assert isinstance(ip, str)
    parts = ip.split(".")
    assert len(parts) == 4
    for part in parts:
        assert part.isdigit()


def test_print_banner_includes_lan_url():
    """Verify banner outputs both local URL and LAN network URL for multi-machine access."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        print_banner("0.0.0.0", 8000)
        output = buf.getvalue()
        assert "LAN Network URL:" in output
        assert ":8000" in output
        assert "Local URL:" in output or "Web Interface:" in output
    finally:
        sys.stdout = old_stdout
