# Admin-Player Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strictly decouple the Admin role from player gameplay so that the Admin cannot participate in matches, bots, leaderboards, or tournament brackets, and normal users have zero admin buttons or privilege-elevation controls.

**Architecture:** Add authorization checks and database queries filtering out `User.is_admin == True` in `leaderboard.py`, `main.py`, `matches.py`, `bots.py`, and `admin.py`. In templates, remove unauthenticated/non-admin buttons (such as the admin button in `bracket.html`), show an Admin role badge in navbar instead of player Elo, and restrict player profile bot upload controls for admin accounts.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, Jinja2 templates, pytest.

**Spec:** Brainstorming consensus on 2026-10-17 and Section 10 update in `docs/CONTEXT_RESUME.md`.

## Global Constraints

- Single-Admin Invariant: Only one admin account exists (`is_admin=True`), strictly for platform operation.
- No-Node.js: All templates use Jinja2 + Vanilla HTML/CSS/JS.
- Admin Excluded From Play: Admin must never appear in `GET /api/leaderboard`, cannot upload bots, cannot challenge or be challenged, and cannot be seeded in bracket generation.
- Player UI Isolation: Players must not see admin buttons (e.g. `bracket.html`).
- Code Comments: All code comments and docstrings MUST be in clear, detailed English.

## Review Focus

1. Normal player accessing `/bracket` sees no "⚙ Quản trị Admin" button.
2. Admin account (`is_admin=True`) visiting `/api/leaderboard` is absent from rankings and rank calculations.
3. Admin attempting to POST to `/api/matches/challenge` receives HTTP 400 Bad Request.
4. Normal player attempting to challenge Admin receives HTTP 400 Bad Request.
5. Admin attempting to POST to `/api/bots/upload` receives HTTP 403 Forbidden.

---

### Task 1: Update Architecture Documentation (SSOT Law)

**Files:**
- Modify: `docs/CONTEXT_RESUME.md:152-167`
- Modify: `TASKS.md`

**Interfaces:**
- Consumes: Architectural consensus for Admin-Player role decoupling.
- Produces: Updated SSOT in `docs/CONTEXT_RESUME.md` (Section 10.4) and milestone tracking in `TASKS.md`.

- [ ] **Step 1: Update `docs/CONTEXT_RESUME.md` Section 10 with Rule 4 (Admin-Player Decoupling Invariant)**
- [ ] **Step 2: Append tracking task to `TASKS.md`**
- [ ] **Step 3: Verify document consistency**

---

### Task 2: Filter Admin Out of Leaderboard and Homepage Rankings

**Files:**
- Modify: `server/routes/leaderboard.py:20-45`
- Modify: `server/main.py:100-135`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `User.is_admin` attribute from `server.models.User`.
- Produces: `get_leaderboard` and `homepage` ranking list excluding all users where `is_admin == True`.

- [ ] **Step 1: Write failing test in `tests/test_api.py` asserting admin does not appear on leaderboard**
- [ ] **Step 2: Run test using `py -m pytest tests/test_api.py -k test_admin_excluded_from_leaderboard` to verify it fails**
- [ ] **Step 3: Update `server/routes/leaderboard.py` and `server/main.py` with `.filter(User.is_admin == False)`**
- [ ] **Step 4: Run test to verify it passes**

---

### Task 3: Restrict Match Challenge and Bot Upload for Admin Accounts

**Files:**
- Modify: `server/routes/matches.py:62-90`
- Modify: `server/routes/bots.py:19-35`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `current_user.is_admin` and `opponent.is_admin`.
- Produces: HTTP 400/403 errors when admin attempts to challenge/upload bot, or when opponent is admin.

- [ ] **Step 1: Write failing tests in `tests/test_api.py` for admin challenge rejection and bot upload rejection**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement guards in `server/routes/matches.py` and `server/routes/bots.py`**
- [ ] **Step 4: Run tests to verify they pass**

---

### Task 4: Exclude Admin From Bracket Generation

**Files:**
- Modify: `server/routes/admin.py:180-215`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `db.query(User).filter(User.is_admin == False)`.
- Produces: `trigger_bracket_generation` containing only non-admin players.

- [ ] **Step 1: Write failing test in `tests/test_api.py` for bracket generation ignoring admin**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Update `server/routes/admin.py` query to filter `User.is_admin == False`**
- [ ] **Step 4: Run test to verify it passes**

---

### Task 5: Clean Up Frontend UI Templates

**Files:**
- Modify: `web/templates/bracket.html:12-16`
- Modify: `web/templates/base.html:26-32`
- Modify: `web/templates/profile.html:12-60`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `current_user.is_admin` in Jinja2 template context.
- Produces: Clean UI without admin buttons for regular users, admin badge in navbar, admin notice in profile.

- [ ] **Step 1: Write failing test in `tests/test_web.py` checking `/bracket` HTML for regular user does not have admin link**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Modify `bracket.html`, `base.html`, and `profile.html`**
- [ ] **Step 4: Run test to verify it passes**

---

### Task 6: Full Verification Suite Run and Git Commit

- [ ] **Step 1: Run full test suite with `py -m pytest -v`**
- [ ] **Step 2: Git commit changes**
