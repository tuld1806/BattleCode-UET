# Multi-Game Engine & Plugin System (Track A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Transform the single-game RPS Chess 9x9 execution layer into a generic multi-game tournament platform engine with abstract `GameEngine` interface, plugin loader with AST security scanner, updated database schemas (`Game`, `GameProfile`, `Tournament`, `TournamentEnrollment`), idempotent migration script, and refactored subprocess match runner.

**Architecture:** Define abstract `GameEngine` base class in `engine/base.py`. Package RPS Chess as the first standard plugin in `games/rps_chess/` wrapping the read-only `engine/game.py`. Update SQLAlchemy models in `server/models.py` with multi-game tables and per-game profiles while removing global Elo from `User`. Refactor `engine/runner.py` to be game-agnostic by injecting `GameEngine`. Implement secure `engine/plugin_loader.py` enforcing ZipSlip protection and 74-rule AST scanning on all `.py` files inside plugin packages before dynamic `importlib` loading. Provide an idempotent database migration script in `scripts/migrate_multi_game.py`.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (SQLite WAL), PyYAML, AST, zipfile, importlib, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-multi-game-platform-design.md`
**Team Workstream:** `docs/TEAM_WORKSTREAMS.md`

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies. Pure Python standard library + FastAPI + SQLAlchemy + PyYAML + pytest.
- Single-Admin Invariant: Admin account (`is_admin=True`) must never have `GameProfile` entries.
- Ranh giới file sở hữu (Hard Boundaries):
  - Track A owns: `engine/base.py`, `engine/plugin_loader.py`, `engine/runner.py`, `games/rps_chess/*`, `server/models.py`, `scripts/migrate_multi_game.py`, `tests/test_plugin_loader.py`, `tests/test_engine_base.py`, `tests/test_database.py`, `tests/test_runner.py`, `tests/test_queue.py`.
  - Strictly READ-ONLY: `engine/game.py` and `engine/sandbox.py`.
  - Track B/C files untouched: `server/game_registry.py`, `server/tournament.py`, `web/templates/*`.
- All code comments and docstrings in clear English.
- Worktree isolation: Execute inside `.worktrees/feature/multi-game-engine`.
- Full test suite regression guarantee: `pytest -v` 100% PASS on the worktree at completion.

## Review Focus
1. Malicious plugin upload attempting ZipSlip path traversal (`../../evil.py`) — must be rejected and raise security error before unpacking.
2. Malicious Python code in plugin zip (`import os`, `subprocess`, reflection exploits) — must be caught and rejected by AST scanner before execution.
3. Incomplete plugin zip missing `engine.py` or `config.yaml` or missing concrete `GameEngine` subclass — must fail validation with a clean descriptive error.
4. Idempotent migration script executed multiple times — must not duplicate `Game` (slug='rps-chess'), `GameProfile`, or corrupt existing records.
5. `GameEngine` tiebreaker and check_winner handling in `engine/runner.py` — must correctly interpret winner and win reasons without crashing the runner loop.

---

### Task 1: Verify & Finalize GameEngine Abstract Interface (Task A1)

**Files:**
- Create/Verify: `engine/base.py`
- Test: `tests/test_engine_base.py`

**Interfaces:**
- Produces: `engine.base.GameEngine` abstract base class with methods:
  - `get_initial_state(player1_id: int, player2_id: int) -> dict[str, Any]`
  - `get_player_view(state: dict[str, Any], player_id: int) -> dict[str, Any]`
  - `apply_action(state: dict[str, Any], player_id: int, action: Any) -> dict[str, Any]`
  - `check_winner(state: dict[str, Any]) -> tuple[int | None, str]`
  - `is_action_valid(state: dict[str, Any], player_id: int, action: Any) -> bool`
  - `get_max_turns() -> int`
  - `score_for_tiebreak(state: dict[str, Any], player_id: int) -> float`

- [x] **Step 1: Write the failing/extended test in `tests/test_engine_base.py`**

Verify interface coverage for all abstract methods and edge cases:
```python
import pytest
from engine.base import GameEngine

def test_abstract_methods_raise_not_implemented():
    class IncompleteEngine(GameEngine):
        pass

    with pytest.raises(TypeError):
        IncompleteEngine()
```

- [x] **Step 2: Run test to verify behavior**

Run: `pytest tests/test_engine_base.py -v`
Expected: PASS (verifying existing implementation meets spec contract).

- [x] **Step 3: Verify `engine/base.py` matches Section 4.2 of Spec**

Confirm `engine/base.py` has full type annotations and clear English docstrings for all 7 abstract methods.

- [x] **Step 4: Commit**

```bash
git add engine/base.py tests/test_engine_base.py
git commit -m "feat(engine): verify and finalize GameEngine abstract interface (Task A1)"
```

---

### Task 2: Multi-Game Database Schema in `server/models.py` (Task A3)

**Files:**
- Modify: `server/models.py`
- Modify: `tests/test_database.py`

**Interfaces:**
- Consumes: `server.database.Base`
- Produces:
  - `server.models.Game`: `id`, `slug`, `display_name`, `description_md`, `plugin_path`, `config_json`, `icon_path`, `is_active`, `created_at`
  - `server.models.GameProfile`: `id`, `user_id`, `game_id`, `elo`, `wins`, `losses`, `draws`, `UniqueConstraint('user_id', 'game_id')`
  - `server.models.Tournament`: `id`, `game_id`, `name`, `status`, `ffa_start_time`, `ffa_end_time`, `ffa_day_count`, `bracket_top_n`, `elo_multiplier`, `enrollment_open`, `created_at`
  - `server.models.TournamentEnrollment`: `id`, `tournament_id`, `user_id`, `bot_id`, `enrolled_at`, `UniqueConstraint('tournament_id', 'user_id')`
  - Updated `Match`: adds `game_id: Mapped[Optional[int]]`, `tournament_id: Mapped[Optional[int]]`
  - Updated `Bot`: adds `game_id: Mapped[int]`
  - Updated `User`: adds `game_profiles` relationship, removes column definitions for `elo`, `wins`, `losses`, `draws`, but maintains `@hybrid_property` getters/setters delegating to `game_profile` (game_id=1) for smooth inter-track transition.

- [x] **Step 1: Write the failing tests in `tests/test_database.py`**

```python
def test_new_multi_game_models_creation(tmp_path):
    """Verify creation and relationships of Game, GameProfile, Tournament, and TournamentEnrollment."""
    from server.database import init_db, get_db
    from server.models import Game, GameProfile, Tournament, TournamentEnrollment, User, Bot, Match

    init_db()
    db = next(get_db())
    try:
        # Create game
        game = Game(
            slug="rps-chess",
            display_name="RPS Chess 9x9",
            description_md="Classic RPS Chess rules",
            plugin_path="games/rps_chess",
            config_json='{"max_turns": 200}',
            is_active=True,
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        assert game.id is not None
        assert game.slug == "rps-chess"

        # Create user & profile
        user = User(username="bob", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        profile = GameProfile(user_id=user.id, game_id=game.id, elo=1250, wins=1, losses=0, draws=0)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        assert profile.id is not None
        assert profile.elo == 1250

        # Create tournament & enrollment
        tournament = Tournament(
            game_id=game.id,
            name="Fall Cup",
            status="open",
            ffa_start_time="19:00",
            ffa_end_time="21:00",
            ffa_day_count=7,
            bracket_top_n=8,
            elo_multiplier=1.5,
            enrollment_open=True,
        )
        db.add(tournament)
        db.commit()
        db.refresh(tournament)
        assert tournament.id is not None

        bot = Bot(user_id=user.id, game_id=game.id, filename="bot.py", filepath="bots/bot.py")
        db.add(bot)
        db.commit()
        db.refresh(bot)

        enrollment = TournamentEnrollment(
            tournament_id=tournament.id,
            user_id=user.id,
            bot_id=bot.id,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        assert enrollment.id is not None
    finally:
        db.close()
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py::test_new_multi_game_models_creation -v`
Expected: FAIL with `ImportError: cannot import name 'Game' from 'server.models'`

- [x] **Step 3: Implement new models in `server/models.py`**

Define `Game`, `GameProfile`, `Tournament`, `TournamentEnrollment`. Update `Match` and `Bot`. Add hybrid properties for `elo`, `wins`, `losses`, `draws` on `User` to ensure zero breakages across existing tests during Track A.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add server/models.py tests/test_database.py
git commit -m "feat(models): add Game, GameProfile, Tournament, TournamentEnrollment schemas (Task A3)"
```

---

### Task 3: Package RPS Chess Plugin & Config (Task A2)

**Files:**
- Create: `games/rps_chess/engine.py`
- Create: `games/rps_chess/config.yaml`
- Create: `games/rps_chess/bosses/novice_bot.py`
- Create: `games/rps_chess/bosses/rusher_bot.py`
- Create: `games/rps_chess/bosses/sentinel_bot.py`
- Create: `games/rps_chess/bosses/tactician_bot.py`
- Create: `games/rps_chess/bosses/apex_bot.py`
- Create: `tests/test_rps_chess_plugin.py`

**Interfaces:**
- Consumes: `engine.base.GameEngine`, `engine.game.GameState`, `engine.game.create_initial_board`
- Produces: `games.rps_chess.engine.RPSChessEngine` (subclassing `GameEngine`)

- [x] **Step 1: Write the failing test in `tests/test_rps_chess_plugin.py`**

```python
import pytest
from games.rps_chess.engine import RPSChessEngine

def test_rps_chess_engine_lifecycle():
    engine = RPSChessEngine()
    assert engine.get_max_turns() == 200
    state = engine.get_initial_state(1, 2)
    assert state["turn"] == 1
    assert "board" in state
    
    # Check valid moves
    valid = engine.is_action_valid(state, 1, ((0, 0), (1, 0)))
    assert isinstance(valid, bool)
    
    # Apply action
    new_state = engine.apply_action(state, 1, ((0, 0), (1, 0)))
    assert new_state["turn"] == 2
    
    # Check winner
    winner, reason = engine.check_winner(new_state)
    assert winner is None
    assert reason == ""
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rps_chess_plugin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'games'`

- [x] **Step 3: Implement `games/rps_chess/engine.py`, `config.yaml`, and copy bosses**

1. Create `games/__init__.py` and `games/rps_chess/__init__.py`.
2. Implement `RPSChessEngine` in `games/rps_chess/engine.py` wrapping `engine.game.GameState`.
3. Create `games/rps_chess/config.yaml` with config fields (slug, display_name, bot_interface, max_turns, timeout_ms).
4. Copy 5 boss bots from `server/bosses/` to `games/rps_chess/bosses/`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_rps_chess_plugin.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add games/ tests/test_rps_chess_plugin.py
git commit -m "feat(plugin): package RPS Chess 9x9 as first GameEngine plugin (Task A2)"
```

---

### Task 4: Refactor Subprocess Match Runner to Accept GameEngine (Task A5)

**Files:**
- Modify: `engine/runner.py`
- Modify: `tests/test_runner.py`

**Interfaces:**
- Consumes: `engine.base.GameEngine`, `games.rps_chess.engine.RPSChessEngine`
- Produces: `run_match(..., engine: GameEngine | None = None)`

- [x] **Step 1: Write failing test in `tests/test_runner.py`**

Test passing custom `GameEngine` instance to `run_match`:
```python
def test_run_match_with_explicit_game_engine():
    from games.rps_chess.engine import RPSChessEngine
    from engine.runner import run_match
    # Run simple match with explicit engine parameter
    engine = RPSChessEngine()
    result = run_match(
        bot1_path="starter_kit/bot_template.py",
        bot2_path="starter_kit/bot_template.py",
        max_turns=10,
        engine=engine,
    )
    assert "match_id" in result
    assert result["winner"] in [1, 2, None]
```

- [x] **Step 2: Run test to verify it fails or verifies signature**

Run: `pytest tests/test_runner.py::test_run_match_with_explicit_game_engine -v`

- [x] **Step 3: Refactor `engine/runner.py`**

Update `run_match()`:
- Add `engine: GameEngine | None = None` parameter.
- Default to `RPSChessEngine()` if `engine is None`.
- Use `engine.get_initial_state()`, `engine.apply_action()`, `engine.is_action_valid()`, and `engine.check_winner()`.
- Preserve isolated worker subprocess protocol, heartbeat, IPC communication, and replay formatting.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runner.py -v`
Expected: ALL PASS

- [x] **Step 5: Commit**

```bash
git add engine/runner.py tests/test_runner.py
git commit -m "refactor(runner): accept GameEngine instance for generic multi-game execution (Task A5)"
```

---

### Task 5: Plugin Loader with ZipSlip Guard & AST Security Scan (Task A6 & A8)

**Files:**
- Create: `engine/plugin_loader.py`
- Create: `tests/test_plugin_loader.py`

**Interfaces:**
- Consumes: `engine.base.GameEngine`, `engine.sandbox.validate_bot_ast`
- Produces:
  - `class PluginSecurityError(Exception)`
  - `class PluginValidationError(Exception)`
  - `validate_plugin_zip(zip_path: str | Path) -> dict[str, Any]`
  - `unpack_plugin(zip_path: str | Path, target_dir: str | Path) -> Path`
  - `load_plugin_engine(plugin_dir: str | Path) -> GameEngine`

- [x] **Step 1: Write failing tests in `tests/test_plugin_loader.py`**

Cover at least 5 security and validation cases:
1. Valid plugin zip unpacks and loads `GameEngine` instance.
2. Malicious Python file containing forbidden imports (`import os`, `subprocess`) raises `PluginSecurityError`.
3. Zip with missing `engine.py` or missing `config.yaml` raises `PluginValidationError`.
4. Zip with ZipSlip path traversal (`../../evil.py`) raises `PluginSecurityError`.
5. `engine.py` without concrete `GameEngine` subclass raises `PluginValidationError`.

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_plugin_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.plugin_loader'`

- [x] **Step 3: Implement `engine/plugin_loader.py`**

1. `validate_plugin_zip`: Inspect zip member list, verify required files exist, check for ZipSlip traversal (`..` or absolute paths).
2. Read all `.py` files from zip in-memory, run `validate_bot_ast(code)` from `engine.sandbox`. Raise `PluginSecurityError` on any violation.
3. Parse and validate `config.yaml` using `yaml.safe_load`.
4. `unpack_plugin`: Extract safely to target directory.
5. `load_plugin_engine`: Use `importlib.util.spec_from_file_location` to load module and instantiate subclass of `GameEngine`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_plugin_loader.py -v`
Expected: 5/5 PASS

- [x] **Step 5: Commit**

```bash
git add engine/plugin_loader.py tests/test_plugin_loader.py
git commit -m "feat(engine): add plugin_loader with ZipSlip protection and AST scan (Task A6 & A8)"
```

---

### Task 6: Idempotent Database Migration Script (Task A4)

**Files:**
- Create: `scripts/migrate_multi_game.py`
- Create: `tests/test_migration_multi_game.py`

**Interfaces:**
- Consumes: `server.database.engine`, `server.models`
- Produces: `migrate_multi_game(db_url: str | None = None) -> bool`

- [x] **Step 1: Write the failing test in `tests/test_migration_multi_game.py`**

```python
def test_migration_is_idempotent(tmp_path):
    """Verify running migration once and twice leaves database in consistent state."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"
    from scripts.migrate_multi_game import migrate_multi_game

    # Run 1
    assert migrate_multi_game(db_url) is True
    # Run 2 (idempotent)
    assert migrate_multi_game(db_url) is True
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_multi_game.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.migrate_multi_game'`

- [x] **Step 3: Implement `scripts/migrate_multi_game.py`**

1. Connect to SQLite database.
2. Create `game`, `game_profile`, `tournament`, `tournament_enrollment` tables if they don't exist.
3. Seed `game(id=1, slug='rps-chess', display_name='RPS Chess 9x9', ...)` if not present.
4. Backfill `bot.game_id = 1` and `match.game_id = 1` for existing records where `game_id IS NULL`.
5. Migrate non-admin users to `game_profile` with `game_id = 1` copying their existing Elo, wins, losses, draws if not already migrated.
6. Convert any existing `tournament_settings` to seed `tournament(id=1, game_id=1)`.
7. Ensure clean transaction commit.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_multi_game.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add scripts/migrate_multi_game.py tests/test_migration_multi_game.py
git commit -m "feat(migration): add idempotent multi-game database migration script (Task A4)"
```

---

### Task 7: Update Existing Test Suites & Final Full-Suite Verification (Task A7 & A9)

**Files:**
- Modify: `tests/test_queue.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_runner.py`

**Interfaces:**
- Consumes: All Track A deliverables
- Produces: 100% green test suite across all domains

- [x] **Step 1: Update `tests/test_queue.py` and `tests/test_database.py` for schema compatibility**

Ensure tests initializing bots and matches populate `game_id = 1` or utilize updated model defaults.

- [x] **Step 2: Run full regression test suite**

Run: `pytest -v`
Expected: 100% PASS (all existing 318+ tests + new tests green).

- [x] **Step 3: Commit**

```bash
git add tests/
git commit -m "test(regression): update queue and database tests for multi-game schema (Task A7 & A9)"
```

---

### Task 8: Documentation Sync for Teammates (Sync Point 0 Ready)

**Files:**
- Modify: `docs/TEAM_WORKSTREAMS.md`
- Modify: `TASKS.md`
- Modify: `docs/CONTEXT_RESUME.md`

- [x] **Step 1: Update `docs/TEAM_WORKSTREAMS.md`**

Mark Tasks A1 through A9 as complete `[x]`, note that Sync Point 0 (`engine/base.py` and `server/models.py`) is fully unlocked for Member B and C.

- [x] **Step 2: Update `TASKS.md`**

Mark Track A tasks complete under Milestone 11.

- [x] **Step 3: Update `docs/CONTEXT_RESUME.md` (SSOT)**

Document `GameEngine` abstract interface and multi-game database schema changes in accordance with the Continuous Feedback Loop Law.

- [x] **Step 4: Run documentation integrity tests**

Run: `pytest tests/test_documentation_integrity.py -v`
Expected: 100% PASS

- [x] **Step 5: Commit**

```bash
git add docs/ TASKS.md
git commit -m "docs: sync SSOT and TEAM_WORKSTREAMS for Track A completion"
```
