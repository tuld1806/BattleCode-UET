# Track B Bugfix & Full Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the 8 failing tests across `test_admin_boss_deployment.py`, `test_api.py`, and `test_e2e.py`, ensure default game seeding for relational integrity (Foreign Key compliance), provide backward-compatible fallback for leaderboard ranking, verify 100% test suite pass (356/356 tests), and harmonize documentation across SSOT (`docs/CONTEXT_RESUME.md`, `TASKS.md`, `docs/TEAM_WORKSTREAMS.md`).

**Architecture:** 
1. Auto-seed default `rps-chess` game (`id=1`) inside `server/database.py:init_db()` whenever tables are created, ensuring all test fixtures and production runtimes satisfy SQLite foreign keys for `bots.game_id` and `game_profiles.game_id`.
2. Enhance `server/routes/games.py:get_game_leaderboard` with a fallback mechanism that ranks non-admin users based on `GameProfile`, filling with global `User.elo` for players who have not yet enrolled in a tournament, ensuring complete backward compatibility with legacy endpoints and test assertions.
3. Add explicit test coverage in `tests/test_api.py` verifying the HTTP 301 Permanent Redirect behavior on `/api/leaderboard` when `follow_redirects=False`.
4. Update SSOT documentation and task ledgers upon full suite pass.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (SQLite WAL), Starlette TestClient, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-multi-game-platform-design.md`
**Original Plan:** `docs/superpowers/plans/2026-10-17-multi-game-backend-track-b.md`

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies.
- Strict Single-Admin Invariant (`is_admin=True` must never have `GameProfile`, cannot enroll in tournaments, and cannot appear on leaderboards).
- Strict Foreign Key Integrity (`PRAGMA foreign_keys=ON`).
- Code comments and docstrings in clear English.
- Full test suite regression guarantee: `pytest -v` 100% PASS (356/356 tests).

## Review Focus
1. SQLite Foreign Key violations on `bots.game_id` and `game_profiles.game_id`: `init_db()` must ensure `Game(id=1, slug="rps-chess")` exists before any bot or profile insertion.
2. `GET /api/leaderboard` legacy redirect: Must return HTTP 301 Permanent Redirect to `/api/games/rps-chess/leaderboard` with valid `Location` header when `follow_redirects=False`, and return HTTP 200 with JSON list when followed.
3. Leaderboard query for users without `GameProfile`: Newly registered players or FFA contestants without tournament enrollment must still appear with baseline Elo (1200) without crashing with 404 or returning empty lists.
4. Boss deployment idempotence: Deploying or retracting bosses must update both `Bot.game_id` and `GameProfile(game_id)` without duplicating records or violating uniqueness constraints.
5. Documentation harmonization: `docs/CONTEXT_RESUME.md`, `TASKS.md`, and `docs/TEAM_WORKSTREAMS.md` must accurately reflect Track B completion.

---

### Task 1: Auto-Seed Default Game in `init_db()` for Foreign Key Integrity

**Files:**
- Modify: `server/database.py:50-58`
- Modify: `tests/test_admin_boss_deployment.py:16-35`
- Test: `tests/test_admin_boss_deployment.py`

**Interfaces:**
- Consumes: `server.models.Game`, `server.database.SessionLocal`
- Produces: `seed_default_game(db: Session) -> Game` helper callable by `init_db()` and fixtures.

- [ ] **Step 1: Write failing test in `tests/test_admin_boss_deployment.py`**

Confirm that `test_deploy_boss_creates_user_and_active_bot` reproduces SQLite FK error when DB is empty.
Run: `python -m pytest tests/test_admin_boss_deployment.py::test_deploy_boss_creates_user_and_active_bot -v`
Expected: FAIL with `IntegrityError: FOREIGN KEY constraint failed`

- [ ] **Step 2: Implement `seed_default_game` in `server/database.py` and invoke in `init_db()`**

In `server/database.py`:
```python
def seed_default_game(db_session: Optional[Session] = None) -> None:
    """Ensure baseline RPS Chess game (id=1, slug='rps-chess') exists."""
    from server.models import Game
    close_after = False
    if db_session is None:
        db = SessionLocal()
        close_after = True
    else:
        db = db_session

    try:
        existing = db.query(Game).filter(Game.slug == "rps-chess").first()
        if not existing:
            default_game = Game(
                id=1,
                slug="rps-chess",
                display_name="RPS Chess 9x9",
                description_md="Two players battle on a 9x9 grid using Rock, Paper, Scissors pieces.",
                plugin_path="games/rps_chess",
                config_json='{"max_turns": 200, "bot_interface": "python_function", "timeout_ms": 1000}',
                is_active=True,
            )
            db.add(default_game)
            db.commit()
    finally:
        if close_after:
            db.close()
```
Call `seed_default_game(SessionLocal(bind=eng))` inside `init_db(target_engine=None)` after `Base.metadata.create_all(bind=eng)`.

- [ ] **Step 3: Update `tests/test_admin_boss_deployment.py` fixture to call `init_db()`**

Ensure `setup_and_teardown_db` fixture uses `init_db()` so tables and the default game record are properly created.

- [ ] **Step 4: Run boss deployment tests to verify fix**

Run: `python -m pytest tests/test_admin_boss_deployment.py -v`
Expected: PASS (4/4 passed).

- [ ] **Step 5: Commit**

```bash
git add server/database.py tests/test_admin_boss_deployment.py
git commit -m "fix(db): auto-seed default rps-chess game in init_db to satisfy foreign key constraints"
```

---

### Task 2: Leaderboard Fallback & HTTP 301 Redirect Fix

**Files:**
- Modify: `server/routes/games.py:250-295`
- Modify: `tests/test_api.py:65-90`
- Test: `tests/test_api.py`, `tests/test_e2e.py`

**Interfaces:**
- Consumes: `server.models.User`, `GameProfile`, `Game`
- Produces: Robust `get_game_leaderboard` returning 200 with ranked users even when `GameProfile` rows are sparse.

- [ ] **Step 1: Write test for explicit 301 redirect in `tests/test_api.py`**

```python
def test_leaderboard_redirect_301():
    """Verify legacy GET /api/leaderboard issues a 301 Permanent Redirect to /api/games/rps-chess/leaderboard."""
    res = client.get("/api/leaderboard", follow_redirects=False)
    assert res.status_code == 301
    assert "/api/games/rps-chess/leaderboard" in res.headers.get("location", "")
```

- [ ] **Step 2: Run test to verify behavior**

Run: `python -m pytest tests/test_api.py::test_leaderboard_redirect_301 -v`
Expected: PASS (since redirect is already implemented) or FAIL if 404 occurs.

- [ ] **Step 3: Update `get_game_leaderboard` in `server/routes/games.py` with fallback**

1. If `game` is not found, check if `slug == "rps-chess"`. If so, auto-seed and reload `game` before failing.
2. Query `GameProfile` for `game.id`. If no profiles exist or fewer than total registered non-admin users, merge registered non-admin users using their `User.elo`, `wins`, `losses`, `draws`.
3. Ensure admin accounts (`User.is_admin == True`) are strictly filtered out under all circumstances.

- [ ] **Step 4: Run `test_api.py` and `test_e2e.py` to verify fix**

Run: `python -m pytest tests/test_api.py tests/test_e2e.py -v`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**

```bash
git add server/routes/games.py tests/test_api.py
git commit -m "fix(leaderboard): provide fallback for users without GameProfile and verify 301 redirect"
```

---

### Task 3: Full Regression Run & Documentation Harmonization (Task B14)

**Files:**
- Modify: `docs/TEAM_WORKSTREAMS.md`
- Modify: `TASKS.md`
- Modify: `docs/CONTEXT_RESUME.md`

- [ ] **Step 1: Run full test suite regression**

Run: `python -m pytest -v`
Expected: 100% PASS (356+ tests passing, 0 failed).

- [ ] **Step 2: Update `docs/TEAM_WORKSTREAMS.md`**
- Mark Track B items B1 through B14 as 100% COMPLETED.
- Record completed components: `GameRegistry`, `admin_games.py`, `admin_tournaments.py`, `games.py`, `GameProfile` Elo scoping, `queue.py` engine integration, `boss_manager.py` per-game deployment, and 301 leaderboard redirect.

- [ ] **Step 3: Update `TASKS.md`**
- Update Milestone 11 (Track B) status to `[x] COMPLETED`.
- Record verification evidence (command, test count, pass rate).

- [ ] **Step 4: Update `docs/CONTEXT_RESUME.md`**
- Harmonize Section 17 with implemented Multi-Game Backend architecture, database schemas, and API routes.

- [ ] **Step 5: Commit documentation updates**

```bash
git add docs/TEAM_WORKSTREAMS.md TASKS.md docs/CONTEXT_RESUME.md
git commit -m "docs: harmonize SSOT, TEAM_WORKSTREAMS, and TASKS for Track B completion"
```
