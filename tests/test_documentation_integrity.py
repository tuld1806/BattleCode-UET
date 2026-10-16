import re
from pathlib import Path
import pytest

CORE_DOCS = [
    "README.md",
    "TASKS.md",
    "docs/CONTEXT_RESUME.md",
    "docs/ARCHITECTURE.md",
    "docs/BOT_GUIDE.md",
    "docs/ADMIN_GUIDE.md",
]

# Regex pattern matching unicode decorative emojis and pictographs
EMOJI_PATTERN = re.compile(
    r"[\U0001F000-\U0001FAFF"  # Plane 1 symbols, emoticons, pictographs
    r"\u2600-\u26FF"          # Misc symbols (warning, gear, lightning, sword, etc.)
    r"\u2700-\u27BF"          # Dingbats (checkmarks, crosses, hands, etc.)
    r"\uFE00-\uFE0F]"         # Variation selectors
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_core_documentation_files_exist():
    """Verify all 6 authoritative documentation files exist at repository root and docs/."""
    for rel_path in CORE_DOCS:
        doc_path = REPO_ROOT / rel_path
        assert doc_path.is_file(), f"Required documentation file is missing: {rel_path}"


@pytest.mark.parametrize("rel_path", CORE_DOCS)
def test_no_decorative_emojis_in_documentation(rel_path: str):
    """Ensure documentation maintains a clean, academic, professional tone without emojis."""
    doc_path = REPO_ROOT / rel_path
    assert doc_path.is_file(), f"File does not exist: {rel_path}"
    content = doc_path.read_text(encoding="utf-8")
    matches = EMOJI_PATTERN.findall(content)
    assert not matches, (
        f"File {rel_path} contains decorative emojis/icons: "
        f"{[f'U+{ord(c):04X}' for c in set(matches)]}"
    )


def test_architecture_documentation_content():
    """Verify docs/ARCHITECTURE.md contains modern Boss Arena and UI tokens references."""
    arch_path = REPO_ROOT / "docs" / "ARCHITECTURE.md"
    content = arch_path.read_text(encoding="utf-8")
    assert "server/bosses" in content
    assert "boss_manager" in content
    assert "tokens" in content.lower() or "--color-" in content


def test_admin_guide_content():
    """Verify docs/ADMIN_GUIDE.md explains schedule controls and boss bots."""
    admin_path = REPO_ROOT / "docs" / "ADMIN_GUIDE.md"
    content = admin_path.read_text(encoding="utf-8")
    assert "start_time" in content
    assert "end_time" in content
    assert "boss" in content.lower()


def test_bot_guide_content():
    """Verify docs/BOT_GUIDE.md provides comprehensive competitor strategies and Minimax."""
    bot_path = REPO_ROOT / "docs" / "BOT_GUIDE.md"
    content = bot_path.read_text(encoding="utf-8")
    assert "heuristic" in content.lower()
    assert "minimax" in content.lower()


def test_context_resume_content():
    """Verify docs/CONTEXT_RESUME.md documents server bosses, schedule persistence, and theme."""
    cr_path = REPO_ROOT / "docs" / "CONTEXT_RESUME.md"
    content = cr_path.read_text(encoding="utf-8")
    assert "server/bosses" in content
    assert "TournamentSetting" in content
    assert "start_time" in content
    assert "end_time" in content
    assert "novice" in content.lower()
    assert "rusher" in content.lower()
    assert "sentinel" in content.lower()
    assert "tactician" in content.lower()
    assert "apex" in content.lower()


def test_tasks_milestone_8_content():
    """Verify TASKS.md documents Milestone 8 and associated subtasks."""
    tasks_path = REPO_ROOT / "TASKS.md"
    content = tasks_path.read_text(encoding="utf-8")
    assert "Milestone 8" in content
    assert "8.1" in content
    assert "8.6" in content


def test_context_resume_rating_history_content():
    """Verify docs/CONTEXT_RESUME.md documents Section 16 Rating History Visualizer."""
    cr_path = REPO_ROOT / "docs" / "CONTEXT_RESUME.md"
    content = cr_path.read_text(encoding="utf-8")
    assert "rating_history" in content
    assert "/rating-history" in content
    assert "RatingChart" in content


def test_tasks_milestone_10_content():
    """Verify TASKS.md documents Milestone 10 and subtasks 10.1 through 10.5."""
    tasks_path = REPO_ROOT / "TASKS.md"
    content = tasks_path.read_text(encoding="utf-8")
    assert "Milestone 10" in content
    assert "10.1" in content
    assert "10.2" in content
    assert "10.3" in content
    assert "10.4" in content
    assert "10.5" in content

