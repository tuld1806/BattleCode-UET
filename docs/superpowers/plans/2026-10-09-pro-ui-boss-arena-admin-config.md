# Implementation Plan: Professional Minimalist UI, Admin Boss Arena, and Non-Tech Tournament Scheduling

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the web interface into a clean, minimalist developer-grade theme without decorative gradients, harden admin access control, implement five server-side benchmark boss bots for administrators, enable web-based tournament schedule configuration, and synchronize all documentation in a professional icon-free tone.

**Architecture:** The presentation layer is refactored into a neutral Slate/Charcoal palette with high-contrast legibility. Route-level and template-level authorization guards isolate administrative features. Five algorithmic boss bots reside exclusively in `server/bosses/`, deployable via administrative REST APIs, and tournament schedule parameters are persisted dynamically in the SQLite database to empower non-technical administrators.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, SQLite WAL, Jinja2, Vanilla JavaScript (ES2020+), CSS3 (Design Tokens), Pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-pro-ui-boss-arena-admin-config-design.md`

## Global Constraints

- Zero Node.js runtime or npm dependencies; all frontend assets are served natively via FastAPI.
- Code comments, docstrings, and commit messages must be in precise, idiomatic English.
- All project documentation must use an academic and professional tone free of decorative emojis or icons.
- Continuous Feedback Loop: All architectural alterations must be immediately reflected in `docs/CONTEXT_RESUME.md`.
- Incremental verification: Every task must commit isolated, working code verified via `pytest`.

## Review Focus

1. Unauthorized Admin Route Escape: Verify that manual URL entry to `/admin` by unauthenticated visitors or non-admin users cannot render administrative controls or data.
2. Boss Bot Sandbox Violations: Verify that all five algorithmic boss implementations strictly comply with `engine.sandbox.validate_bot_source` and execute safely within 1.0s.
3. Schedule Boundary Clamping: Verify that updating `start_time` and `end_time` to identical values or overnight spans (`22:00` to `02:00`) behaves predictably without unhandled exceptions.
4. Boss Deployment Duplication: Verify that repeatedly deploying or retracting a boss does not generate redundant user records or orphan active bots.
5. High-Resolution Replay Integrity: Verify that the redesigned minimalist visualizer renders all coordinates and piece movements accurately without visual clipping or transport stutter.

---

### Task 1: Professional Minimalist User Interface Redesign

**Files:**
- Modify: `web/static/css/style.css`
- Modify: `web/static/js/visualizer.js`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: Existing HTML template IDs and classes.
- Produces: CSS design tokens `--bg-main: #0d1117`, `--bg-surface: #161b22`, `--border-subtle: #30363d`, `--text-primary: #f0f6fc`, `--text-muted: #8b949e`.

- [ ] **Step 1: Write the failing test for minimalist design tokens**

In `tests/test_web.py`, add `test_minimalist_css_design_tokens_present` asserting that `style.css` defines the Slate/Charcoal palette tokens and no longer contains multi-stop radial gradient patterns.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py::test_minimalist_css_design_tokens_present -v`
Expected: FAIL due to missing tokens or legacy gradient rules.

- [ ] **Step 3: Refactor `web/static/css/style.css` and `web/static/js/visualizer.js`**

Replace multi-stop radial background gradients with solid `#0d1117`, replace neon box-shadows with subtle 1px `#30363d` borders, update table styles to crisp flat borders, and modernize the visualizer transport bar with clean neutral controls.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web.py -v`
Expected: PASS (all web tests green).

- [ ] **Step 5: Commit changes**

```bash
git add web/static/css/style.css web/static/js/visualizer.js tests/test_web.py
git commit -m "style(ui): redesign interface with professional minimalist charcoal palette"
```

---

### Task 2: Admin Access Control and Navigation Hardening

**Files:**
- Modify: `web/templates/base.html`
- Modify: `server/main.py`
- Test: `tests/test_admin_security.py`

**Interfaces:**
- Consumes: `current_user: User | None` from dependency injection.
- Produces: HTTP 303 redirect for unauthenticated `/admin` requests; HTTP 403 Forbidden for non-admin requests; conditional Admin navbar link.

- [ ] **Step 1: Write failing tests for Admin HTML route authorization**

In `tests/test_admin_security.py`, add `test_admin_page_unauthenticated_redirects_to_login` and `test_admin_page_non_admin_forbidden`, asserting that unauthenticated GET `/admin` returns a 303 redirect to `/login?next=/admin` and regular users receive a 403 status code.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_admin_security.py -k "admin_page" -v`
Expected: FAIL (currently `/admin` returns 200 for all callers).

- [ ] **Step 3: Implement authorization guards in `server/main.py` and `web/templates/base.html`**

Update `admin_page` in `server/main.py` to check `current_user` and redirect or raise `HTTPException(status_code=403)`. Wrap the Admin link in `web/templates/base.html` with `{% if current_user and current_user.is_admin %}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_admin_security.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add web/templates/base.html server/main.py tests/test_admin_security.py
git commit -m "feat(security): enforce strict route-level authorization and conditional navbar for admin"
```

---

### Task 3: Dynamic Web-Based Tournament Schedule Configuration

**Files:**
- Modify: `server/tournament.py`
- Modify: `server/routes/admin.py`
- Modify: `web/templates/admin.html`
- Test: `tests/test_admin_schedule.py`

**Interfaces:**
- Consumes: `TournamentSetting` records from SQLite.
- Produces: Dynamic evaluation in `is_ffa_portal_open(config, current_time_str, db_settings)`.

- [ ] **Step 1: Write failing tests for database-driven schedule evaluation**

Create `tests/test_admin_schedule.py` testing that updating `start_time`, `end_time`, and operating mode (`auto`, `true`, `false`) via API controls `is_ffa_portal_open` dynamically.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_admin_schedule.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement dynamic schedule handling in backend and admin template**

Update `server/tournament.py` to accept dynamic database settings. Extend `server/routes/admin.py` to save `start_time` and `end_time`. Update `web/templates/admin.html` with time picker inputs and asynchronous submission.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_schedule.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add server/tournament.py server/routes/admin.py web/templates/admin.html tests/test_admin_schedule.py
git commit -m "feat(tournament): add web-based schedule configuration for non-technical administrators"
```

---

### Task 4: Implementation of Five Server-Side Boss Benchmark Bots

**Files:**
- Create: `server/bosses/__init__.py`
- Create: `server/bosses/novice_bot.py`
- Create: `server/bosses/rusher_bot.py`
- Create: `server/bosses/sentinel_bot.py`
- Create: `server/bosses/tactician_bot.py`
- Create: `server/bosses/apex_bot.py`
- Test: `tests/test_boss_bots.py`

**Interfaces:**
- Consumes: Standard bot signature `get_move(board, my_player, history)`.
- Produces: Five distinct strategic tiers passing AST sandbox validation.

- [ ] **Step 1: Write failing tests for boss bots**

Create `tests/test_boss_bots.py` checking that all five bots exist, pass `validate_bot_source`, and return valid legal moves within 0.5s.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_boss_bots.py -v`
Expected: FAIL (files do not exist yet).

- [ ] **Step 3: Implement all five boss bot algorithms**

Implement `novice_bot.py` (Level 1: opportunistic random), `rusher_bot.py` (Level 2: Chebyshev goal rusher), `sentinel_bot.py` (Level 3: defensive perimeter and wipeout targeting), `tactician_bot.py` (Level 4: 2-ply Alpha-Beta Minimax), and `apex_bot.py` (Level 5: dynamic depth Minimax with piece baiting).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_boss_bots.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add server/bosses/ tests/test_boss_bots.py
git commit -m "feat(ai): implement five graduated benchmark boss bots in server repository"
```

---

### Task 5: Admin Boss Deployment API and Web Integration

**Files:**
- Create: `server/boss_manager.py`
- Modify: `server/routes/admin.py`
- Modify: `web/templates/admin.html`
- Test: `tests/test_admin_boss_deployment.py`

**Interfaces:**
- Consumes: Boss bot files from `server/bosses/`.
- Produces: `GET /api/admin/bosses` and `POST /api/admin/bosses/deploy`.

- [ ] **Step 1: Write failing integration test for boss deployment API**

Create `tests/test_admin_boss_deployment.py` testing deployment of Level 1 and Level 5 bosses, verifying that boss user accounts and active bot entries are created and listed on the leaderboard.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_admin_boss_deployment.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `server/boss_manager.py` and routes**

Implement logic to register boss user accounts with default ratings, store active bot records, and expose endpoints in `server/routes/admin.py`. Add Boss Arena management cards to `web/templates/admin.html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_boss_deployment.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add server/boss_manager.py server/routes/admin.py web/templates/admin.html tests/test_admin_boss_deployment.py
git commit -m "feat(admin): add boss deployment api and management controls in admin portal"
```

---

### Task 6: Documentation Harmonization (Clean Professional Tone Without Icons)

**Files:**
- Modify: `docs/CONTEXT_RESUME.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/BOT_GUIDE.md`
- Modify: `docs/ADMIN_GUIDE.md`
- Modify: `README.md`
- Modify: `TASKS.md`
- Test: `tests/test_documentation_integrity.py`

**Interfaces:**
- Consumes: Codebase architecture and API state.
- Produces: 100% synchronized, icon-free technical documentation.

- [ ] **Step 1: Write test for documentation consistency and absence of decorative icons**

Create `tests/test_documentation_integrity.py` ensuring that core markdown docs exist, contain updated section headers, and do not contain decorative emojis.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_documentation_integrity.py -v`
Expected: FAIL (legacy emojis present in docs).

- [ ] **Step 3: Update and sanitize all documentation files**

Update `docs/CONTEXT_RESUME.md`, `docs/ARCHITECTURE.md`, `docs/BOT_GUIDE.md`, and `docs/ADMIN_GUIDE.md` to reflect the new UI design tokens, Boss Arena, and non-tech schedule features in an academic tone without emojis.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_documentation_integrity.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add docs/ README.md TASKS.md tests/test_documentation_integrity.py
git commit -m "docs: synchronize architecture and competitor manuals in professional icon-free tone"
```

---

### Task 7: Comprehensive System Verification and Independent Simulation Session

**Files:**
- Test: Full test suite (`pytest -v`)
- Create: `scripts/independent_boss_arena_simulation.py`

**Interfaces:**
- Consumes: Entire application stack.
- Produces: End-to-end simulation results proving system stability.

- [ ] **Step 1: Create independent boss simulation script**

Create `scripts/independent_boss_arena_simulation.py` which executes automated round-robin matches between the five boss bots, records match replay files, and verifies leaderboard updates.

- [ ] **Step 2: Run the simulation script**

Run: `python scripts/independent_boss_arena_simulation.py`
Expected: Zero timeouts, zero crashes, valid JSON replays generated.

- [ ] **Step 3: Run the complete regression test suite**

Run: `pytest -v`
Expected: 100% of all tests passing (215+ tests green).

- [ ] **Step 4: Commit verification script**

```bash
git add scripts/independent_boss_arena_simulation.py
git commit -m "test(simulation): add independent end-to-end boss arena simulation script"
```
