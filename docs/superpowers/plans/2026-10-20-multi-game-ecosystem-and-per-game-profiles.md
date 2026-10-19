# Multi-Game Dynamic Ecosystem & Per-Game Player Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable automatic discovery and lobby display of all games located in the `games/` folder, streamline admin game plugin installation via zip uploads with automated tournament creation, enforce strictly isolated per-game Elo and leaderboard rankings, and upgrade the player profile page into a comprehensive multi-game command center.

**Architecture:** 
1. Database startup hook in `server/database.py` scans `games/` for valid plugin manifests (`config.yaml` + `engine.py`) and idempotently upserts `Game` and baseline `Tournament` records.
2. `server/routes/admin_games.py` and `server/game_registry.py` process `.zip` uploads, validate AST security, unpack into `games/<slug>`, invalidate engine caches, and register game entities.
3. Match outcomes and Elo adjustments are scoped strictly to `GameProfile` entities (`(user_id, game_id)` composite scope), ensuring rankings and rating histories remain 100% isolated per game.
4. `server/main.py` supplies the profile template with a unified list of all active games paired with the user's specific `GameProfile` statistics and active bot status for each game.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy (SQLite with WAL mode), PyYAML, Jinja2, Vanilla JavaScript, CSS3 Design Tokens (Zero-Node.js).

**Spec:** [`docs/superpowers/specs/2026-10-16-multi-game-platform-design.md`](../specs/2026-10-16-multi-game-platform-design.md)

## Global Constraints

- Zero-Node.js/npm dependencies: pure HTML5, CSS3 tokens, and Vanilla JS.
- Single-Admin invariant: The administrator account cannot participate in tournaments or matches as a player.
- Single Source of Truth (SSOT): All breaking schema, route, and architectural changes must be reflected in `docs/CONTEXT_RESUME.md`.
- Test-Driven Development: Every task must follow strict RED-GREEN-REFACTOR cycles with automated pytest verifications.
- Non-destructive idempotent migrations: Existing match and user records must never be lost during schema or game seeding updates.

## Review Focus

1. Auto-discovery must handle malformed subdirectories in `games/` (missing `config.yaml`, missing `engine.py`, or invalid YAML syntax) without crashing server startup.
2. Zip plugin upload must strictly prevent Zip Slip vulnerabilities and reject malicious AST nodes (e.g. `import os`, `subprocess`, `socket`).
3. Playing matches in Game A must never alter a user's `GameProfile.elo` or match counters in Game B.
4. Players without any matches or bot submissions in Game B must display a clean 1200 default baseline in Game B's profile card without null reference errors.
5. Deactivating a game via admin (`is_active=False`) must immediately hide it from the lobby while preserving historical `GameProfile` data in the database.

---

### Task 1: Automatic Discovery and Database Seeding for `games/` Subdirectories

**Files:**
- Modify: `server/database.py:53-125`
- Test: `tests/test_game_discovery.py`

**Interfaces:**
- Produces: `auto_discover_and_seed_games(db_session: Optional[Session] = None) -> List[Game]`
- Consumes: `games/*/config.yaml`, `games/*/engine.py`, `server.models.Game`, `server.models.Tournament`

- [ ] **Step 1: Write failing test in `tests/test_game_discovery.py`**

```python
def test_auto_discover_and_seed_games_registers_sample_game():
    """Verify that auto_discover_and_seed_games registers both rps-chess and sample-game."""
    from server.database import init_db, SessionLocal, auto_discover_and_seed_games
    from server.models import Game, Tournament
    
    init_db()
    db = SessionLocal()
    try:
        discovered = auto_discover_and_seed_games(db)
        slugs = {g.slug for g in discovered}
        assert "rps-chess" in slugs
        assert "sample-game" in slugs
        
        # Verify sample-game record fields
        sample = db.query(Game).filter(Game.slug == "sample-game").first()
        assert sample is not None
        assert sample.is_active is True
        assert sample.display_name == "Sample Game Plugin"
        
        # Verify a default tournament was seeded for sample-game
        t = db.query(Tournament).filter(Tournament.game_id == sample.id).first()
        assert t is not None
        assert t.name == "Sample Game Plugin Championship"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_game_discovery.py -v`
Expected: FAIL (cannot import `auto_discover_and_seed_games` or `sample-game` not in slugs)

- [ ] **Step 3: Implement `auto_discover_and_seed_games` in `server/database.py`**

Scan the `games/` directory. For every subdirectory containing both `config.yaml` and `engine.py`, parse the YAML manifest and upsert a `Game` record. If no `Tournament` exists for that `game_id`, create a default open championship tournament. Update `init_db()` to invoke `auto_discover_and_seed_games(db)`.

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/test_game_discovery.py -v`
Expected: PASS (1/1 passed)

- [ ] **Step 5: Commit changes**

```bash
git add server/database.py tests/test_game_discovery.py
git commit -m "feat(engine): auto-discover and seed games from filesystem on startup"
```

---

### Task 2: Multi-Game Lobby Automatic View Transition

**Files:**
- Modify: `server/main.py:116-172`
- Test: `tests/test_web.py`

**Interfaces:**
- Route: `GET /` and `GET /lobby`
- Consumes: `db.query(Game).filter(Game.is_active == True)`

- [ ] **Step 1: Write failing test in `tests/test_web.py`**

```python
def test_home_page_automatically_renders_lobby_when_multiple_games_active(client: TestClient):
    """When 2 or more games are active in DB, GET / must render lobby.html containing all game cards."""
    from server.models import Game
    db = SessionLocal()
    g1 = db.query(Game).filter(Game.slug == "rps-chess").first()
    if not g1:
        g1 = Game(slug="rps-chess", display_name="RPS Chess 9x9", is_active=True)
        db.add(g1)
    g2 = Game(slug="sample-game", display_name="Sample Game Plugin", is_active=True)
    db.add(g2)
    db.commit()
    db.close()

    res = client.get("/")
    assert res.status_code == 200
    assert "game-card" in res.text
    assert "RPS Chess 9x9" in res.text
    assert "Sample Game Plugin" in res.text
    assert "/games/rps-chess" in res.text
    assert "/games/sample-game" in res.text
```

- [ ] **Step 2: Run test to verify failure or behavior**

Run: `python -m pytest tests/test_web.py -k "test_home_page_automatically_renders_lobby" -v`
Expected: Verify assertion outcomes.

- [ ] **Step 3: Update `server/main.py` home_page handler**

Ensure `home_page` checks `len(games) > 1` and returns `lobby.html` with all active games, rendering modern badge metrics (active players count, active tournaments count, game rules preview).

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/test_web.py -k "test_home_page_automatically_renders_lobby" -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/main.py tests/test_web.py
git commit -m "feat(ui): ensure home page automatically renders multi-game lobby"
```

---

### Task 3: Admin Zip Upload Lifecycle & Automated Tournament Provisioning

**Files:**
- Modify: `server/game_registry.py:103-162`
- Modify: `server/routes/admin_games.py:41-85`
- Test: `tests/test_admin_game_routes.py`

**Interfaces:**
- Route: `POST /api/admin/games/upload`
- Consumes: Multipart ZIP archive containing `config.yaml`, `engine.py`, `rules.md`
- Produces: `Game` entity, `Tournament` entity, unpacked files in `games/<slug>`

- [ ] **Step 1: Write test in `tests/test_admin_game_routes.py`**

```python
def test_admin_upload_zip_creates_game_and_default_tournament(client: TestClient):
    """Uploading a game zip should unpack plugin, register Game, and provision a Tournament."""
    # Test zip creation with config.yaml, engine.py
    # Post to /api/admin/games/upload with admin cookie or header
    # Assert Game exists, Tournament exists, engine is immediately loadable via GameRegistry
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_admin_game_routes.py -k "test_admin_upload_zip_creates_game" -v`

- [ ] **Step 3: Implement automatic default tournament provisioning in `register_from_zip`**

In `server/game_registry.py:register_from_zip()`, after creating or updating the `Game` row:
Check if a `Tournament` exists for `game.id`. If not, provision a default `Tournament(game_id=game.id, name=f"{game.display_name} Championship", status="open", ffa_start_time="19:00", ffa_end_time="21:00", bracket_top_n=8)`.
Ensure `session_token` cookie authentication is properly accepted by `get_current_admin`.

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/test_admin_game_routes.py -v`
Expected: 100% PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/game_registry.py server/routes/admin_games.py tests/test_admin_game_routes.py
git commit -m "feat(admin): auto-provision default tournament upon game zip registration"
```

---

### Task 4: Strict Per-Game Elo and Leaderboard Isolation

**Files:**
- Modify: `server/tournament.py:100-240`
- Modify: `server/routes/games.py:120-210`
- Test: `tests/test_per_game_elo_isolation.py`

**Interfaces:**
- Consumes: `Match.game_id`, `GameProfile`
- Produces: Isolated Elo adjustments per game without cross-game contamination

- [ ] **Step 1: Write failing test in `tests/test_per_game_elo_isolation.py`**

```python
def test_per_game_elo_isolation_independent_ratings():
    """Verify that winning a match in Game 1 updates Game 1 Elo while Game 2 Elo remains untouched."""
    # 1. Create User Alice and Bob
    # 2. Create Game 1 (rps-chess) and Game 2 (sample-game)
    # 3. Create GameProfile for Alice in Game 1 (elo=1400) and Game 2 (elo=1200)
    # 4. Execute a completed match in Game 1 with Alice winning
    # 5. Assert Alice's Game 1 Elo increased (> 1400)
    # 6. Assert Alice's Game 2 Elo is strictly 1200 (unchanged)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_per_game_elo_isolation.py -v`
Expected: FAIL or verify existing isolation guarantees.

- [ ] **Step 3: Audit and enforce `game_id` constraints in `server/tournament.py` and `server/routes/games.py`**

Ensure `calculate_elo_delta`, `update_ratings_after_match`, and leaderboard queries strictly query and update `GameProfile` filtered by `GameProfile.game_id == match.game_id`.

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/test_per_game_elo_isolation.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/tournament.py server/routes/games.py tests/test_per_game_elo_isolation.py
git commit -m "feat(rating): guarantee strict per-game Elo and match statistics isolation"
```

---

### Task 5: Player Profile Multi-Game Command Center View

**Files:**
- Modify: `server/main.py:291-335`
- Modify: `web/templates/profile.html`
- Test: `tests/test_web.py`

**Interfaces:**
- Route: `GET /profile`
- Context:
  - `current_user: User`
  - `games_summary: List[Dict[str, Any]]` (contains game metadata, user's GameProfile, win_rate, rank, active bot for this game)
  - `user_bots: List[Bot]`
  - `user_matches: List[Match]`

- [ ] **Step 1: Write failing test in `tests/test_web.py`**

```python
def test_profile_page_multi_game_summary_cards(client: TestClient):
    """User profile must display a summary card for every active game with isolated stats."""
    # Create 2 games: rps-chess and sample-game
    # Create user with GameProfile in rps-chess (elo=1550, 10 wins) and sample-game (elo=1300, 2 wins)
    # Login user and GET /profile
    # Assert 'rps-chess' card shows 1550 Elo, 10 wins
    # Assert 'sample-game' card shows 1300 Elo, 2 wins
    # Assert active bot status badge for each game
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_web.py -k "test_profile_page_multi_game_summary_cards" -v`

- [ ] **Step 3: Update `profile_page` controller in `server/main.py`**

In `server/main.py:profile_page()`:
Fetch all active games. For each game, find the user's `GameProfile` (or construct a baseline object with `elo=1200, wins=0, losses=0, draws=0`). Find any active `Bot` uploaded by the user scoped to that `game_id`. Compute `win_rate`. Pass `games_summary` into the Jinja2 template context.

- [ ] **Step 4: Modernize `web/templates/profile.html`**

Update the template to render:
1. Top Section: User identity banner & Quick overview stats.
2. Multi-Game Scorecards Grid (`.game-profile-card`):
   - Game display name, slug tag, and status badge.
   - Current Elo rating with color badges (Gold > 1500, Cyan > 1300, Slate <= 1300).
   - Win/Loss/Draw pills and calculated Win Rate percentage.
   - Active Bot status: Shows submitted bot filename or "Chưa nộp bot" warning with a quick link to enroll.
3. Bot Management Drop Zone with Game selector dropdown.
4. Recent Match History table scoped with Game badges.

- [ ] **Step 5: Run test to verify pass**

Run: `python -m pytest tests/test_web.py -k "test_profile" -v`
Expected: 100% PASS

- [ ] **Step 6: Commit changes**

```bash
git add server/main.py web/templates/profile.html tests/test_web.py
git commit -m "feat(ui): upgrade player profile into comprehensive multi-game command center"
```

---

### Task 6: Full Regression Verification & Documentation Synchronization

**Files:**
- Modify: `docs/CONTEXT_RESUME.md`
- Modify: `TASKS.md`
- Test: All tests (`python -m pytest -v`)

- [ ] **Step 1: Run complete repository test suite**

Run: `python -m pytest -v`
Expected: 100% PASS across all 380+ tests with 0 failures.

- [ ] **Step 2: Verify documentation integrity**

Run: `python -m pytest tests/test_documentation_integrity.py -v`
Expected: 14/14 PASS.

- [ ] **Step 3: Update `docs/CONTEXT_RESUME.md` and `TASKS.md`**

Document the auto-discovery mechanism, the updated profile schema, and the admin zip lifecycle in the SSOT.

- [ ] **Step 4: Commit documentation updates**

```bash
git add docs/CONTEXT_RESUME.md TASKS.md
git commit -m "docs: document multi-game auto-discovery and per-game player profile architecture"
```
