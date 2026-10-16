# Rating History & Top Teams Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive, motivating Elo Rating Trajectory Visualizer (Pure SVG multi-line chart, Zero-npm) displaying live rating curves for the Top 5 teams on the Leaderboard and personal Elo history on the Profile page.

**Architecture:** Reconstruct historical Elo points chronologically from completed `Match` database entities in a dedicated service `server/rating_history.py`. Expose REST endpoints `GET /api/leaderboard/rating-history` and `GET /api/users/{user_id}/rating-history`. Render responsive, tooltip-enabled SVG charts in Vanilla JS with minimalist Charcoal styling.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (SQLite WAL), HTML5, CSS3 Design Tokens, Vanilla JavaScript SVG.

**Spec:** `docs/superpowers/specs/2026-10-10-rating-history-visualizer-design.md`

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies. Pure HTML5, CSS3, Vanilla JS.
- Minimalist Charcoal design palette (`--bg-main: #0d1117`, `--bg-surface: #161b22`, `--border-subtle: #30363d`, `--text-primary: #f0f6fc`, `--text-muted: #8b949e`).
- All code comments and docstrings in clear, detailed English.
- No decorative emojis or icons in documentation, code comments, or commit messages.
- Continuous Feedback Loop Law: synchronize `docs/CONTEXT_RESUME.md` and `TASKS.md` immediately upon interface updates.

## Review Focus
1. User with 0 matches must return clean initial point (1200, delta=0) without crash.
2. Missing user ID in `GET /api/users/{user_id}/rating-history` must return HTTP 404 cleanly.
3. Chronological sorting must correctly track multiple matches in order of occurrence.
4. Top N parameter must be clamped safely between 1 and 10; limit clamped between 5 and 100.
5. Empty database / no completed matches must display friendly motivational notice without SVG rendering exceptions.

---

### Task 1: Rating History Backend Service & Data Reconstruction

**Files:**
- Create: `server/rating_history.py`
- Test: `tests/test_rating_history.py`

**Interfaces:**
- Produces:
  - `get_user_rating_history(user_id: int, db: Session, limit: int = 50) -> Dict[str, Any]`
  - `get_top_teams_rating_history(db: Session, top: int = 5, limit: int = 30) -> Dict[str, Any]`

- [ ] **Step 1: Write the failing tests in `tests/test_rating_history.py`**

```python
def test_get_user_rating_history_zero_matches():
    # Verify user with 0 matches returns initial 1200 milestone
    ...

def test_get_user_rating_history_multiple_matches():
    # Verify chronological sequence and delta calculation
    ...

def test_get_top_teams_rating_history():
    # Verify top N users returned with color badges and points
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rating_history.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Implement `server/rating_history.py`**

Implement chronological rating point calculation, assigning palette colors (`#2dd4bf`, `#38bdf8`, `#fbbf24`, `#c084fc`, `#f43f5e`), calculating Elo deltas from `Match` records.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rating_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/rating_history.py tests/test_rating_history.py
git commit -m "feat(api): implement rating history reconstruction service"
```

---

### Task 2: Leaderboard & User Rating History API Routes

**Files:**
- Modify: `server/routes/leaderboard.py`
- Test: `tests/test_rating_history.py`

**Interfaces:**
- Consumes: `server.rating_history.get_top_teams_rating_history`, `server.rating_history.get_user_rating_history`
- Produces:
  - `GET /api/leaderboard/rating-history`
  - `GET /api/users/{user_id}/rating-history`

- [ ] **Step 1: Write failing API route tests in `tests/test_rating_history.py`**

```python
def test_api_leaderboard_rating_history_endpoint():
    # Test GET /api/leaderboard/rating-history returns 200 and schema
    ...

def test_api_user_rating_history_endpoint():
    # Test GET /api/users/{user_id}/rating-history returns 200 or 404
    ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_rating_history.py::test_api_leaderboard_rating_history_endpoint -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Add endpoints to `server/routes/leaderboard.py`**

Mount endpoints with query parameter bounds (`top: int = Query(5, ge=1, le=10)`, `limit: int = Query(30, ge=5, le=100)`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rating_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/routes/leaderboard.py tests/test_rating_history.py
git commit -m "feat(api): expose rating history endpoints for leaderboard and user profile"
```

---

### Task 3: Vanilla JS Pure SVG Chart Visualizer Engine & Styling

**Files:**
- Create: `web/static/js/rating_chart.js`
- Modify: `web/static/css/style.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Produces:
  - Global JS object `window.RatingChart.render(containerId, data, options)`
  - CSS classes: `.chart-card`, `.chart-wrapper`, `.chart-svg`, `.chart-tooltip`, `.chart-legend`, `.legend-item`

- [ ] **Step 1: Write failing tests in `tests/test_web.py`**

```python
def test_rating_chart_static_asset_served():
    # Verify GET /static/js/rating_chart.js returns 200 and javascript mime
    ...

def test_rating_chart_css_tokens():
    # Verify style.css contains chart styling rules
    ...
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_web.py::test_rating_chart_static_asset_served -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Implement `web/static/js/rating_chart.js` and update `web/static/css/style.css`**

Pure SVG chart renderer with responsive viewBox, gridlines, multi-line polyline strokes, interactive circle points, hover tooltips, and legend highlights.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/static/js/rating_chart.js web/static/css/style.css tests/test_web.py
git commit -m "feat(ui): implement pure svg rating trajectory visualizer engine and styles"
```

---

### Task 4: Template Integration on Leaderboard & Profile Pages

**Files:**
- Modify: `web/templates/index.html`
- Modify: `web/templates/profile.html`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `web/static/js/rating_chart.js`, `/api/leaderboard/rating-history`, `/api/users/{user_id}/rating-history`

- [ ] **Step 1: Write failing tests in `tests/test_web.py`**

```python
def test_leaderboard_contains_rating_chart_container():
    # Verify index.html contains chart wrapper and script tag
    ...

def test_profile_contains_user_rating_chart_container():
    # Verify profile.html contains chart wrapper
    ...
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_web.py::test_leaderboard_contains_rating_chart_container -v`
Expected: FAIL (container not found)

- [ ] **Step 3: Update `web/templates/index.html` and `web/templates/profile.html`**

Embed `#rating-chart-card` and `#user-rating-chart-card` with fetch and rendering script invocations.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/templates/index.html web/templates/profile.html tests/test_web.py
git commit -m "feat(ui): integrate rating trajectory charts into leaderboard and profile templates"
```

---

### Task 5: Documentation Harmonization & Continuous Feedback Loop

**Files:**
- Modify: `docs/CONTEXT_RESUME.md`
- Modify: `TASKS.md`
- Modify: `README.md`
- Test: `tests/test_documentation_integrity.py`

**Interfaces:**
- Consumes: Documentation SSOT standards

- [ ] **Step 1: Write test in `tests/test_documentation_integrity.py` asserting Milestone 10 in TASKS.md and rating-history in docs**

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_documentation_integrity.py -v`
Expected: FAIL

- [ ] **Step 3: Update `docs/CONTEXT_RESUME.md`, `TASKS.md`, and `README.md`**

Document Section 16 in `docs/CONTEXT_RESUME.md` detailing Rating History API and SVG Visualizer. Add Milestone 10 in `TASKS.md`. Keep completely emoji-free.

- [ ] **Step 4: Run full test suite across entire project**

Run: `pytest -q`
Expected: 100% PASS

- [ ] **Step 5: Commit**

```bash
git add docs/ TASKS.md README.md tests/test_documentation_integrity.py
git commit -m "docs: synchronize rating history visualizer architecture and milestone records"
```
