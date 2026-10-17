# Multi-Game Backend Server & Tournament System (Track B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the multi-game backend server and tournament orchestration layer (Track B) including `GameRegistry` singleton, admin plugin and tournament management APIs, player-facing game and tournament enrollment routes, per-game Elo calculations in `GameProfile`, enrollment-scoped queue processing, per-game boss deployment, and backward-compatible 301 redirects for legacy leaderboard routes.

**Architecture:** Build a thread-safe `GameRegistry` singleton in `server/game_registry.py` that utilizes `engine.plugin_loader` to validate, unpack, and dynamically load/cache `GameEngine` instances using `importlib`. Create RESTful admin routes in `server/routes/admin_games.py` and `server/routes/admin_tournaments.py` protected by strict `is_admin=True` session authorization. Expose player-facing APIs in `server/routes/games.py` allowing game exploration and tournament enrollment tied to active game-specific bots. Refactor `server/tournament.py`, `server/rating_history.py`, `server/queue.py`, and `server/boss_manager.py` to decouple rating updates from `User` and operate strictly on `GameProfile` per `(user_id, game_id)`. Maintain a 301 redirect shim on `/api/leaderboard` forwarding to `/api/games/rps-chess/leaderboard`.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (SQLite WAL), PyYAML, importlib, pytest, starlette TestClient.

**Spec:** `docs/superpowers/specs/2026-10-16-multi-game-platform-design.md`
**Team Workstream:** `docs/TEAM_WORKSTREAMS.md`

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies. Pure Python standard library + FastAPI + SQLAlchemy + PyYAML + pytest.
- Single-Admin Invariant: Admin account (`is_admin=True`) must never have `GameProfile` entries, cannot enroll in tournaments, and cannot appear in leaderboards or Elo charts.
- Admin-Player Decoupling Invariant: Admins cannot upload contestant bots, cannot challenge, and cannot be bracket contestants.
- Ranh giới file sở hữu (Hard Boundaries for Track B):
  - Track B owns: `server/game_registry.py`, `server/routes/admin_games.py`, `server/routes/admin_tournaments.py`, `server/routes/games.py`, `server/routes/leaderboard.py`, `server/routes/admin.py`, `server/tournament.py`, `server/rating_history.py`, `server/queue.py`, `server/boss_manager.py`, `tests/test_game_registry.py`, `tests/test_tournament_enrollment.py`, `tests/test_admin_game_routes.py`, `tests/test_tournament.py`, `tests/test_rating_history.py`.
  - Strictly READ-ONLY: `engine/base.py`, `engine/runner.py`, `engine/game.py`, `engine/sandbox.py`, `server/models.py`, `web/templates/*`.
- All code comments and docstrings in clear English.
- Worktree isolation: Execute inside `.worktrees/feature/multi-game-backend`.
- Full test suite regression guarantee: `pytest -v` 100% PASS on the worktree at completion.

## Review Focus
1. Malicious plugin upload via `POST /api/admin/games/upload` (ZipSlip traversal or forbidden AST): Must return HTTP 400 with error details without extracting files or persisting DB records.
2. Admin account attempting tournament enrollment: Must return HTTP 400/403 with error explaining admin cannot enroll under Admin-Player Decoupling Invariant.
3. Player enrolling without an active bot for `game_id`: Must return HTTP 400 detailing that an active bot for the specific game is required.
4. Invalid tournament status transitions (e.g. `open` -> `bracket` directly or modifying `finished`): Must return HTTP 400 with invalid transition error message.
5. Legacy `/api/leaderboard` requests: Must return HTTP 301 Permanent Redirect to `/api/games/rps-chess/leaderboard`.

---

### Task 1: GameRegistry Singleton Service & Cache (Task B1 & B10)

**Files:**
- Create: `server/game_registry.py`
- Create: `tests/test_game_registry.py`

**Interfaces:**
- Consumes:
  - `engine.base.GameEngine`
  - `engine.plugin_loader.validate_plugin_zip`, `unpack_plugin`, `load_plugin_engine`
  - `server.models.Game`
- Produces:
  - `server.game_registry.GameRegistry`:
    - `get_instance() -> GameRegistry` (singleton accessor)
    - `register_from_zip(zip_path: str | Path, db: Session) -> Game`
    - `load_engine(slug: str, db: Optional[Session] = None) -> GameEngine`
    - `list_active_games(db: Session) -> List[Game]`
    - `deactivate_game(slug: str, db: Session) -> None`
    - `activate_game(slug: str, db: Session) -> None`
    - `invalidate_cache(slug: Optional[str] = None) -> None`

- [ ] **Step 1: Write tests in `tests/test_game_registry.py`**

Cover at least 4 test cases:
1. `test_registry_load_engine_rps_chess`: loading `rps-chess` returns concrete `GameEngine` and subsequent calls hit cache.
2. `test_registry_cache_invalidation`: `invalidate_cache("rps-chess")` clears cached engine instance.
3. `test_registry_register_from_zip_and_deactivate`: registers mock game from zip, saves to DB, deactivates, verifies `list_active_games`.
4. `test_registry_load_engine_nonexistent_slug_raises`: non-existent slug raises `KeyError` or `ValueError`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_game_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.game_registry'`

- [ ] **Step 3: Implement `server/game_registry.py`**

Implement `GameRegistry` class with thread-safe singleton pattern using a module-level lock and `_instance`.
In `load_engine(slug: str, db: Optional[Session] = None)`:
- Check `self._engine_cache[slug]`. If present, return it.
- If not present, find game plugin path in `games/<slug>/` or query `Game` record in `db` to get `plugin_path`.
- Call `load_plugin_engine(plugin_path)` and cache the instance in `self._engine_cache[slug]`.
In `register_from_zip(zip_path: str | Path, db: Session) -> Game`:
- Validate zip and unpack via `unpack_plugin(zip_path, "games")`.
- Read `config.yaml` from unpacked dir.
- Create or update `Game(slug=..., display_name=..., description_md=..., plugin_path=..., config_json=..., is_active=True)`.
- Commit and return `Game`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_game_registry.py -v`
Expected: PASS (4/4 passed).

- [ ] **Step 5: Commit**

```bash
git add server/game_registry.py tests/test_game_registry.py
git commit -m "feat(server): implement GameRegistry singleton and engine caching (Task B1 & B10)"
```

---

### Task 2: Admin Game Management Routes (Task B2 & B12)

**Files:**
- Create: `server/routes/admin_games.py`
- Create: `tests/test_admin_game_routes.py`
- Modify: `server/main.py:60-75` (mount `admin_games.router`)

**Interfaces:**
- Consumes:
  - `server.game_registry.GameRegistry`
  - `server.routes.auth.get_current_admin` / session check
  - `server.models.Game`
- Produces:
  - `GET /api/admin/games` -> `List[Dict[str, Any]]`
  - `POST /api/admin/games/upload` -> `Dict[str, Any]` (UploadFile multipart)
  - `POST /api/admin/games/{slug}/toggle` -> `Dict[str, Any]`

- [ ] **Step 1: Write tests in `tests/test_admin_game_routes.py`**

Cover at least 4 test cases:
1. `test_admin_games_requires_admin_auth`: Unauthenticated returns 401/403, non-admin returns 403.
2. `test_admin_games_list_returns_all_games`: Returns active and inactive games.
3. `test_admin_games_upload_valid_plugin`: Uploading valid zip creates game and returns 200.
4. `test_admin_games_upload_malicious_plugin_rejected`: Uploading zip with AST violations or ZipSlip returns 400 with descriptive error.
5. `test_admin_games_toggle_active_status`: Toggle flips `is_active` boolean.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_game_routes.py -v`
Expected: FAIL with 404 or router not found.

- [ ] **Step 3: Implement `server/routes/admin_games.py` and mount in `server/main.py`**

Create `APIRouter(prefix="/admin/games", tags=["admin-games"])`.
Add endpoints:
- `GET ""`: List all games from DB (`id`, `slug`, `display_name`, `is_active`, `created_at`, `tournaments_count`).
- `POST "/upload"`: Accepts `file: UploadFile = File(...)`. Saves to a secure temporary location, validates via `GameRegistry.get_instance().register_from_zip(temp_path, db)`, catches `PluginSecurityError` or `PluginValidationError` and raises `HTTPException(status_code=400, detail=str(err))`.
- `POST "/{slug}/toggle"`: Queries game by slug, toggles `is_active = not is_active`, commits and returns updated status.
Mount `app.include_router(admin_games.router, prefix="/api")` in `server/main.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_game_routes.py -v`
Expected: PASS (5/5 passed).

- [ ] **Step 5: Commit**

```bash
git add server/routes/admin_games.py tests/test_admin_game_routes.py server/main.py
git commit -m "feat(api): add admin game plugin upload and toggle routes (Task B2 & B12)"
```

---

### Task 3: Admin Tournament Orchestration Routes (Task B3)

**Files:**
- Create: `server/routes/admin_tournaments.py`
- Create: `tests/test_admin_tournament_routes.py`
- Modify: `server/main.py:60-75` (mount `admin_tournaments.router`)

**Interfaces:**
- Consumes:
  - `server.models.Tournament`, `TournamentEnrollment`, `Game`, `GameProfile`
  - `server.tournament.generate_bracket`
  - `server.routes.auth.get_current_admin`
- Produces:
  - `GET /api/admin/tournaments` -> `List[Dict[str, Any]]`
  - `POST /api/admin/tournaments` -> `Dict[str, Any]` (Create new tournament)
  - `GET /api/admin/tournaments/{tournament_id}` -> `Dict[str, Any]` (Detail + enrollments)
  - `POST /api/admin/tournaments/{tournament_id}/set-status` -> `Dict[str, Any]` (`open` -> `running` -> `bracket` -> `finished`)
  - `POST /api/admin/tournaments/{tournament_id}/start-bracket` -> `Dict[str, Any]` (Seed top N players from `GameProfile`)

- [ ] **Step 1: Write tests in `tests/test_admin_tournament_routes.py`**

Cover:
1. `test_admin_tournaments_auth_guard`: 401/403 for non-admin.
2. `test_create_tournament_success_and_validation`: Valid creation with game_id, name, times, multiplier; rejection on nonexistent game_id.
3. `test_tournament_status_transition_valid_and_invalid`: Valid sequence `open` -> `running` -> `bracket` -> `finished`; invalid transition returns 400.
4. `test_start_bracket_seeds_enrolled_players`: Seeds Top N enrolled players based on `GameProfile.elo`, creates `BracketMatch` records.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_tournament_routes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `server/routes/admin_tournaments.py`**

Create `APIRouter(prefix="/admin/tournaments", tags=["admin-tournaments"])`.
State machine logic:
- Permitted transitions: `open` -> `running`, `running` -> `bracket`, `bracket` -> `finished`, `open` -> `finished` (cancelled).
- In `start-bracket`:
  - Query enrolled users in `TournamentEnrollment` for `tournament_id`.
  - Fetch their `GameProfile` for `tournament.game_id`. Filter out any admin users.
  - Sort descending by `GameProfile.elo`.
  - Slice to `tournament.bracket_top_n`.
  - Generate bracket pairings and insert into `BracketMatch` rows.
  - Set `tournament.status = "bracket"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_tournament_routes.py -v`
Expected: PASS (4/4 passed).

- [ ] **Step 5: Commit**

```bash
git add server/routes/admin_tournaments.py tests/test_admin_tournament_routes.py server/main.py
git commit -m "feat(api): implement admin tournament CRUD and status state machine (Task B3)"
```

---

### Task 4: Player-Facing Game & Tournament Enrollment Routes (Task B4 & B11)

**Files:**
- Create: `server/routes/games.py`
- Create: `tests/test_tournament_enrollment.py`
- Modify: `server/main.py:60-75` (mount `games.router`)

**Interfaces:**
- Consumes:
  - `server.models.Game`, `Tournament`, `TournamentEnrollment`, `GameProfile`, `Bot`, `User`
  - `server.routes.auth.get_current_user`
- Produces:
  - `GET /api/games` -> `List[Dict[str, Any]]`
  - `GET /api/games/{slug}` -> `Dict[str, Any]`
  - `GET /api/games/{slug}/tournaments` -> `List[Dict[str, Any]]`
  - `GET /api/games/{slug}/tournaments/{tournament_id}` -> `Dict[str, Any]`
  - `POST /api/games/{slug}/tournaments/{tournament_id}/enroll` -> `Dict[str, Any]`
  - `POST /api/games/{slug}/tournaments/{tournament_id}/unenroll` -> `Dict[str, Any]`

- [ ] **Step 1: Write tests in `tests/test_tournament_enrollment.py`**

Cover at least 5 test cases:
1. `test_list_games_and_game_detail`: Returns active games with rules metadata.
2. `test_player_enroll_success_creates_game_profile`: Enrolling with active bot succeeds and initializes `GameProfile(elo=1200)`.
3. `test_admin_cannot_enroll_in_tournament`: Admin returns 400/403.
4. `test_player_cannot_enroll_without_active_bot_for_game`: Returns 400 if user has no active bot for target `game_id`.
5. `test_player_unenroll_when_open_vs_running`: Unenroll succeeds when `status == "open"`; rejected when `status == "running"`.
6. `test_duplicate_enrollment_rejected`: Re-enrolling returns 400 ("Already enrolled").

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tournament_enrollment.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `server/routes/games.py`**

Create `APIRouter(prefix="/games", tags=["games"])`.
In `POST /{slug}/tournaments/{tournament_id}/enroll`:
- Verify `current_user.is_admin is False`. If admin, return 400 ("Admin accounts cannot enroll in tournaments").
- Verify tournament exists, belongs to `slug`, and `tournament.enrollment_open is True` and `tournament.status == "open"`.
- Check if already enrolled in `TournamentEnrollment`. If so, raise 400 ("Already enrolled in this tournament").
- Find active bot for user where `bot.game_id == game.id` and `bot.is_active is True`. If not found, raise 400 ("You must have an active bot uploaded for this game to enroll").
- Find or create `GameProfile(user_id=current_user.id, game_id=game.id, elo=1200, wins=0, losses=0, draws=0)`.
- Create `TournamentEnrollment(tournament_id=tournament.id, user_id=current_user.id, bot_id=active_bot.id)`. Commit and return status.
In `POST /{slug}/tournaments/{tournament_id}/unenroll`:
- If `tournament.status != "open"`, raise 400 ("Cannot un-enroll once tournament is running or finished").
- Delete enrollment record.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tournament_enrollment.py -v`
Expected: PASS (6/6 passed).

- [ ] **Step 5: Commit**

```bash
git add server/routes/games.py tests/test_tournament_enrollment.py server/main.py
git commit -m "feat(api): implement player game listing and tournament enrollment routes (Task B4 & B11)"
```

---

### Task 5: Per-Game Elo Calculations in Tournament Engine & Rating History (Task B5 & B6 [part] & B13)

**Files:**
- Modify: `server/tournament.py`
- Modify: `server/rating_history.py`
- Modify: `tests/test_tournament.py`
- Modify: `tests/test_rating_history.py`

**Interfaces:**
- Consumes:
  - `server.models.GameProfile`, `Match`, `User`
- Produces:
  - Updated `server.tournament.apply_elo_change` and `calculate_final_scores` supporting `GameProfile`
  - Updated `server.rating_history.get_user_rating_history(user_id: int, db: Session, game_id: Optional[int] = None, limit: int = 50)`
  - Updated `server.rating_history.get_top_teams_rating_history(db: Session, game_id: Optional[int] = None, top: int = 5, limit: int = 30)`

- [ ] **Step 1: Write extended tests in `tests/test_rating_history.py` and `tests/test_tournament.py`**

1. Verify `get_user_rating_history` filters matches by `game_id` and reads current Elo from `GameProfile`.
2. Verify `get_top_teams_rating_history` queries `GameProfile` for specified `game_id` (fallback to `game_id=1` if None), excluding admins.
3. Verify `calculate_final_scores` calculates scores per game using `GameProfile.elo`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rating_history.py -k "game_id" -v`
Expected: FAIL or parameter errors.

- [ ] **Step 3: Refactor `server/tournament.py` and `server/rating_history.py`**

In `server/rating_history.py`:
- Update `get_user_rating_history(user_id: int, db: Session, game_id: Optional[int] = None, limit: int = 50)`:
  - Target `effective_game_id = game_id or 1`.
  - Fetch `GameProfile` for `(user.id, effective_game_id)`. Current elo comes from `profile.elo` if present, fallback to 1200.
  - Filter `Match` query with `(Match.game_id == effective_game_id) | (Match.game_id.is_(None) if effective_game_id == 1 else False)`.
- Update `get_top_teams_rating_history(db: Session, game_id: Optional[int] = None, top: int = 5, limit: int = 30)`:
  - Target `effective_game_id = game_id or 1`.
  - Query `GameProfile` joined with `User`: `filter(User.is_admin == False, GameProfile.game_id == effective_game_id).order_by(GameProfile.elo.desc(), GameProfile.wins.desc())`.
  - Construct leaderboard payload with user metadata and per-game rating history.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tournament.py tests/test_rating_history.py -v`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**

```bash
git add server/tournament.py server/rating_history.py tests/test_tournament.py tests/test_rating_history.py
git commit -m "feat(tournament): scope Elo ratings and historical trajectory to GameProfile (Task B5 & B13)"
```

---

### Task 6: Enrolled FFA Queue, Per-Game Boss Deployment & Leaderboard 301 Redirect (Task B6, B7, B8, B9)

**Files:**
- Modify: `server/queue.py`
- Modify: `server/boss_manager.py`
- Modify: `server/routes/leaderboard.py`
- Modify: `server/routes/admin.py`
- Modify: `tests/test_queue.py`
- Modify: `tests/test_admin_boss_deployment.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes:
  - `server.game_registry.GameRegistry`
  - `server.models.GameProfile`, `TournamentEnrollment`, `Tournament`
- Produces:
  - `server.queue.execute_match_job` updates `GameProfile` and loads engine via `GameRegistry`.
  - `server.boss_manager.deploy_boss(db: Session, boss_slug: str, game_id: int = 1)` creates/updates `GameProfile` and attaches `bot.game_id = game_id`.
  - `GET /api/leaderboard` returns HTTP 301 redirect to `/api/games/rps-chess/leaderboard`.
  - `GET /api/games/{slug}/leaderboard` returns leaderboard for `slug`.
  - `GET /api/games/{slug}/rating-history` returns top rating history for `slug`.
  - `GET /api/games/{slug}/users/{user_id}/rating-history` returns user history for `slug`.

- [ ] **Step 1: Write tests in `tests/test_api.py` and `tests/test_queue.py`**

1. `test_leaderboard_redirect_301`: `GET /api/leaderboard` returns 301 to `/api/games/rps-chess/leaderboard`.
2. `test_game_scoped_leaderboard_endpoint`: `GET /api/games/rps-chess/leaderboard` returns list with `rank`, `username`, `elo`.
3. `test_queue_updates_game_profile_elo`: `execute_match_job` updates `GameProfile(user_id, match.game_id).elo`.
4. `test_boss_deploy_with_game_id`: `deploy_boss(db, "novice", game_id=1)` sets `GameProfile(user_id, 1)` and `bot.game_id=1`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_leaderboard_redirect_301 -v`
Expected: FAIL with status code mismatch (200 != 301).

- [ ] **Step 3: Implement changes in `queue.py`, `boss_manager.py`, `leaderboard.py`, and `admin.py`**

In `server/routes/leaderboard.py`:
- `GET ""` on `/api/leaderboard`:
  ```python
  from fastapi.responses import RedirectResponse
  return RedirectResponse(url="/api/games/rps-chess/leaderboard", status_code=status.HTTP_301_MOVED_PERMANENTLY)
  ```
- Add endpoints mounted under `/api/games/{slug}` or inside `server/routes/games.py`:
  - `GET /api/games/{slug}/leaderboard`: Query `GameProfile` for `game.id`, filter out admin, order by `elo DESC`.
  - `GET /api/games/{slug}/rating-history`: Call `get_top_teams_rating_history(db, game_id=game.id)`.
  - `GET /api/games/{slug}/users/{user_id}/rating-history`: Call `get_user_rating_history(user_id, db, game_id=game.id)`.
In `server/queue.py`:
- Fetch `game_id = match.game_id or 1`.
- Load engine: `engine = GameRegistry.get_instance().load_engine(game.slug)`.
- Pass `engine=engine` to `run_match`.
- In Elo update: find or create `GameProfile` for `player1` and `player2` with `game_id`. Update `profile.elo`, `wins`, `losses`, `draws`. Also mirror to `player.elo` for backward compatibility.
In `server/boss_manager.py`:
- Add `game_id: int = 1` parameter to `deploy_boss` and `get_all_bosses_status`.
- Set `bot.game_id = game_id`.
- Ensure `GameProfile(user_id=user.id, game_id=game_id, elo=boss_meta["default_elo"])` exists.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_queue.py tests/test_admin_boss_deployment.py tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/queue.py server/boss_manager.py server/routes/leaderboard.py server/routes/admin.py tests/test_queue.py tests/test_admin_boss_deployment.py tests/test_api.py
git commit -m "feat(server): wire queue execution to GameProfile, per-game bosses, and 301 leaderboard redirect (Task B6-B9)"
```

---

### Task 7: Documentation Harmonization & Full Test Suite Verification (Task B14)

**Files:**
- Modify: `docs/TEAM_WORKSTREAMS.md`
- Modify: `TASKS.md`
- Modify: `docs/CONTEXT_RESUME.md`

- [ ] **Step 1: Update `docs/TEAM_WORKSTREAMS.md`**
  - Reference this plan: `docs/superpowers/plans/2026-10-17-multi-game-backend-track-b.md`.
  - Mark Checklist items B1 - B14 as in-progress or completed.

- [ ] **Step 2: Update `TASKS.md`**
  - Update Milestone 11 Track B section with progress and plan link.

- [ ] **Step 3: Update `docs/CONTEXT_RESUME.md`**
  - Section 17: Update architectural details for `GameRegistry`, per-game tournament enrollment, and per-game Elo routes.

- [ ] **Step 4: Run full test suite regression**

Run: `pytest -v`
Expected: 100% PASS across all tests.

- [ ] **Step 5: Commit**

```bash
git add docs/TEAM_WORKSTREAMS.md TASKS.md docs/CONTEXT_RESUME.md
git commit -m "docs: harmonize SSOT, TEAM_WORKSTREAMS, and TASKS for Track B implementation plan"
```
