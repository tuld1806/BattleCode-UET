# Multi-Game Platform: Track B & C Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all remaining deliverables for Track B (Playoff BO3 Runner, Excel-compatible Score Export, Admin Password Security) and Track C (Multi-game Lobby, Game Detail, Tournament Public Detail, Navbar & Profile Per-Game Integration).

**Architecture:**
1. **Track B Completion**: Add `server/bracket_runner.py` for automated Best-of-3 playoff round execution and winner promotion; implement `server/bracket_export.py` for UTF-8-SIG CSV generation; secure bracket generation behind admin password checks.
2. **Track C Completion**: Introduce `web/templates/lobby.html` as the new landing portal, `web/templates/game_detail.html` featuring a 3-tab layout (Rules, Leaderboard, Tournaments), public `web/templates/tournament_detail.html` for contestant viewing, and update `web/templates/base.html` and `web/templates/profile.html` with per-game profile cards.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (SQLite WAL), Jinja2, Vanilla JavaScript (Zero Node.js), CSS3 Design Tokens, standard library `csv`, pytest.

**Spec:** [`docs/superpowers/specs/2026-10-16-multi-game-platform-design.md`](../specs/2026-10-16-multi-game-platform-design.md) and [`docs/superpowers/specs/2026-10-18-bracket-execution-and-excel-export-design.md`](../specs/2026-10-18-bracket-execution-and-excel-export-design.md).

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies. Pure HTML5 / CSS3 / Vanilla JS.
- Code comments and docstrings strictly in clear English.
- Single-Admin Invariant (`is_admin=True` accounts cannot be seeded in brackets or receive tournament placement points).
- 100% test suite pass rate: `python -m pytest` must remain green across all tests before task completion.

## Review Focus
1. **Bracket Runner Walkover**: If a contestant in a matchup has not uploaded an active bot, the opposing contestant must be awarded an automatic 2-0 walkover win without throwing an exception.
2. **Side Alternation in BO3**: Game 1 must assign Player 1 as Red (P1) and Player 2 as Blue (P2); Game 2 must alternate sides (Player 2 as Red, Player 1 as Blue); Game 3 (if required) must decide sides deterministically.
3. **Excel UTF-8-SIG Encoding**: Exported CSV files must start with the byte sequence `\xef\xbb\xbf` (UTF-8 BOM) so Microsoft Excel opens Vietnamese text without mojibake/corrupted characters.
4. **Non-Admin Password Rejection**: Calling bracket generation endpoints with an invalid admin password must return HTTP 403 Forbidden without mutating database records.
5. **Backwards Compatibility**: Navigating to legacy routes (such as `/admin`, `/bracket`, `/api/leaderboard`) must continue to work cleanly or redirect smoothly.

---

## Part 1: Track B Finalization (Backend Playoff Engine & Export)

### Task B1: Admin Password Confirmation on Bracket Generation

**Files:**
- Modify: `server/routes/admin.py`
- Modify: `server/routes/admin_tournaments.py`
- Test: `tests/test_admin_security.py`
- Test: `tests/test_admin_tournament_routes.py`

**Interfaces:**
- Consumes: `current_admin.verify_password(password: str) -> bool`
- Produces: `AdminConfirmPasswordPayload(BaseModel): admin_password: str`

- [ ] **Step 1: Write failing tests in `tests/test_admin_security.py`**
  Assert that `POST /api/admin/bracket/generate` returns 403 when password is incorrect, and returns 200 when correct.
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_admin_security.py -k "password" -v`
- [ ] **Step 3: Implement `AdminConfirmPasswordPayload` and verification in `admin.py` and `admin_tournaments.py`**
  Verify `payload.admin_password` against `current_admin.verify_password()`.
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_admin_security.py tests/test_admin_tournament_routes.py -v`
- [ ] **Step 5: Commit changes**
  Run: `git commit -am "feat(admin): require admin password confirmation for bracket creation"`

---

### Task B2: Playoff Best-of-3 (BO3) Match Runner Engine

**Files:**
- Create: `server/bracket_runner.py`
- Test: `tests/test_bracket_runner.py`

**Interfaces:**
- Consumes: `GameRegistry`, `engine.runner.run_match_process`, `server.models.BracketMatch`
- Produces:
  - `run_bracket_round(db: Session, tournament_id: Optional[int] = None) -> Dict[str, Any]`
  - `run_all_bracket_rounds(db: Session, tournament_id: Optional[int] = None) -> Dict[str, Any]`

- [ ] **Step 1: Write unit tests in `tests/test_bracket_runner.py`**
  Cover:
  - Playing 1 round: updates `score_p1`, `score_p2`, `winner_id`, and `status="completed"`.
  - Walkover when 1 player has no bot (score 2-0).
  - Promotion of winners to the next stage (Quarter-Final -> Semi-Final -> Final).
  - `run_all_bracket_rounds` terminating when champion is crowned.
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_bracket_runner.py -v`
- [ ] **Step 3: Implement `server/bracket_runner.py`**
  Handle BO3 series with side swapping, save replays as `bracket_{match_id}_game_{1,2,3}`, and construct next-round pairings automatically when the current round concludes.
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_bracket_runner.py -v`
- [ ] **Step 5: Commit changes**
  Run: `git add server/bracket_runner.py tests/test_bracket_runner.py && git commit -m "feat(bracket): implement automated BO3 playoff runner service"`

---

### Task B3: Excel-Compatible (UTF-8-SIG) Score Export Service

**Files:**
- Create: `server/bracket_export.py`
- Test: `tests/test_bracket_export.py`

**Interfaces:**
- Consumes: `server.tournament.calculate_final_scores`, `server.models.Tournament`
- Produces: `generate_bracket_scores_csv(db: Session, tournament_id: Optional[int] = None) -> str`

- [ ] **Step 1: Write unit test in `tests/test_bracket_export.py`**
  Check that the output string starts with `\ufeff`, contains header columns `Thứ hạng,Tên kỳ thủ,Elo FFA,Điểm nhánh đấu,Tổng điểm,Kết quả`, and correctly formats rows.
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_bracket_export.py -v`
- [ ] **Step 3: Implement `server/bracket_export.py`**
  Use Python's `csv` module with `io.StringIO` and prepend `\ufeff` (UTF-8 BOM).
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_bracket_export.py -v`
- [ ] **Step 5: Commit changes**
  Run: `git add server/bracket_export.py tests/test_bracket_export.py && git commit -m "feat(export): implement Excel UTF-8-SIG bracket scores export"`

---

### Task B4: Register Admin Bracket Execution & Export Endpoints

**Files:**
- Modify: `server/routes/admin.py`
- Modify: `server/routes/admin_tournaments.py`
- Test: `tests/test_admin_tournament_routes.py`

**Interfaces:**
- Produces:
  - `POST /api/admin/bracket/run-round` & `POST /api/admin/bracket/run-all`
  - `POST /api/admin/tournaments/{id}/bracket/run-round` & `POST /api/admin/tournaments/{id}/bracket/run-all`
  - `GET /api/admin/bracket/export-scores` & `GET /api/admin/tournaments/{id}/export-scores`

- [ ] **Step 1: Write integration tests in `tests/test_admin_tournament_routes.py`**
  Test calling round runner and CSV export endpoints via FastAPI TestClient.
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_admin_tournament_routes.py -k "run_round or export" -v`
- [ ] **Step 3: Implement endpoints in `admin.py` and `admin_tournaments.py`**
  Wire handlers to `server.bracket_runner` and `server.bracket_export`. For CSV export, return `Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=..."})`.
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_admin_tournament_routes.py -v`
- [ ] **Step 5: Commit changes**
  Run: `git commit -am "feat(api): expose bracket execution and csv export routes"`

---

## Part 2: Track C (Frontend Multi-Game Experience)

### Task C1: Multi-Game Lobby Portal (`web/templates/lobby.html`)

**Files:**
- Create: `web/templates/lobby.html`
- Modify: `server/main.py:120-145`
- Test: `tests/test_web.py`

**Interfaces:**
- Route: `GET /` -> renders `lobby.html` when multiple games or explicit lobby view requested.
- Context: `games: List[Game]`, `current_user: Optional[User]`

- [ ] **Step 1: Write failing test in `tests/test_web.py`**
  Ensure `GET /` or `GET /lobby` returns HTTP 200 and contains game card elements with class `.game-card`.
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_web.py -k "test_lobby" -v`
- [ ] **Step 3: Build `web/templates/lobby.html` and update `main.py`**
  Design sleek dark-mode game cards with badge tags, game description, active player count, and "Play / Xem chi tiết" button pointing to `/games/{slug}`.
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_web.py -k "test_lobby" -v`
- [ ] **Step 5: Commit changes**
  Run: `git add web/templates/lobby.html server/main.py tests/test_web.py && git commit -m "feat(ui): add multi-game lobby template and route"`

---

### Task C2: Game Detail Page with 3-Tab Interface (`web/templates/game_detail.html`)

**Files:**
- Create: `web/templates/game_detail.html`
- Modify: `server/main.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Route: `GET /games/{slug}`
- Context: `game: Game`, `profiles: List[GameProfile]`, `tournaments: List[Tournament]`, `current_user: Optional[User]`

- [ ] **Step 1: Write test in `tests/test_web.py`**
  Ensure `GET /games/rps-chess` returns 200 and contains the 3 tabs: Rules (`#tab-rules`), Leaderboard (`#tab-leaderboard`), Tournaments (`#tab-tournaments`).
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_web.py -k "test_game_detail" -v`
- [ ] **Step 3: Build `web/templates/game_detail.html`**
  Implement responsive Vanilla JS tabs, per-game Elo leaderboard table, rules breakdown, and active tournaments with one-click enrollment.
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_web.py -k "test_game_detail" -v`
- [ ] **Step 5: Commit changes**
  Run: `git add web/templates/game_detail.html server/main.py tests/test_web.py && git commit -m "feat(ui): implement 3-tab game detail view"`

---

### Task C3: Public Tournament Detail Page (`web/templates/tournament_detail.html`)

**Files:**
- Create: `web/templates/tournament_detail.html` (public view for contestants)
- Modify: `server/main.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Route: `GET /games/{slug}/tournaments/{id}`
- Context: `tournament: Tournament`, `enrollments: List[TournamentEnrollment]`, `bracket_matches: List[BracketMatch]`, `current_user: Optional[User]`

- [ ] **Step 1: Write test in `tests/test_web.py`**
  Ensure `GET /games/rps-chess/tournaments/{id}` returns 200 with enrolled contestants table and bracket tree visualizer.
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_web.py -k "test_public_tournament_detail" -v`
- [ ] **Step 3: Create `web/templates/tournament_detail.html`**
  Include status badges, FFA portal schedule countdown clock, enrolled participants list, and live playoff bracket pairings.
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_web.py -k "test_public_tournament_detail" -v`
- [ ] **Step 5: Commit changes**
  Run: `git add web/templates/tournament_detail.html server/main.py tests/test_web.py && git commit -m "feat(ui): create public tournament detail template"`

---

### Task C4: Profile Per-Game Integration & Navbar Modernization

**Files:**
- Modify: `web/templates/base.html`
- Modify: `web/templates/profile.html`
- Modify: `web/static/js/rating_chart.js`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write test in `tests/test_web.py`**
  Check that user profile displays individual `GameProfile` cards with game names and specific Elos.
- [ ] **Step 2: Run test to verify failure**
  Run: `python -m pytest tests/test_web.py -k "test_profile_game_cards" -v`
- [ ] **Step 3: Update `base.html`, `profile.html`, and `rating_chart.js`**
  - In `base.html`: Add "Sảnh Game (Lobby)" link, dynamic games dropdown, and direct admin navigation.
  - In `profile.html`: Replace single Elo badge with a responsive grid of `GameProfile` cards showing wins/losses/draws per game.
  - In `rating_chart.js`: Accept `game_slug` parameter to dynamically fetch rating histories.
- [ ] **Step 4: Run test to verify pass**
  Run: `python -m pytest tests/test_web.py -v`
- [ ] **Step 5: Commit changes**
  Run: `git commit -am "feat(ui): update navbar, rating chart, and profile with multi-game support"`

---

## Part 3: Final Verification & Documentation Sync

### Task Integration: Full System Regression & Documentation Update

**Files:**
- Modify: `TASKS.md`
- Modify: `docs/TEAM_WORKSTREAMS.md`
- Modify: `docs/CONTEXT_RESUME.md`
- Test: All test suites (`python -m pytest`)

- [ ] **Step 1: Run complete test suite**
  Run: `python -m pytest -v`
  Ensure 100% PASS with 0 errors.
- [ ] **Step 2: Update `TASKS.md`**
  Check off completed tasks in Milestone 11 and playoff bracket execution sections.
- [ ] **Step 3: Update `docs/TEAM_WORKSTREAMS.md`**
  Update Track B & Track C checklists and completion status to 100%.
- [ ] **Step 4: Update `docs/CONTEXT_RESUME.md`**
  Maintain the Single Source of Truth by recording the new routes, templates, and tournament services.
- [ ] **Step 5: Commit documentation updates**
  Run: `git commit -am "docs: update master context resume and task trackers for track B and C completion"`
