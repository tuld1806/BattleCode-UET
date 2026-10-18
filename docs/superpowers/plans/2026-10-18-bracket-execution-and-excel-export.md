# Playoff Bracket Password Confirmation, BO3 Execution & Excel Export Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement admin password verification for bracket generation, a Best-of-3 (BO3) automated playoff match runner that advances winners to the championship, and an Excel-compatible (UTF-8-SIG) score export endpoint with matching UI controls.

**Architecture:** 
1. Add `AdminConfirmPasswordPayload` pydantic model and integrate password verification into `POST /api/admin/bracket/generate` and `POST /api/admin/tournaments/{id}/start-bracket`.
2. Build `server/bracket_runner.py` service that executes BO3 playoff matches using active bots and `GameEngine`, alternates sides, records replays, updates `BracketMatch` records, and advances winners through Quarterfinals, Semifinals, and Finals.
3. Implement `server/bracket_export.py` generating RFC 4180 CSV with UTF-8 BOM (`utf-8-sig`) containing final composite scores ($0.5 \times \text{Normalized Elo} + 0.5 \times \text{Bracket Score}$) and stream it via FastAPI endpoints.
4. Enhance `web/templates/admin.html` and `web/templates/bracket.html` with password prompt modal, "Run Next Round / Run All" buttons, and "Export Excel (CSV)" download button.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (SQLite WAL), Jinja2, standard library `csv`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-bracket-execution-and-excel-export-design.md`

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies.
- Zero extra external package dependencies (use standard library `csv` with `utf-8-sig` for 100% Excel compatibility).
- Strict Single-Admin Invariant (`is_admin=True` accounts cannot be seeded in brackets or receive scores).
- Full test suite regression guarantee: `pytest -v` 100% PASS across all tests.

## Review Focus
1. Password Verification Security: An incorrect password must return HTTP 403 Forbidden without mutating existing bracket matches or tournament status.
2. BO3 Series Alternate Sides: Game 1 must have Player 1 as Red (P1) and Player 2 as Blue (P2); Game 2 must invert sides (Player 2 as Red, Player 1 as Blue) to ensure competitive fairness.
3. Walkover Handling: If a seeded contestant has no active bot uploaded, the opposing contestant must be awarded a 2-0 walkover win automatically.
4. Excel UTF-8 Compatibility: The exported CSV must begin with the byte sequence `\xef\xbb\xbf` (UTF-8 BOM) so Microsoft Excel opens it without character corruption.
5. Idempotent Round Advancement: Calling run round when all matches in that round are already completed must not duplicate matchups or throw exceptions.

---

### Task 1: Admin Password Confirmation on Bracket Generation

**Files:**
- Modify: `server/routes/admin.py:200-245`
- Modify: `server/routes/admin_tournaments.py:220-270`
- Modify: `web/templates/admin.html:95-115, 250-275`
- Test: `tests/test_admin_security.py`
- Test: `tests/test_admin_tournament_routes.py`

**Interfaces:**
- Consumes: `User.verify_password`, `get_current_admin`
- Produces: `AdminConfirmPasswordPayload(admin_password: str)`

- [ ] **Step 1: Write failing tests in `tests/test_admin_security.py`**

Cover 3 test cases:
1. `test_generate_bracket_requires_password_success`: Correct password returns 200 and generates bracket.
2. `test_generate_bracket_invalid_password_returns_403`: Wrong password returns 403 Forbidden and preserves DB state.
3. `test_generate_bracket_missing_password_returns_422`: Empty/missing payload returns 422.

Run: `python -m pytest tests/test_admin_security.py -k "password" -v`
Expected: FAIL with status code mismatch.

- [ ] **Step 2: Implement password verification in `server/routes/admin.py` and `server/routes/admin_tournaments.py`**

Define schema:
```python
from pydantic import BaseModel

class AdminConfirmPasswordPayload(BaseModel):
    admin_password: str
```
In `generate_bracket_endpoint`:
```python
if not current_admin.verify_password(payload.admin_password):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Mật khẩu quản trị viên không chính xác.",
    )
```
Apply the same guard to `start_bracket` in `server/routes/admin_tournaments.py`.

- [ ] **Step 3: Update `web/templates/admin.html` with password prompt UI**

Update `triggerBracketGeneration()` to prompt for the admin password or show an input modal before sending the POST request with `json: { admin_password: password }`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_admin_security.py tests/test_admin_tournament_routes.py -k "bracket" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/routes/admin.py server/routes/admin_tournaments.py web/templates/admin.html tests/test_admin_security.py tests/test_admin_tournament_routes.py
git commit -m "feat(admin): require admin password confirmation for bracket generation"
```

---

### Task 2: Best-of-3 (BO3) Playoff Bracket Runner

**Files:**
- Create: `server/bracket_runner.py`
- Modify: `server/routes/admin.py`
- Modify: `server/routes/admin_tournaments.py`
- Modify: `web/templates/admin.html`
- Modify: `web/templates/bracket.html`
- Create: `tests/test_bracket_runner.py`

**Interfaces:**
- Consumes: `BracketMatch`, `Bot`, `engine.runner.run_match`, `server.game_registry.GameRegistry`
- Produces:
  - `server.bracket_runner.run_bracket_match(bm: BracketMatch, db: Session, best_of: int = 3) -> BracketMatch`
  - `server.bracket_runner.advance_bracket_round(tournament_id: Optional[int], db: Session) -> Dict[str, Any]`
  - `POST /api/admin/bracket/run-round` -> `Dict[str, Any]`
  - `POST /api/admin/bracket/run-all` -> `Dict[str, Any]`

- [ ] **Step 1: Write tests in `tests/test_bracket_runner.py`**

Cover 4 test cases:
1. `test_run_bracket_match_bo3_alternating_sides`: Executes BO3 series, confirms `score_p1 + score_p2 >= 2`, sets `winner_id` and `status="completed"`.
2. `test_run_bracket_match_walkover_when_bot_missing`: Awards 2-0 win to player with active bot.
3. `test_advance_bracket_round_quarterfinals_to_semifinals`: Advances winners of 4 Quarterfinals matches to 2 Semifinals matches.
4. `test_run_all_bracket_rounds_to_finished`: Runs all rounds to completion, sets tournament status to `finished`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bracket_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.bracket_runner'`.

- [ ] **Step 3: Implement `server/bracket_runner.py`**

1. `run_bracket_match(bm, db, engine=None, best_of=3)`:
   - Queries active bots for `bm.player1_id` and `bm.player2_id`.
   - If either bot is missing, awards walkover (`2-0`).
   - Runs games sequentially up to `best_of` games (first to $\lceil \text{best\_of} / 2 \rceil = 2$ wins):
     - Game 1: P1 vs P2
     - Game 2: P2 vs P1
     - Game 3 (if 1-1): P1 vs P2
   - Saves replay for each game to `replays/bracket_{bm.id}_game_{g}.json`.
   - Sets `bm.score_p1`, `bm.score_p2`, `bm.winner_id`, and `bm.status = "completed"`.
2. `advance_bracket_round(tournament_id, db)`:
   - Finds current pending round matches. Runs each via `run_bracket_match`.
   - If Quarterfinals (4 matches completed) -> creates 2 Semifinals matches.
   - If Semifinals (2 matches completed) -> creates 1 Finals match.
   - If Finals (1 match completed) -> sets `tournament.status = "finished"`.

- [ ] **Step 4: Mount API routes in `server/routes/admin.py` and `server/routes/admin_tournaments.py`**

Add `POST /bracket/run-round` and `POST /bracket/run-all` protected by `get_current_admin`.

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_bracket_runner.py -v`
Expected: PASS (4/4 passed).

- [ ] **Step 6: Commit**

```bash
git add server/bracket_runner.py server/routes/admin.py server/routes/admin_tournaments.py tests/test_bracket_runner.py
git commit -m "feat(tournament): implement Best-of-3 playoff bracket runner and round advancement"
```

---

### Task 3: Excel-Compatible Score Export (UTF-8-SIG CSV)

**Files:**
- Create: `server/bracket_export.py`
- Modify: `server/routes/admin.py`
- Modify: `server/routes/admin_tournaments.py`
- Modify: `web/templates/admin.html`
- Modify: `web/templates/bracket.html`
- Create: `tests/test_bracket_export.py`

**Interfaces:**
- Consumes: `server.tournament.calculate_final_scores`, `BracketMatch`, `User`, `GameProfile`
- Produces:
  - `server.bracket_export.generate_tournament_score_csv(tournament_id: Optional[int], db: Session) -> str`
  - `GET /api/admin/bracket/export-scores` -> `Response(media_type="text/csv", headers={"Content-Disposition": ...})`

- [ ] **Step 1: Write tests in `tests/test_bracket_export.py`**

Cover 4 test cases:
1. `test_export_csv_starts_with_utf8_bom`: Output bytes start with `b"\xef\xbb\xbf"`.
2. `test_export_csv_contains_all_contestants_and_scores`: Headers and contestant rows contain usernames, Elo, Normalized Elo, Bracket points, and Final score.
3. `test_export_csv_auth_required`: Unauthenticated request returns 401/403.
4. `test_export_csv_content_disposition_header`: Response header specifies attachment filename ending in `.csv`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bracket_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.bracket_export'`.

- [ ] **Step 3: Implement `server/bracket_export.py`**

1. Query all completed `BracketMatch` records to map `user_id -> standing rank`:
   - Winner of Finals -> Rank 1 (Champion)
   - Loser of Finals -> Rank 2 (Runner-up)
   - Losers of Semifinals -> Rank 3-4
   - Losers of Quarterfinals -> Rank 5-8
2. Call `calculate_final_scores(users, bracket_standings)`.
3. Build CSV using `io.StringIO` and standard library `csv.writer`:
   - Write UTF-8 BOM `\ufeff`.
   - Header row: `Thứ hạng,Tên tài khoản,Điểm Elo,Điểm Elo chuẩn hóa (50%),Vòng Bracket đạt được,Điểm Bracket (50%),Tổng điểm chung cuộc`.
   - Data rows sorted by Final Score descending.
4. Return string encoded in UTF-8.

- [ ] **Step 4: Mount endpoints and update Web UI**

Mount `GET /bracket/export-scores` in `server/routes/admin.py` returning `Response(content=csv_bytes, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="battlecode_final_scores.csv"'})`.
Add download button in `web/templates/admin.html` and `web/templates/bracket.html`.

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_bracket_export.py -v`
Expected: PASS (4/4 passed).

- [ ] **Step 6: Commit**

```bash
git add server/bracket_export.py server/routes/admin.py server/routes/admin_tournaments.py web/templates/admin.html web/templates/bracket.html tests/test_bracket_export.py
git commit -m "feat(export): add Excel-compatible UTF-8-SIG CSV tournament score export"
```

---

### Task 4: Documentation Harmonization & Full Test Suite Regression

**Files:**
- Modify: `docs/ADMIN_GUIDE.md`
- Modify: `docs/CONTEXT_RESUME.md`
- Modify: `TASKS.md`

- [ ] **Step 1: Update `docs/ADMIN_GUIDE.md`**
Document password-confirmed bracket generation, BO3 execution controls, and CSV score export.

- [ ] **Step 2: Update `docs/CONTEXT_RESUME.md`**
Harmonize Section 17 with playoff bracket runner and score export features.

- [ ] **Step 3: Update `TASKS.md`**
Add tracking items for bracket execution and score export.

- [ ] **Step 4: Run full test suite regression**

Run: `python -m pytest -v`
Expected: 100% PASS (all existing + new tests passing, 0 failed).

- [ ] **Step 5: Commit documentation updates**

```bash
git add docs/ADMIN_GUIDE.md docs/CONTEXT_RESUME.md TASKS.md
git commit -m "docs: document password-confirmed bracket generation, BO3 runner, and Excel score export"
```
