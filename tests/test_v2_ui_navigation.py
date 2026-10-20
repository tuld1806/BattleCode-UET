"""Unit tests for UI navigation and template overhaul."""

import pytest
from fastapi.testclient import TestClient

from server.database import init_db
from server.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_navbar_does_not_contain_global_leaderboard():
    """Verify navbar focuses on Sảnh Game and Bracket without standalone global leaderboard."""
    res = client.get("/lobby")
    assert res.status_code == 200
    html = res.text
    # Should not have nav link to standalone "Bảng Xếp Hạng" in navbar
    assert 'href="/" class="nav-link">Bảng Xếp Hạng' not in html
    assert 'href="/" class="">Bảng Xếp Hạng' not in html


def test_game_detail_renders_4_tabs():
    """Verify game detail page contains all 4 tabs: Rules/Upload, Friendly, Leaderboard, Tournaments."""
    res = client.get("/games/rps-chess")
    assert res.status_code == 200
    html = res.text
    assert "tab-rules" in html or "Hướng Dẫn & Nộp Bot" in html
    assert "tab-friendly" in html or "Đấu Giao Hữu" in html
    assert "tab-leaderboard" in html or "Bảng Xếp Hạng" in html
    assert "tab-tournaments" in html or "Giải Đấu" in html


def test_bracket_page_has_no_back_to_leaderboard_or_admin_btn():
    """Verify bracket page removed outdated buttons."""
    res = client.get("/bracket")
    assert res.status_code == 200
    html = res.text
    assert "⬅ Bảng xếp hạng" not in html
    assert "Quản trị Admin" not in html
