# Rating History & Top Teams Visualizer Design Specification

## 1. Overview & Objective
To enhance player motivation and competitive drive in the Battlecode RPS 9x9 tournament, this feature introduces an interactive, motivating Elo Rating Trajectory Visualizer. Similar to competitive platforms (Codeforces, Chess.com), players and spectators can inspect how ratings fluctuate over time, track the trajectories of the Top 5/Top 8 teams, and analyze individual rating curves.

---

## 2. Global Constraints & Standards
- **Zero Node.js / npm dependencies**: Pure Python 3.10+, FastAPI, SQLite WAL, HTML5, CSS3, and Vanilla JavaScript.
- **Charcoal Design Tokens**: Seamless integration with the minimalist dark palette (`#0d1117`, `#161b22`, `#30363d`, `#f0f6fc`, `#8b949e`).
- **No Decorative Emojis**: All documentation, code comments, and commit messages must strictly avoid decorative emojis.
- **Continuous Feedback Loop Law**: Any schema, route, or architectural updates must be immediately synchronized with `docs/CONTEXT_RESUME.md` and `TASKS.md`.
- **Test-Driven Development (TDD)**: 100% test pass on full test suite before merge.

---

## 3. Architecture & Data Flow

### 3.1 Backend Service: `server/rating_history.py` & API Endpoints
The backend reconstructs historical rating points directly from completed `Match` records (`player1_id`, `player2_id`, `p1_elo_after`, `p2_elo_after`, `created_at`) ordered chronologically, eliminating data duplication.

1. **`GET /api/leaderboard/rating-history`**:
   - Query Parameters: `top: int = 5` (clamped 1 to 10), `limit: int = 30` (max matches per user).
   - Logic:
     - Identifies the top N active users ranked by current Elo descending.
     - For each top user, fetches their completed non-bracket matches sorted by `created_at ASC`.
     - Reconstructs points sequence:
       - Initial entry: `match_id: 0`, `elo: 1200` (or `p*_elo_before` of first match), `created_at: <user.created_at>`, `delta: 0`.
       - Subsequent entries: `match_id`, `created_at`, `elo: p*_elo_after`, `delta: p*_elo_after - p*_elo_before`, `opponent_username`.
     - Assigns distinct accent colors from the curated palette:
       - Rank 1: Cyan/Teal `#2dd4bf`
       - Rank 2: Sky Blue `#38bdf8`
       - Rank 3: Amber `#fbbf24`
       - Rank 4: Purple `#c084fc`
       - Rank 5: Rose `#f43f5e`
   - Response Payload Schema:
     ```json
     {
       "users": [
         {
           "id": 1,
           "username": "apex_master",
           "current_elo": 1800,
           "color": "#2dd4bf",
           "points": [
             {"match_id": 0, "created_at": "2026-10-09T18:00:00", "elo": 1200, "delta": 0, "opponent": "Start"},
             {"match_id": 12, "created_at": "2026-10-09T19:30:00", "elo": 1264, "delta": 64, "opponent": "novice"}
           ]
         }
       ]
     }
     ```

2. **`GET /api/users/{user_id}/rating-history`**:
   - Query Parameters: `limit: int = 50`.
   - Returns individual user history sequence with match summaries and peak rating metrics.

### 3.2 Frontend Visualizer: Pure SVG Multi-Line Chart (`web/static/js/rating_chart.js`)
- **Container**: Rendered inside `#rating-chart-container` above the Leaderboard table in `web/templates/index.html`.
- **SVG Engine**:
  - Dynamically calculates X (time/match index) and Y (Elo value clamped between `min_elo - 50` and `max_elo + 50`).
  - Generates gridlines at clean intervals (1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800...).
  - Draws smooth `<polyline>` elements per user with glowing 2px stroke and distinct colors.
  - Draws interactive `<circle>` points at each match milestone.
  - Interactive tooltip element `#chart-tooltip` positioning dynamically on hover, displaying:
    `[Player Name] | Match #[id] | Elo: [value] ([+delta]) | Opponent: [name] | Time: [HH:MM]`.
  - Interactive Legend: Clicking or hovering over a user badge highlights their trajectory line while dimming other lines.
  - Fallback display: When fewer than 2 matches exist, renders a clean slate with a motivating notice: "Chưa có đủ dữ liệu trận đấu để dựng biểu đồ. Hãy thi đấu thêm để biểu đồ xuất hiện!".

### 3.3 Profile Page Sparkline: `web/templates/profile.html`
- Embedded personal rating card displaying current Elo, peak Elo, lowest Elo, and a dedicated personal SVG trajectory line.

---

## 4. Testing Strategy
- `tests/test_rating_history.py`:
  - Verify `GET /api/leaderboard/rating-history` returns proper status 200 and schema.
  - Verify parameter clamping (`top` clamped to [1, 10], `limit` clamped to [5, 100]).
  - Verify chronological order and correct calculation of Elo deltas.
  - Verify behavior with 0 matches (returns initial points cleanly).
  - Verify individual `GET /api/users/{user_id}/rating-history` 200 and 404 for missing user.
- `tests/test_web.py`:
  - Verify `web/static/js/rating_chart.js` is served and syntax is valid.
  - Verify `index.html` and `profile.html` include the chart containers and scripts.
- Documentation Integrity:
  - Verify zero emojis across all markdown documentation.
